"""Run the installed import-linter console entry point under Python/coverage.

The native console executable is not an importable module on Windows. This
bridge invokes the same installed entry point, without Git or shell execution.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution
import sys


def main() -> int:
    try:
        package = distribution('import-linter')
        matches = [ep for ep in package.entry_points if ep.group == 'console_scripts' and ep.name == 'lint-imports']
        if len(matches) != 1 or matches[0].value != 'importlinter.cli:lint_imports_command':
            print('unsupported import-linter console entry point', file=sys.stderr)
            return 2
        command = matches[0].load()
    except (PackageNotFoundError, ImportError) as exc:
        print('import-linter is unavailable: ' + str(exc), file=sys.stderr)
        return 2
    command(prog_name='lint-imports')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
