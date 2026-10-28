"""Apply test-only unified diffs to verified public text without invoking Git."""
from __future__ import annotations

import pathlib
import re

from .execution import _test_path
from .fsmodel import through_link
from .workspace import verify_workspace


def validate_patch(directory: str, patch: str) -> str:
    """Return a canonical patch; reject hidden payloads, implementation and stale hunks."""
    if not isinstance(patch, str) or not patch.endswith('\n') or len(patch.encode('utf-8')) > 1024 * 1024:
        raise ValueError('finish requires a newline-terminated test patch within one megabyte')
    snapshot = verify_workspace(directory)
    links = {item['path'] for item in snapshot['files'] if item.get('kind') == 'symlink'}
    root = pathlib.Path(directory) / 'source'
    lines, files, i = patch.splitlines(keepends=True), {}, 0
    while i < len(lines):
        header = re.fullmatch(r'diff --git a/(\S+) b/(\S+)\n', lines[i])
        if not header or header[1] != header[2]:
            raise ValueError('only same-path test file diffs are supported')
        name = header[1]
        _test_path(name)
        if name in files or len(files) >= 20 or through_link(name, links):
            raise ValueError('duplicate, linked or excessive test patch paths')
        i += 1
        while i < len(lines) and (lines[i] == 'new file mode 100644\n' or
                re.fullmatch(r'index [a-f0-9]+\.\.[a-f0-9]+(?: 100644)?\n', lines[i])):
            i += 1
        path = root / name
        old = path.read_text(encoding='utf-8') if path.is_file() else ''
        old_header = '--- a/' + name + '\n' if path.is_file() else '--- /dev/null\n'
        if lines[i:i+2] != [old_header, '+++ b/' + name + '\n']:
            raise ValueError('patch headers do not match public test file')
        i += 2
        original, result, cursor, hunks = old.splitlines(keepends=True), [], 0, 0
        while i < len(lines) and not lines[i].startswith('diff --git '):
            hunk = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n', lines[i])
            if not hunk:
                raise ValueError('unexpected patch metadata or malformed hunk')
            old_start, old_count, new_start, new_count = (int(hunk[1]), int(hunk[2] or 1),
                                                          int(hunk[3]), int(hunk[4] or 1))
            start = old_start if old_count == 0 else old_start - 1
            if start < cursor or start > len(original):
                raise ValueError('patch hunk is outside the public file')
            result.extend(original[cursor:start])
            if new_start != len(result) + (1 if new_count else 0):
                raise ValueError('inconsistent new hunk position')
            i += 1
            entries = []
            while i < len(lines) and not lines[i].startswith(('@@ ', 'diff --git ')):
                line = lines[i]
                if line == '\\ No newline at end of file\n':
                    if not entries or not entries[-1][1].endswith('\n'):
                        raise ValueError('invalid no-newline marker')
                    entries[-1] = (entries[-1][0], entries[-1][1][:-1])
                elif line[:1] in (' ', '+', '-'):
                    entries.append((line[0], line[1:]))
                else:
                    raise ValueError('unexpected patch body')
                i += 1
            before = [value for kind, value in entries if kind in (' ', '-')]
            after = [value for kind, value in entries if kind in (' ', '+')]
            if len(before) != old_count or len(after) != new_count or original[start:start+old_count] != before:
                raise ValueError('patch hunk does not match public source')
            result.extend(after)
            cursor, hunks = start + old_count, hunks + 1
        if not hunks:
            raise ValueError('patch file has no hunks')
        result.extend(original[cursor:])
        files[name] = ''.join(result)
    if not files:
        raise ValueError('patch contains no test changes')
    # Canonical re-emission drops all metadata and retains only verified test content.
    from .native import test_patch
    return test_patch(directory, files)
