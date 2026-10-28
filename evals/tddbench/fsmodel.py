"""Portable snapshot restoration; executed only in the offline Linux workspace."""


def restore_source(snapshot, root):
    """Host snapshots hold inert link files. Recreate POSIX types before running tests."""
    for item in snapshot['files']:
        path = root / item['path']
        if item.get('kind') == 'symlink':
            path.unlink()
            path.symlink_to(item['target'])
        elif 'mode' in item:
            path.chmod(item['mode'])


def through_link(name, links):
    return any(name == link or name.startswith(link + '/') for link in links)


def copy_installed_source(snapshot, source, destination):
    """Stage verified image-resident public files without Windows bind-mount latency."""
    import hashlib
    import os
    import shutil
    destination.mkdir()
    for item in snapshot['files']:
        original, target = source / item['path'], destination / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.get('kind') == 'symlink':
            if not original.is_symlink() or os.readlink(str(original)) != item['target']:
                raise ValueError('installed public source link differs')
            # The shared POSIX restorer creates all links after the regular files.
            target.write_bytes(b'')
        else:
            original.resolve(strict=True).relative_to(source)
            if original.is_symlink() or not original.is_file():
                raise ValueError('installed public source file missing')
            if hashlib.sha256(original.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('installed public source bytes differ')
            shutil.copyfile(str(original), str(target))


def python_source_paths(root):
    """Conventional layouts used by the frozen Python benchmark repositories."""
    return [str(path) for path in (root / 'src', root / 'lib', root) if path.is_dir()]


def project_origin(module, root, finder=None):
    """Diagnostic boundary: installed or sibling code is not the copied base revision."""
    import importlib.util
    import pathlib
    if finder is None:
        finder = importlib.util.find_spec
    try:
        spec = finder(module)
        origin = getattr(spec, 'origin', None)
        path = pathlib.Path(origin) if origin not in (None, 'built-in', 'frozen') else None
        inside = False
        if path is not None and path.is_file():
            try:
                path.resolve().relative_to(root.resolve())
                inside = True
            except ValueError:
                pass
        return {'module': module, 'origin': origin, 'in_public_source': inside}
    except Exception as error:
        return {'module': module, 'in_public_source': False, 'reason': type(error).__name__}
