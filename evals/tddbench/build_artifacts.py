"""Portable inventory and restoration of public project installation outputs."""


def validate_artifacts(snapshot, items):
    import re
    import posixpath
    if not isinstance(items, list) or len(items) > 20000:
        raise ValueError('invalid build artifact inventory')
    known = {item['path'] for item in snapshot['files']}
    directories = {'/'.join(name.split('/')[:index]) for name in known
                   for index in range(1, len(name.split('/')))}
    links = {item['path'] for item in snapshot['files'] if item.get('kind') == 'symlink'}
    seen, total = set(), 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('invalid build artifact entry')
        name = item.get('path')
        if (not isinstance(name, str) or not name or '\\' in name or ':' in name or
                any(part in ('', '.', '..') or part.lower() == '.git' for part in name.split('/'))):
            raise ValueError('invalid build artifact path')
        if name in known or name in directories or name in seen:
            raise ValueError('build artifact overlaps public source or another artifact')
        seen.add(name)
        if item.get('kind') == 'symlink':
            target = item.get('target')
            if not isinstance(target, str) or not target or target.startswith('/') or '\\' in target or ':' in target:
                raise ValueError('invalid build artifact link')
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
            if resolved == '..' or resolved.startswith('../'):
                raise ValueError('build artifact link escapes source')
            links.add(name)
        elif item.get('kind') == 'file':
            if not re.fullmatch('[a-f0-9]{64}', item.get('sha256', '')):
                raise ValueError('invalid build artifact hash')
            size, mode = item.get('size'), item.get('mode')
            if type(size) is not int or size < 0 or mode not in (0o644, 0o755):
                raise ValueError('invalid build artifact size or mode')
            total += size
        else:
            raise ValueError('unsupported build artifact type')
    if total > 512 * 1024 * 1024:
        raise ValueError('build artifacts exceed offline workspace budget')
    for name in seen:
        parents = {'/'.join(name.split('/')[:index]) for index in range(1, len(name.split('/')))}
        if parents & links:
            raise ValueError('build artifact traverses a source or artifact link')
        if parents & (known | seen):
            raise ValueError('build artifact parent is a file')
    return items


def inventory_build_artifacts(snapshot, root):
    import hashlib
    import os
    import pathlib
    known = {item['path'] for item in snapshot['files']}
    items = []
    for folder, dirs, files in os.walk(str(root), followlinks=False):
        dirs[:] = [name for name in dirs if name not in ('.git', '__pycache__') and
                   not (pathlib.Path(folder) == root and name in ('build', 'dist', '.eggs'))]
        for name in sorted(files + [name for name in dirs if (pathlib.Path(folder) / name).is_symlink()]):
            path = pathlib.Path(folder) / name
            rel = path.relative_to(root).as_posix()
            if rel in known or rel.endswith(('.pyc', '.pyo')):
                continue
            if path.is_symlink():
                path.resolve(strict=True).relative_to(root)
                items.append({'path': rel, 'kind': 'symlink', 'target': os.readlink(str(path))})
            elif path.is_file():
                items.append({'path': rel, 'kind': 'file', 'size': path.stat().st_size,
                              'mode': 0o755 if path.stat().st_mode & 0o111 else 0o644,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            else:
                raise ValueError('special build artifact')
    return validate_artifacts(snapshot, sorted(items, key=lambda item: item['path']))


def restore_build_artifacts(snapshot, items, source, destination):
    import hashlib
    import os
    import pathlib
    import shutil
    validate_artifacts(snapshot, items)
    for item in items:
        target = destination / item['path']
        if target.exists() or target.is_symlink():
            raise ValueError('build artifact destination already exists')
        target.parent.mkdir(parents=True, exist_ok=True)
        original = source / item['path']
        original.resolve(strict=True).relative_to(source)
        if item['kind'] == 'file':
            if original.is_symlink() or original.stat().st_size != item['size']:
                raise ValueError('build artifact type or size differs')
            if hashlib.sha256(original.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('build artifact bytes differ')
            shutil.copyfile(str(original), str(target))
            target.chmod(item['mode'])
    # Files precede links, so no writes can traverse newly restored aliases.
    for item in items:
        if item['kind'] == 'symlink':
            original = source / item['path']
            if not original.is_symlink() or os.readlink(str(original)) != item['target']:
                raise ValueError('build artifact link differs')
            (destination / item['path']).symlink_to(item['target'])
    for item in items:
        if item['kind'] == 'symlink':
            (destination / item['path']).resolve(strict=True).relative_to(destination)
