"""Filesystem state transitions used by the Linux runner, without Windows symlink rights."""
from evals.tddbench.fsmodel import restore_source, through_link


def test_installed_source_copy_hashes_only_declared_public_files(tmp_path):
    """C-6.14 - only matching declared bytes are copied and the bound runtime controls source mode."""
    from hashlib import sha256
    import pytest
    from evals.tddbench.fsmodel import copy_installed_source
    source=tmp_path/'source';source.mkdir()
    text=b'PUBLIC = True\n'
    (source/'public.py').write_bytes(text)
    (source/'unlisted.py').write_text('NOT_PUBLIC = True\n')
    snapshot={'files':[{'path':'public.py','sha256':sha256(text).hexdigest()}]}
    work=tmp_path/'work'
    copy_installed_source(snapshot,source,work)
    assert (work/'public.py').read_bytes()==text
    assert not (work/'unlisted.py').exists()
    (source/'public.py').write_text('CHANGED = True\n')
    with pytest.raises(ValueError,match='bytes differ'):
        copy_installed_source(snapshot,source,tmp_path/'bad')
    assert not (tmp_path/'bad/public.py').exists()


def test_public_build_artifacts_restore_exact_bytes_without_replacing_source(tmp_path):
    """C-6.12 - exact additional outputs are copied while public source, path boundaries and inventory fingerprints are enforced."""
    import pytest
    from evals.tddbench.build_artifacts import inventory_build_artifacts, restore_build_artifacts
    source, work = tmp_path / 'installed', tmp_path / 'work'
    for root in (source, work):
        (root / 'pkg').mkdir(parents=True)
        (root / 'pkg/source.py').write_text('PUBLIC = True\n')
    snapshot = {'files': [{'path': 'pkg/source.py', 'kind': 'file'}]}
    (source / 'pkg/_compiled.so').write_bytes(b'build output\x00')
    (source / 'build').mkdir()
    (source / 'build/temporary.o').write_bytes(b'not a runtime output')
    items = inventory_build_artifacts(snapshot, source)
    assert [item['path'] for item in items] == ['pkg/_compiled.so']
    restore_build_artifacts(snapshot, items, source, work)
    assert (work / 'pkg/_compiled.so').read_bytes() == b'build output\x00'
    assert (work / 'pkg/source.py').read_text() == 'PUBLIC = True\n'
    with pytest.raises(ValueError, match='already exists'):
        restore_build_artifacts(snapshot, items, source, work)
    other = tmp_path / 'other'; other.mkdir()
    (source / 'pkg/_compiled.so').write_bytes(b'wrong output!')
    with pytest.raises(ValueError, match='differ'):
        restore_build_artifacts(snapshot, items, source, other)


def test_build_artifacts_reject_public_paths_link_traversal_and_forged_manifest():
    import pytest
    from evals.tddbench.build_artifacts import validate_artifacts
    snapshot = {'files': [{'path': 'pkg/source.py'}, {'path': 'alias', 'kind': 'symlink'}]}
    file = {'path': 'pkg/new.so', 'kind': 'file', 'sha256': 'a' * 64, 'size': 1, 'mode': 0o644}
    assert validate_artifacts(snapshot, [file]) == [file]
    for name in ('pkg/source.py', 'pkg', 'alias/new.so', '../escape', '/absolute', 'pkg/.git/config'):
        with pytest.raises(ValueError):
            validate_artifacts(snapshot, [{**file, 'path': name}])
    with pytest.raises(ValueError):
        validate_artifacts(snapshot, [file, file])
    with pytest.raises(ValueError):
        validate_artifacts(snapshot, [{**file, 'sha256': 'wrong'}])
    with pytest.raises(ValueError, match='escapes'):
        validate_artifacts(snapshot, [{'path': 'alias.so', 'kind': 'symlink', 'target': '../outside'}])


def test_source_layout_resolution_and_origin_boundary(tmp_path):
    """C-6.8 - only the declared source and runtime are credited."""
    from types import SimpleNamespace
    from evals.tddbench.fsmodel import python_source_paths, project_origin
    from evals.tddbench.execution import TEST_RUNNER
    compile(TEST_RUNNER, 'offline_runner', 'exec')
    root = tmp_path / 'work'
    (root / 'src/pkg').mkdir(parents=True)
    (root / 'lib').mkdir()
    origin = root / 'src/pkg/__init__.py'
    origin.write_text('VALUE=1')
    assert python_source_paths(root) == [str(root / 'src'), str(root / 'lib'), str(root)]
    assert project_origin('pkg', root, lambda m: SimpleNamespace(origin=str(origin)))['in_public_source']
    other = tmp_path / 'work-installed/pkg.py'
    other.parent.mkdir()
    other.write_text('VALUE=999')
    assert not project_origin('pkg', root, lambda m: SimpleNamespace(origin=str(other)))['in_public_source']
    assert not project_origin('pkg', root, lambda m: SimpleNamespace(origin='built-in'))['in_public_source']
    assert not project_origin('pkg', root, lambda m: None)['in_public_source']


def test_restoration_preserves_inode_types_targets_and_executable_mode():
    """C-6.7 - links and executable bits are restored, overlays cannot traverse links and the runtime permits temporary executable files."""
    state = {'package/actual.py': {'kind': 'file', 'mode': 0o644},
             'package/alias.py': {'kind': 'file', 'mode': 0o644},
             'alias_dir': {'kind': 'file', 'mode': 0o644}}
    class Node:
        def __init__(self, name):
            self.name = name
        def unlink(self):
            del state[self.name]
        def symlink_to(self, target):
            assert self.name not in state
            state[self.name] = {'kind': 'symlink', 'target': target}
        def chmod(self, mode):
            state[self.name]['mode'] = mode
    class Root:
        def __truediv__(self, name):
            return Node(name)
    snapshot = {'files': [
        {'path': 'package/actual.py', 'kind': 'file', 'mode': 0o755},
        {'path': 'package/alias.py', 'kind': 'symlink', 'target': 'actual.py'},
        {'path': 'alias_dir', 'kind': 'symlink', 'target': 'package'}]}
    restore_source(snapshot, Root())
    assert state['package/actual.py'] == {'kind': 'file', 'mode': 0o755}
    assert state['package/alias.py'] == {'kind': 'symlink', 'target': 'actual.py'}
    assert state['alias_dir'] == {'kind': 'symlink', 'target': 'package'}
    assert through_link('alias_dir/test_new.py', {'alias_dir'})
    assert not through_link('alias_directory/test_new.py', {'alias_dir'})
