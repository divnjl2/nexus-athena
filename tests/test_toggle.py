import os
import pathlib

from lib.frontend import parse_source, speckit_enabled
from lib.plan2beads import compile

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_toggle_speckit_on_parses_tasks():
    res = compile(parse_source(str(FIX / "speckit_tasks.md"), speckit=True))
    assert res.issue_count == 6
    assert len(res.epic_keys) == 4


def test_toggle_speckit_off_parses_plan():
    res = compile(parse_source(str(FIX / "valid.md"), speckit=False))
    assert res.issue_count == 2
    assert len(res.epic_keys) == 2


def test_toggle_both_paths_same_compiler_contract():
    # both fronts produce a Plan AST the SAME compiler consumes; every issue carries
    # a success_check in its body (invariant §1/§6)
    on = compile(parse_source(str(FIX / "speckit_tasks.md"), speckit=True))
    off = compile(parse_source(str(FIX / "valid.md"), speckit=False))
    for res in (on, off):
        cmds = [str(c) for c in res.commands]
        issues = [s for s in cmds if s.split()[:2] == ["bd", "create"] and "--parent" in s]
        assert issues
        assert all("success_check:" in s for s in issues)


def test_toggle_env_default_is_on():
    old = os.environ.pop("ATHENA_SPECKIT", None)
    try:
        assert speckit_enabled() is True
    finally:
        if old is not None:
            os.environ["ATHENA_SPECKIT"] = old


def test_toggle_env_off():
    old = os.environ.get("ATHENA_SPECKIT")
    os.environ["ATHENA_SPECKIT"] = "off"
    try:
        assert speckit_enabled() is False
    finally:
        if old is None:
            os.environ.pop("ATHENA_SPECKIT", None)
        else:
            os.environ["ATHENA_SPECKIT"] = old
