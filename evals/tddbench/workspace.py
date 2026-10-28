"""Export a base-revision workspace using public inputs only, without Git history."""
from __future__ import annotations

import io
import json
import pathlib
import re
import tarfile
import tempfile
import urllib.request

from .adapter import PUBLIC_FIELDS, sha

MAX_ARCHIVE = 128 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024


def link_placeholder(target: str) -> bytes:
    return ('ATHENA_SYMLINK\n' + target + '\n').encode('utf-8')


def resolve_link(name: str, links: dict[str, str]) -> str:
    """Resolve POSIX link components without touching host files, including chained .. ."""
    pending = name.split('/')
    stack = []
    hops = 0
    while pending:
        part = pending.pop(0)
        if part in ('', '.'):
            continue
        if part == '..':
            if not stack:
                raise ValueError('symlink escapes archive root')
            stack.pop()
            continue
        if part.casefold() == '.git' or '\\' in part or ':' in part or '\x00' in part:
            raise ValueError('unsafe symlink target')
        key = '/'.join([*stack, part])
        if key in links:
            target = links[key]
            if not isinstance(target, str) or not target or target.startswith('/'):
                raise ValueError('unsafe symlink target')
            hops += 1
            if hops > 40:
                raise ValueError('symlink cycle or excessive chain')
            pending = target.split('/') + pending
        else:
            stack.append(part)
    return '/'.join(stack)


def export_workspace(public_file: str, instance_id: str, destination: str, *,
                     opener=urllib.request.urlopen) -> dict:
    """Download exactly the requested base revision; never open sealed benchmark data."""
    raw = pathlib.Path(public_file).read_bytes()
    rows = json.loads(raw)
    if not isinstance(rows, list) or not rows:
        raise ValueError('public input must be a nonempty list')
    seen = set()
    selected = None
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(PUBLIC_FIELDS):
            raise ValueError('only public fields are allowed; sealed inputs are forbidden')
        if any(not isinstance(row[k], str) or not row[k] for k in PUBLIC_FIELDS):
            raise ValueError('public fields must be nonempty strings')
        if row['instance_id'] in seen:
            raise ValueError('duplicate public instance')
        seen.add(row['instance_id'])
        if row['instance_id'] == instance_id:
            selected = row
    if selected is None:
        raise ValueError('instance is not in the public cohort')
    repo, revision = selected['repo'], selected['base_commit']
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)
            or any(x in ('.', '..') for x in repo.split('/'))
            or not re.fullmatch(r'[0-9a-f]{40}', revision)):
        raise ValueError('invalid repository or base revision')
    out = pathlib.Path(destination).resolve()
    if out.exists():
        raise ValueError('refusing to overwrite a generator workspace')
    url = f'https://codeload.github.com/{repo}/tar.gz/{revision}'
    request = urllib.request.Request(url, headers={'User-Agent': 'Athena-blind-workspace/1'})
    with opener(request, timeout=120) as response:
        archive = response.read(MAX_ARCHIVE + 1)
    if len(archive) > MAX_ARCHIVE:
        raise ValueError('base archive exceeds size limit')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='athena-public-', dir=out.parent) as tmp:
        stage = pathlib.Path(tmp) / 'workspace'
        source = stage / 'source'
        source.mkdir(parents=True)
        files = {}
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
            members = tar.getmembers()
            roots = set()
            spellings = {}
            links = {}
            total = 0
            for member in members:
                p = pathlib.PurePosixPath(member.name)
                # Symlinks become explicit inert metadata on the host, restored only
                # inside the offline Linux runtime. No archive link is followed here.
                reserved = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)),
                            *(f'lpt{i}' for i in range(1, 10))}
                if (not p.parts or p.is_absolute() or any(x.casefold() in ('.', '..', '.git') for x in p.parts)
                        or any(any(c in x for c in '\\:<>|"*?') or x.endswith((' ', '.'))
                               or x.split('.')[0].casefold() in reserved for x in p.parts)
                        or not (member.isfile() or member.isdir() or member.issym())):
                    raise ValueError('unsafe or unsupported archive member: ' + member.name)
                roots.add(p.parts[0])
                if member.issym():
                    if len(p.parts) < 2:
                        raise ValueError('archive root cannot be a symlink')
                    links[pathlib.PurePosixPath(*p.parts[1:]).as_posix()] = member.linkname
                for length in range(1, len(p.parts) + 1):
                    spelling = pathlib.PurePosixPath(*p.parts[:length]).as_posix()
                    alias = spelling.casefold()
                    if alias in spellings and spellings[alias] != spelling:
                        raise ValueError('ambiguous archive path')
                    spellings[alias] = spelling
                total += member.size
            if len(roots) != 1 or len(members) > 100000 or total > MAX_EXPANDED:
                raise ValueError('invalid archive root or expanded size')
            resolved_links = {name: resolve_link(name, links) for name in links}
            for member in members:
                parts = pathlib.PurePosixPath(member.name).parts[1:]
                if any('/'.join(parts[:i]) in links for i in range(1, len(parts))):
                    raise ValueError('archive member traverses a symlink parent')
            for member in members:
                parts = pathlib.PurePosixPath(member.name).parts[1:]
                if not parts:
                    if not member.isdir():
                        raise ValueError('archive root must be a directory')
                    continue
                target = source.joinpath(*parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                key = pathlib.PurePosixPath(*parts).as_posix()
                if key.casefold() in files:
                    raise ValueError('duplicate archive path')
                target.parent.mkdir(parents=True, exist_ok=True)
                content = link_placeholder(member.linkname) if member.issym() else tar.extractfile(member).read()
                target.write_bytes(content)
                item = {'path': key, 'sha256': sha(content), 'mode': member.mode & 0o777,
                        'kind': 'symlink' if member.issym() else 'file'}
                if member.issym():
                    item.update(target=member.linkname, resolved_target=resolved_links[key])
                files[key.casefold()] = item
        if not files:
            raise ValueError('empty base repository')
        issue_raw = json.dumps(selected, ensure_ascii=False, indent=2).encode('utf-8')
        (stage / 'issue.json').write_bytes(issue_raw)
        receipt = {'schema': 'athena.blind_workspace/1', 'instance_id': instance_id,
                   'repo': repo, 'base_commit': revision, 'source_url': url,
                   'public_input_sha256': sha(raw), 'archive_sha256': sha(archive),
                   'issue_sha256': sha(issue_raw),
                   'files': list(files.values()), 'contains_git_history': False,
                   'filesystem_model': 'portable-posix-links/1',
                   'is_model_performance': False}
        (stage / 'snapshot.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        stage.rename(out)
    return receipt


def verify_workspace(directory: str) -> dict:
    root = pathlib.Path(directory).resolve()
    if {p.name for p in root.iterdir()} != {'source', 'issue.json', 'snapshot.json'}:
        raise ValueError('workspace contains unexpected top-level artifacts')
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('workspace contains links')
    receipt = json.loads((root / 'snapshot.json').read_text(encoding='utf-8'))
    issue_raw = (root / 'issue.json').read_bytes()
    issue = json.loads(issue_raw)
    if (receipt.get('schema') != 'athena.blind_workspace/1' or set(issue) != set(PUBLIC_FIELDS)
            or sha(issue_raw) != receipt.get('issue_sha256')
            or any(issue[k] != receipt.get(k) for k in ('instance_id', 'repo', 'base_commit'))):
        raise ValueError('workspace identity differs from snapshot')
    actual = {p.relative_to(root / 'source').as_posix(): sha(p.read_bytes())
              for p in (root / 'source').rglob('*') if p.is_file()}
    expected = {f['path']: f['sha256'] for f in receipt['files']}
    if not actual or actual != expected:
        raise ValueError('base source differs from snapshot')
    links = {f['path']: f['target'] for f in receipt['files'] if f.get('kind') == 'symlink'}
    for entry in receipt['files']:
        if entry.get('kind', 'file') not in ('file', 'symlink'):
            raise ValueError('unsupported filesystem entry')
        if 'mode' in entry and (type(entry['mode']) is not int or not 0 <= entry['mode'] <= 0o777):
            raise ValueError('invalid source file mode')
        if entry.get('kind') == 'symlink':
            if (resolve_link(entry['path'], links) != entry.get('resolved_target')
                    or sha(link_placeholder(entry['target'])) != entry['sha256']):
                raise ValueError('symlink metadata differs from snapshot')
    return receipt


def sandbox_command(directory: str, output: str, command: list[str]) -> list[str]:
    """Offline code-tool sandbox. The model API remains in the trusted orchestrator."""
    verify_workspace(directory)
    root, out = pathlib.Path(directory).resolve(), pathlib.Path(output).resolve()
    if (out == root or out.is_relative_to(root) or root.is_relative_to(out)
            or (out.exists() and (not out.is_dir() or any(out.iterdir())))):
        raise ValueError('sandbox output must be an empty, separate directory')
    if not command or not all(isinstance(x, str) and x for x in command):
        raise ValueError('sandbox command must be an argument vector')
    return ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '65534:65534', '--pids-limit', '128',
            '--memory', '1g', '--cpus', '1', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m',
            '--env', 'HOME=/tmp', '--env', 'PYTHONDONTWRITEBYTECODE=1', '--workdir', '/input/source',
            '--env', 'LANG=C.UTF-8', '--env', 'LC_ALL=C.UTF-8',
            '--mount', f'type=bind,source={root},target=/input,readonly',
            '--mount', f'type=bind,source={out},target=/output',
            '--entrypoint', command[0], 'athena-tdd-controller:20261024', *command[1:]]
