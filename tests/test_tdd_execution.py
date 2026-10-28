"""Offline test tools: runtime identity, test-only overlays and typed diagnostics."""
import json
import pathlib
import subprocess
from types import SimpleNamespace

import pytest

from evals.tddbench.adapter import sha
from evals.tddbench.execution import load_runtime, prepare_runtime, run_tests, validate_test_action

IMAGE = 'sweb.env.x86_64.' + 'a' * 22 + ':latest'
ID = 'sha256:' + 'b' * 64


@pytest.fixture
def public_runtime(tmp_path):
    root = tmp_path / 'public'
    (root / 'source').mkdir(parents=True)
    (root / 'source/api.py').write_bytes(b'pass\n')
    issue = {'instance_id': 'example__repo-1', 'repo': 'example/repo',
             'base_commit': 'a' * 40, 'problem_statement': 'Expected behavior.'}
    (root / 'issue.json').write_text(json.dumps(issue))
    snapshot = {'schema': 'athena.blind_workspace/1', **issue,
                'issue_sha256': sha((root / 'issue.json').read_bytes()),
                'files': [{'path': 'api.py', 'sha256': sha(b'pass\n')}]}
    (root / 'snapshot.json').write_text(json.dumps(snapshot))
    path = tmp_path / 'runtime.json'
    def runner(cmd, **kwargs):
        return SimpleNamespace(stdout=ID if cmd[1] == 'image' else json.dumps(
            {'empty_testbed': True, 'python': '3.9', 'pytest': '8.4', 'filesystem_encoding': 'utf-8'}))
    prepare_runtime(str(root), IMAGE, str(path), runner=runner)
    return root, path


def _contract_case_environment_runtime_is_pinned_and_bound_to_one_snapshot(public_runtime, tmp_path):
    root, path = public_runtime
    runtime = load_runtime(str(root), str(path))
    assert runtime['image_id'] == ID and runtime['probe']['empty_testbed'] is True
    def never(*args, **kwargs):
        pytest.fail('task image was not rejected before Docker access')
    with pytest.raises(ValueError, match='environment-only'):
        prepare_runtime(str(root), 'sweb.eval.x86_64.example__repo-1:latest', str(tmp_path / 'bad.json'), runner=never)
    runtime['instance_id'] = 'another__repo-2'
    path.write_text(json.dumps(runtime))
    with pytest.raises(ValueError, match='snapshot'):
        load_runtime(str(root), str(path))


def test_candidate_overlay_cannot_replace_implementation_or_runner_config():
    """C-6.6 - only test overlays are accepted, payload uses stdin and only public input and empty output are mounted."""
    assert validate_test_action({'files': {'tests/test_new.py': 'pass'}, 'tests': ['tests/test_new.py::test_x']})
    for name in ('api.py', '../tests/test_x.py', '/tests/test_x.py', 'tests/conftest.py', 'tests/__init__.py'):
        with pytest.raises(ValueError):
            validate_test_action({'files': {name: 'pass'}, 'tests': [name]})
    with pytest.raises(ValueError):
        validate_test_action({'files': {'tests/test_x.py': 'pass'}, 'tests': ['--override-ini=bad']})


def _contract_case_public_installed_runtime_requires_snapshot_labels_and_complete_inspection(public_runtime, tmp_path):
    from evals.tddbench.execution import PUBLIC_PROBE
    root, _ = public_runtime
    image = 'athena.public-runtime:public-install-control'
    labels = {'athena.public.instance': 'example__repo-1',
              'athena.public.snapshot': sha((root / 'snapshot.json').read_bytes())}
    info = {'public_source_verified': True, 'history_free': True, 'task_setup_present': False,
            'python': '3.9', 'pytest': '8.4', 'filesystem_encoding': 'utf-8', 'build_artifacts': [
                {'path': 'generated.so', 'kind': 'file', 'size': 1, 'mode': 0o644, 'sha256': 'a' * 64}]}
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == 'image':
            return SimpleNamespace(stdout=json.dumps(labels) if cmd[-1] == '{{json .Config.Labels}}' else ID)
        assert '--interactive' in cmd and cmd[-1] == PUBLIC_PROBE
        assert 'LANG=C.UTF-8' in cmd and 'LC_ALL=C.UTF-8' in cmd
        assert json.loads(kwargs['input'])['instance_id'] == 'example__repo-1'
        return SimpleNamespace(stdout=json.dumps(info))
    path = tmp_path / 'public-installed.json'
    prepare_runtime(str(root), image, str(path), runner=runner)
    result = load_runtime(str(root), str(path))
    assert result['schema'] == 'athena.public_runtime/2' and result['image_kind'] == 'public-installed'
    labels['athena.public.snapshot'] = 'wrong'
    count = len(calls)
    with pytest.raises(ValueError, match='labels'):
        prepare_runtime(str(root), image, str(tmp_path / 'bad-label.json'), runner=runner)
    assert all(cmd[1] == 'image' for cmd in calls[count:])
    labels['athena.public.snapshot'] = result['snapshot_sha256']
    info['history_free'] = False
    with pytest.raises(ValueError, match='inspection'):
        prepare_runtime(str(root), image, str(tmp_path / 'bad-inspection.json'), runner=runner)
    assert not (tmp_path / 'bad-inspection.json').exists()
    info['history_free'] = True
    info['filesystem_encoding'] = 'ascii'
    with pytest.raises(ValueError, match='UTF-8'):
        prepare_runtime(str(root), image, str(tmp_path / 'bad-encoding.json'), runner=runner)
    result['build_artifacts'][0]['sha256'] = 'b' * 64
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match='fingerprint'):
        load_runtime(str(root), str(path))
    result['probe']['public_source_verified'] = False
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match='snapshot'):
        load_runtime(str(root), str(path))


@pytest.mark.parametrize('code,xml,status', [
    (0, '<testsuite><testcase name="t"/></testsuite>', 'PASS'),
    (1, '<testsuite><testcase name="t"><failure type="AssertionError">AssertionError: bug</failure></testcase></testsuite>', 'ASSERTION_FAIL'),
    (2, '<testsuite><testcase name="t"><error>ImportError</error></testcase></testsuite>', 'TOOL_ERROR'),
    (0, '<testsuite><testcase name="t"><skipped/></testcase></testsuite>', 'TOOL_ERROR'),
    (0, '', 'TOOL_ERROR'),
])
def test_test_tool_preserves_typed_results_and_container_boundary(public_runtime, tmp_path, code, xml, status):
    """C-6.3 - infrastructure failures never become assertion witnesses."""
    root, runtime = public_runtime
    out = tmp_path / 'tool'
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == 'run':
            assert not list(out.iterdir())  # payload arrives through stdin, never a third mount
            assert kwargs['input'] and json.loads(kwargs['input'])['tests'] == ['tests/test_x.py']
            assert json.loads(kwargs['input'])['source_mode'] == 'environment-only'
            assert ID in cmd and '--network' in cmd and cmd[cmd.index('--network') + 1] == 'none'
            assert cmd[cmd.index('--user') + 1] == '65534:65534'
            assert 'LANG=C.UTF-8' in cmd and 'LC_ALL=C.UTF-8' in cmd
            assert 'exec' in cmd[cmd.index('--tmpfs') + 1].split(',')
            assert len([x for x in cmd if x == '--mount']) == 2
            (out / 'process.json').write_text(json.dumps({'exit_code': code}))
            if xml:
                (out / 'junit.xml').write_text(xml)
            (out / 'test.log').write_text('diagnostic output')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    result = run_tests(str(root), str(runtime), str(out),
                       {'files': {'tests/test_x.py': 'pass'}, 'tests': ['tests/test_x.py'],
                        'source_mode': 'public-installed'}, runner=runner)
    assert result['status'] == status and result['diagnostic_only'] is True
    assert result['tail'] == 'diagnostic output'
    name = calls[0][calls[0].index('--name') + 1]
    assert calls[-1] == ['docker', 'rm', '-f', name]
    assert (out / 'tool.json').exists() and (out / 'request.json').exists()


def test_source_origin_error_overrides_successful_junit(public_runtime, tmp_path):
    root, runtime = public_runtime
    out = tmp_path / 'origin-error'
    def runner(cmd, **kwargs):
        if cmd[1] == 'run':
            (out / 'process.json').write_text(json.dumps({
                'exit_code': 2, 'infrastructure_error': 'project import origin is outside public source'}))
            (out / 'junit.xml').write_text('<testsuite><testcase name="t"/></testsuite>')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    result = run_tests(str(root), str(runtime), str(out),
                       {'files': {'tests/test_x.py': 'pass'}, 'tests': ['tests/test_x.py']}, runner=runner)
    assert result['status'] == 'TOOL_ERROR'
    assert 'outside public source' in result['reason']


def test_timeout_cleans_only_its_container_and_never_counts_as_assertion(public_runtime, tmp_path):
    """C-6.4 - only the invocation's container is removed and the result remains TIMEOUT."""
    root, runtime = public_runtime
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == 'run':
            raise subprocess.TimeoutExpired(cmd, 1)
        return SimpleNamespace(returncode=0)
    result = run_tests(str(root), str(runtime), str(tmp_path / 'timeout'),
                       {'files': {'tests/test_x.py': 'pass'}, 'tests': ['tests/test_x.py']},
                       timeout=1, runner=runner)
    assert result['status'] == 'TIMEOUT'
    assert calls[-1][3] == calls[0][calls[0].index('--name') + 1]


def _contract_case_generator_run_action_obeys_separate_test_budget(public_runtime, tmp_path, monkeypatch):
    from evals.tddbench.generator import Budget, generate_direct
    import evals.tddbench.execution as execution
    root, runtime = public_runtime
    tool_calls = []
    def tool(*args, **kwargs):
        tool_calls.append((args, kwargs))
        return {'status': 'ASSERTION_FAIL', 'tests': 1, 'diagnostic_only': True,
                'command': 'HOST-COMMAND-MUST-NOT-ENTER-MODEL-CONTEXT'}
    monkeypatch.setattr(execution, 'run_tests', tool)
    seen = []
    patch = 'diff --git a/tests/test_x.py b/tests/test_x.py\n--- /dev/null\n+++ b/tests/test_x.py\n@@ -0,0 +1 @@\n+assert True\n'
    def model(messages, budget):
        assert json.loads(messages[1]['content'])['execution_runtime']['python'] == '3.9'
        seen.append(messages)
        action = {'action': 'run', 'files': {'tests/test_x.py': 'pass'}, 'tests': ['tests/test_x.py']}
        if len(seen) == 3:
            action = {'action': 'finish', 'patch': patch}
        return {'text': json.dumps(action), 'finish_reason': 'stop'}
    out = tmp_path / 'generated'
    result = generate_direct(str(root), str(out), model, runtime_receipt=str(runtime),
                             budget=Budget(max_calls=3, max_test_runs=1))
    assert result['status'] == 'GENERATED' and result['test_runs'] == 1 and len(tool_calls) == 1
    assert result['runtime_image_id'] == ID and result['code_tools'] == 'offline-pytest'
    assert 'test-run budget exhausted' in seen[-1][-1]['content']
    assert 'HOST-COMMAND' not in (out / 'transcript.json').read_text()


def test_environment_runtime_is_pinned_and_bound_to_one_snapshot_C_6_1(public_runtime, tmp_path):
    """C-6.1 - task-image tags and changed instance identity are rejected."""
    _contract_case_environment_runtime_is_pinned_and_bound_to_one_snapshot(public_runtime, tmp_path)


def test_environment_runtime_is_pinned_and_bound_to_one_snapshot_C_6_10(public_runtime, tmp_path):
    """C-6.10 - only a matching completely inspected runtime is admitted."""
    _contract_case_environment_runtime_is_pinned_and_bound_to_one_snapshot(public_runtime, tmp_path)


def test_generator_run_action_obeys_separate_test_budget_C_6_5(public_runtime, tmp_path, monkeypatch):
    """C-6.5 - only one execution occurs, runtime identity is retained and host commands never enter model context."""
    _contract_case_generator_run_action_obeys_separate_test_budget(public_runtime, tmp_path, monkeypatch)


def test_generator_run_action_obeys_separate_test_budget_C_6_9(public_runtime, tmp_path, monkeypatch):
    """C-6.9 - only the declared source and runtime are credited."""
    _contract_case_generator_run_action_obeys_separate_test_budget(public_runtime, tmp_path, monkeypatch)


def test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_11(public_runtime, tmp_path):
    """C-6.11 - only a matching completely inspected runtime is admitted."""
    _contract_case_public_installed_runtime_requires_snapshot_labels_and_complete_inspection(public_runtime, tmp_path)


def test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_13(public_runtime, tmp_path):
    """C-6.13 - locale flags are explicit and an inspected ASCII filesystem is rejected."""
    _contract_case_public_installed_runtime_requires_snapshot_labels_and_complete_inspection(public_runtime, tmp_path)
