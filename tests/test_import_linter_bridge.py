"""Native positive/negative controls for the import-linter console bridge."""
import os
from pathlib import Path
import subprocess
import sys


def test_import_linter_bridge_accepts_clean_imports_and_rejects_a_real_violation(tmp_path):
    """C-9.4 — the real external oracle accepts clean code and rejects a forbidden import."""
    repo = Path(__file__).resolve().parents[1]
    package = tmp_path / 'samplepkg'
    package.mkdir()
    module = package / '__init__.py'
    module.write_text('import pathlib\n', encoding='utf-8')
    config = tmp_path / 'imports.ini'
    config.write_text('[importlinter]\nroot_package = samplepkg\ninclude_external_packages = True\n'
                      '[importlinter:contract:C-9.4]\nname = C-9.4\ntype = forbidden\n'
                      'source_modules = samplepkg\nforbidden_modules = json\n', encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(repo), str(tmp_path)]),
           'PYTHONDONTWRITEBYTECODE': '1'}
    argv = [sys.executable, '-m', 'tools.run_import_linter', '--config', str(config), '--no-cache']
    clean = subprocess.run(argv, cwd=tmp_path, capture_output=True, text=True, timeout=30, env=env)
    assert clean.returncode == 0 and 'KEPT' in clean.stdout, clean.stdout + clean.stderr
    module.write_text('import json\n', encoding='utf-8')
    broken = subprocess.run(argv, cwd=tmp_path, capture_output=True, text=True, timeout=30, env=env)
    assert broken.returncode != 0 and 'BROKEN' in broken.stdout, broken.stdout + broken.stderr
    assert 'samplepkg' in broken.stdout and 'json' in broken.stdout
