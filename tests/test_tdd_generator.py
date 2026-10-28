"""Protocol, public context and budget tests; no actual model or Git operations."""
import io
import json
import tarfile

import pytest

from evals.tddbench.generator import Budget, HTTPModel, generate_direct
from evals.tddbench.workspace import export_workspace


@pytest.fixture
def workspace(tmp_path):
    public = tmp_path / 'public.json'
    public.write_text(json.dumps([{'instance_id': 'psf__requests-1', 'repo': 'psf/requests',
                                 'base_commit': 'a' * 40, 'problem_statement': 'Preserve binary data.'}]))
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        value = b'def request(data):\n    return str(data)\n'
        item = tarfile.TarInfo('base/requests/api.py')
        item.size = len(value)
        tar.addfile(item, io.BytesIO(value))
    root = tmp_path / 'workspace'
    export_workspace(str(public), 'psf__requests-1', str(root),
                     opener=lambda *a, **k: io.BytesIO(stream.getvalue()))
    return root


PATCH = 'diff --git a/tests/test_binary.py b/tests/test_binary.py\nnew file mode 100644\n--- /dev/null\n+++ b/tests/test_binary.py\n@@ -0,0 +1 @@\n+assert True\n'


def test_model_sees_remaining_budget_without_receiving_extra_calls(workspace, tmp_path):
    """C-5.8 - the transcript exposes accurate remaining limits without extra calls, test runs or publication."""
    seen = []
    def model(messages, budget):
        current = json.loads(messages[-1]['content'])['execution_budget']
        seen.append(current)
        # A model cannot grant itself more requests through its response.
        return reply({'action': 'read', 'path': 'requests/api.py', 'execution_budget': {'max_calls': 999}})
    out = tmp_path / 'visible-budget'
    result = generate_direct(str(workspace), str(out), model,
                             budget=Budget(max_calls=3, max_test_runs=2, max_output_tokens=777))
    assert [item['generation_calls_available_including_current'] for item in seen] == [3, 2, 1]
    assert all(item['reserved_review_calls'] == 0 and item['test_runs_available'] == 2
               and item['output_tokens_acceptance_limit'] == 777 for item in seen)
    assert result['calls'] == 3 and result['status'] == 'INCOMPLETE'
    assert result['reason'] == 'model call budget exhausted'
    assert not (out / 'prediction.json').exists()
    transcript = json.loads((out / 'transcript.json').read_text())
    recorded = [json.loads(m['content'])['execution_budget'] for m in transcript
                if m['role'] == 'user' and 'execution_budget' in json.loads(m['content'])]
    assert recorded == seen


def reply(action, finish='stop'):
    return {'text': json.dumps(action), 'finish_reason': finish, 'usage': {'completion_tokens': 20}}


def _contract_case_final_patch_rejects_implementation_metadata_and_stale_hunks(workspace, tmp_path):
    from evals.tddbench.patches import validate_patch
    assert validate_patch(str(workspace), PATCH) == PATCH
    assert validate_patch(str(workspace), PATCH.replace('new file mode 100644\n', '')) == PATCH
    bad = [
        PATCH.replace('tests/test_binary.py', 'requests/api.py'),
        PATCH.replace('tests/test_binary.py', '../tests/test_binary.py'),
        PATCH.replace('tests/test_binary.py', 'tests/conftest.py'),
        PATCH.replace('--- /dev/null', 'new file mode 120000\n--- /dev/null'),
        PATCH.replace('@@ -0,0 +1 @@', '@@ -0,0 +1,2 @@'),
        PATCH + 'hidden command\n',
        PATCH + PATCH,
        'diff --git a/tests/test_binary.py b/tests/test_binary.py\n',
    ]
    for patch in bad:
        with pytest.raises(ValueError):
            validate_patch(str(workspace), patch)
    for index, patch in enumerate(bad[:2]):
        out = tmp_path / f'rejected-{index}'
        receipt = generate_direct(str(workspace), str(out),
                                  lambda *a: reply({'action': 'finish', 'patch': patch}),
                                  budget=Budget(max_calls=1))
        assert receipt['status'] == 'INCOMPLETE'
        assert not (out / 'prediction.json').exists()


def test_existing_test_patch_checks_context_and_preserves_untouched_lines(tmp_path):
    from evals.tddbench.patches import validate_patch
    public = tmp_path / 'public.json'
    public.write_text(json.dumps([{'instance_id': 'psf__requests-2', 'repo': 'psf/requests',
                                  'base_commit': 'b' * 40, 'problem_statement': 'Regression.'}]))
    stream = io.BytesIO()
    old = b'assert 1\nassert 2\nassert 3\n'
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        item = tarfile.TarInfo('base/tests/test_old.py')
        item.size = len(old)
        tar.addfile(item, io.BytesIO(old))
    root = tmp_path / 'existing'
    export_workspace(str(public), 'psf__requests-2', str(root),
                     opener=lambda *a, **k: io.BytesIO(stream.getvalue()))
    patch = ('diff --git a/tests/test_old.py b/tests/test_old.py\n'
             '--- a/tests/test_old.py\n+++ b/tests/test_old.py\n'
             '@@ -2 +2 @@\n-assert 2\n+assert 4\n')
    result = validate_patch(str(root), patch)
    assert 'new file mode' not in result
    assert ' assert 1\n' in result and ' assert 3\n' in result
    assert '+assert 4\n' in result
    for stale in (patch.replace('-assert 2', '-assert 999'), patch.replace('@@ -2 +2 @@', '@@ -2 +3 @@')):
        with pytest.raises(ValueError):
            validate_patch(str(root), stale)
    assert (root / 'source/tests/test_old.py').read_bytes() == old


def test_generator_reads_public_source_and_preserves_candidate_provenance(workspace, tmp_path):
    """C-5.1 - the transcript contains only public source and the candidate remains unevaluated."""
    actions = [{'action': 'list'}, {'action': 'read', 'path': 'requests/api.py'},
               {'action': 'finish', 'patch': PATCH}]
    requests = []
    def model(messages, budget):
        requests.append(messages)
        assert budget.max_calls == 3
        return reply(actions[len(requests) - 1])
    out = tmp_path / 'generated'
    receipt = generate_direct(str(workspace), str(out), model, budget=Budget(max_calls=3))
    assert receipt['status'] == 'GENERATED' and receipt['calls'] == 3
    assert receipt['is_model_performance'] is False and receipt['source_kind'] == 'injected'
    assert 'return str(data)' in requests[-1][-1]['content']
    assert json.loads((out / 'prediction.json').read_text())[0]['model_patch'] == PATCH
    assert json.loads((out / 'receipt.json').read_text())['prediction_sha256']
    # Even an always-green test is just a candidate; only the external gate judges it.
    assert 'not yet applied or evaluated' in receipt['reason']
    assert 'private reference' not in (out / 'transcript.json').read_text()


def test_private_paths_are_denied_and_budget_has_no_hidden_retry(workspace, tmp_path):
    """C-5.2 - no private content reaches the transcript and no extra calls occur."""
    private = tmp_path / 'sealed.json'
    private.write_text('private reference test secret')
    messages_seen = []
    def model(messages, budget):
        messages_seen.append(messages)
        return reply({'action': 'read', 'path': '../sealed.json'})
    out = tmp_path / 'attempt'
    receipt = generate_direct(str(workspace), str(out), model, budget=Budget(max_calls=2))
    assert receipt['status'] == 'INCOMPLETE' and receipt['calls'] == 2
    assert receipt['reason'] == 'model call budget exhausted'
    assert 'not in the public source' in messages_seen[-1][-1]['content']
    assert 'private reference test secret' not in (out / 'transcript.json').read_text()
    assert not (out / 'prediction.json').exists()


def test_truncated_output_transport_error_and_context_exhaustion_are_incomplete(workspace, tmp_path):
    """C-5.3 - an incomplete receipt remains, no candidate exists and exception secrets are omitted."""
    truncated = generate_direct(str(workspace), str(tmp_path / 'truncated'),
                                lambda *a: reply({'action': 'finish', 'patch': PATCH}, finish='length'))
    assert truncated['status'] == 'INCOMPLETE' and truncated['calls'] == 1
    assert not (tmp_path / 'truncated/prediction.json').exists()
    def offline(*args):
        raise OSError('secret API credential must never be printed')
    failed = generate_direct(str(workspace), str(tmp_path / 'offline'), offline)
    assert failed['status'] == 'INCOMPLETE' and failed['calls'] == 1
    assert 'credential' not in (tmp_path / 'offline/receipt.json').read_text()
    def never(*args):
        pytest.fail('context budget exceeded before model call')
    exhausted = generate_direct(str(workspace), str(tmp_path / 'exhausted'), never,
                                budget=Budget(max_context_chars=10))
    assert exhausted['status'] == 'INCOMPLETE' and exhausted['calls'] == 0
    with pytest.raises(FileExistsError):
        generate_direct(str(workspace), str(tmp_path / 'offline'), never)


def test_http_transport_uses_explicit_config_and_records_usage_without_exposing_key(monkeypatch):
    """C-5.4 - request limits and authorization are correct and response evidence omits the key."""
    monkeypatch.setenv('ATHENA_BENCH_API_KEY', 'private-key')
    seen = []
    def opener(request, **kwargs):
        seen.append((request, kwargs))
        return io.BytesIO(json.dumps({'model': 'served-model', 'choices': [
            {'finish_reason': 'stop', 'message': {'content': '{"action":"list"}'}}],
            'usage': {'completion_tokens': 5}}).encode())
    model = HTTPModel('http://localhost:8000/v1', 'requested-model', opener=opener)
    result = model([{'role': 'user', 'content': 'public'}], Budget(max_output_tokens=100))
    request, kwargs = seen[0]
    assert request.full_url == 'http://localhost:8000/v1/chat/completions'
    assert request.get_header('Authorization') == 'Bearer private-key'
    assert json.loads(request.data)['max_tokens'] == 100
    assert kwargs['timeout'] == 120 and result['usage']['completion_tokens'] == 5
    assert result['served_model'] == 'served-model' and 'private-key' not in json.dumps(result)
    for url in ('http://user:password@host/v1', 'http://host/v1?key=secret'):
        with pytest.raises(ValueError):
            HTTPModel(url, 'model')


def test_generation_cli_defaults_to_no_model_calls(workspace, tmp_path, capsys, monkeypatch):
    """C-5.5 - it makes no model calls and creates no output directory."""
    from evals.tddbench.__main__ import main
    def never(*args):
        pytest.fail('dry-run made a model call')
    monkeypatch.setattr(HTTPModel, '__call__', never)
    out = tmp_path / 'dry-run'
    assert main(['generate', '--workspace', str(workspace), '--out', str(out),
                 '--endpoint', 'http://localhost:8000/v1', '--model', 'test-model']) == 0
    evidence = json.loads(capsys.readouterr().out)
    assert evidence['executed'] is False and evidence['mode'] == 'direct'
    assert not out.exists()


def test_changed_public_input_cannot_be_used_for_a_candidate(workspace, tmp_path):
    def modified_response(*args):
        issue = json.loads((workspace / 'issue.json').read_text())
        issue['problem_statement'] = 'tampered requirement'
        (workspace / 'issue.json').write_text(json.dumps(issue))
        return reply({'action': 'finish', 'patch': PATCH})
    out = tmp_path / 'modified'
    receipt = generate_direct(str(workspace), str(out), modified_response)
    assert receipt['status'] == 'INCOMPLETE' and receipt['calls'] == 1
    assert not (out / 'prediction.json').exists()


def test_final_patch_rejects_implementation_metadata_and_stale_hunks_C_5_6(workspace, tmp_path):
    """C-5.6 - only applicable test changes are published, and the public source remains unchanged."""
    _contract_case_final_patch_rejects_implementation_metadata_and_stale_hunks(workspace, tmp_path)


def test_final_patch_rejects_implementation_metadata_and_stale_hunks_C_5_7(workspace, tmp_path):
    """C-5.7 - new files receive Git creation metadata and existing-file edits do not."""
    _contract_case_final_patch_rejects_implementation_metadata_and_stale_hunks(workspace, tmp_path)
