"""Exercise the public-only workspace boundary without network or Git."""
import io
import json
import tarfile

import pytest

from evals.tddbench.workspace import export_workspace, sandbox_command, verify_workspace


def archive(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        for name, value in entries:
            item = tarfile.TarInfo(name)
            if value is None or isinstance(value, dict) and 'link' in value:
                item.type = tarfile.SYMTYPE
                item.linkname = '/private/gold.json' if value is None else value['link']
                tar.addfile(item)
            else:
                if isinstance(value, dict):
                    item.mode = value['mode']
                    value = value['content']
                content = value.encode()
                item.size = len(content)
                tar.addfile(item, io.BytesIO(content))
    return buffer.getvalue()


def public(tmp_path):
    path = tmp_path / 'public.json'
    path.write_text(json.dumps([{'instance_id': 'psf__requests-1', 'repo': 'psf/requests',
                                'base_commit': 'a' * 40, 'problem_statement': 'Request fails.'}]))
    return path


def test_workspace_contains_only_public_issue_and_base_files(tmp_path):
    """C-4.1 - source files and fingerprints exist without repository history, and overwrite is refused."""
    path = public(tmp_path)
    calls = []
    def opener(request, **kwargs):
        calls.append(request.full_url)
        return io.BytesIO(archive([('requests-aaa/requests/api.py', 'def get(): pass\n'),
                                  ('requests-aaa/tests/test_api.py', 'assert True\n')]))
    out = tmp_path / 'export'
    receipt = export_workspace(str(path), 'psf__requests-1', str(out), opener=opener)
    assert calls == ['https://codeload.github.com/psf/requests/tar.gz/' + 'a' * 40]
    assert (out / 'source/requests/api.py').read_text() == 'def get(): pass\n'
    assert json.loads((out / 'issue.json').read_text())['problem_statement'] == 'Request fails.'
    assert len(receipt['files']) == 2 and receipt['contains_git_history'] is False
    assert len(receipt['archive_sha256']) == 64
    with pytest.raises(ValueError, match='overwrite'):
        export_workspace(str(path), 'psf__requests-1', str(out), opener=opener)
    assert len(calls) == 1


def test_sealed_or_out_of_cohort_inputs_never_reach_network(tmp_path):
    """C-4.2 - validation rejects input before network access."""
    path = public(tmp_path)
    def offline(*args, **kwargs):
        pytest.fail('invalid input reached the network')
    with pytest.raises(ValueError, match='cohort'):
        export_workspace(str(path), 'missing', str(tmp_path / 'out'), opener=offline)
    rows = json.loads(path.read_text())
    rows[0]['test_patch'] = 'private reference test'
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match='sealed'):
        export_workspace(str(path), 'psf__requests-1', str(tmp_path / 'out'), opener=offline)


@pytest.mark.parametrize('entries', [
    [('root/../escape', 'bad')], [('root/.git/objects/secret', 'gold')],
    [('root/.GIT/config', 'gold')], [('root/link', None)],
    [('root/C:alias', 'bad')], [('root/NUL.py', 'bad')],
    [('one/a.py', 'a'), ('two/b.py', 'b')],
    [('root/A.py', 'a'), ('root/a.py', 'b')],
    [('root/Dir/a.py', 'a'), ('root/dir/b.py', 'b')],
    [('root/a', {'link': 'b'}), ('root/b', {'link': 'a'})],
    [('root/safe/a.py', 'pass'), ('root/dir/link', {'link': '../safe'}),
     ('root/escape', {'link': 'dir/link/../../private'})],
    [('root/dir', {'link': 'target'}), ('root/dir/injected.py', 'pass')],
])
def test_unsafe_snapshot_never_leaves_partial_workspace(tmp_path, entries):
    """C-4.7 - no partial workspace or outside file remains."""
    path = public(tmp_path)
    out = tmp_path / 'out'
    with pytest.raises(ValueError):
        export_workspace(str(path), 'psf__requests-1', str(out),
                         opener=lambda *args, **kwargs: io.BytesIO(archive(entries)))
    assert not out.exists() and not (tmp_path / 'escape').exists()


def test_sandbox_exposes_only_verified_public_workspace(tmp_path):
    """C-4.4 - only two mounts exist, input is read-only, network is disabled and changed source is rejected."""
    path = public(tmp_path)
    root, output = tmp_path / 'input', tmp_path / 'output'
    export_workspace(str(path), 'psf__requests-1', str(root),
                     opener=lambda *a, **k: io.BytesIO(archive([('base/api.py', 'pass\n')])))
    assert verify_workspace(str(root))['instance_id'] == 'psf__requests-1'
    cmd = sandbox_command(str(root), str(output), ['python', '-c', 'print(1)'])
    assert cmd[cmd.index('--network') + 1] == 'none'
    assert '--read-only' in cmd and '--volume' not in cmd
    mounts = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == '--mount']
    assert len(mounts) == 2 and mounts[0].endswith('target=/input,readonly')
    assert mounts[1].endswith('target=/output')
    assert all('docker.sock' not in x for x in cmd)
    with pytest.raises(ValueError, match='separate'):
        sandbox_command(str(root), str(root / 'nested'), ['python'])
    output.mkdir()
    (output / 'sealed.json').write_text('private')
    with pytest.raises(ValueError, match='empty'):
        sandbox_command(str(root), str(output), ['python'])
    (root / 'source/api.py').write_text('changed')
    with pytest.raises(ValueError, match='source differs'):
        sandbox_command(str(root), str(tmp_path / 'new-output'), ['python'])


def test_issue_tampering_invalidates_workspace(tmp_path):
    """C-4.5 - the issue fingerprint mismatch rejects it."""
    path = public(tmp_path)
    out = tmp_path / 'out'
    export_workspace(str(path), 'psf__requests-1', str(out),
                     opener=lambda *a, **k: io.BytesIO(archive([('base/api.py', 'pass\n')])))
    issue = json.loads((out / 'issue.json').read_text())
    issue['problem_statement'] = 'replaced issue'
    (out / 'issue.json').write_text(json.dumps(issue))
    with pytest.raises(ValueError, match='identity differs'):
        verify_workspace(str(out))


def test_contained_links_are_inert_on_host_and_file_modes_are_recorded(tmp_path):
    """C-4.8 - metadata preserves target and mode, no host symlinks exist and the reader returns link identity."""
    from evals.tddbench.generator import read_action
    path = public(tmp_path)
    out = tmp_path / 'out'
    entries = [('root/package/actual.py', {'content': 'VALUE = 1\n', 'mode': 0o755}),
               ('root/package/alias.py', {'link': 'actual.py'}), ('root/alias_dir', {'link': 'package'})]
    receipt = export_workspace(str(path), 'psf__requests-1', str(out),
                               opener=lambda *a, **k: io.BytesIO(archive(entries)))
    assert receipt['filesystem_model'] == 'portable-posix-links/1'
    assert not any(p.is_symlink() for p in out.rglob('*'))
    assert (out / 'source/package/alias.py').read_text().startswith('ATHENA_SYMLINK')
    snapshot = verify_workspace(str(out))
    assert next(f for f in snapshot['files'] if f['path'] == 'package/actual.py')['mode'] == 0o755
    alias = read_action(out, snapshot, {'action': 'read', 'path': 'package/alias.py'})
    assert alias == {'path': 'package/alias.py', 'kind': 'symlink', 'target': 'actual.py',
                     'resolved_target': 'package/actual.py'}
    from evals.tddbench.native import test_patch as make_patch
    from evals.tddbench.execution import validate_reference
    with pytest.raises(ValueError, match='symlinks'):
        make_patch(str(out), {'alias_dir/test_new.py': 'assert True\n'})
    with pytest.raises(ValueError):
        validate_reference(str(out), {'package/alias.py': 'VALUE=2\n'})
    data = json.loads((out / 'snapshot.json').read_text())
    next(f for f in data['files'] if f['path'] == 'package/alias.py')['target'] = '../../outside'
    (out / 'snapshot.json').write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify_workspace(str(out))
