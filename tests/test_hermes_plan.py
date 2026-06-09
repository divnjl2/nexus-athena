import json
import pathlib
import re

from lib.ast import Plan, Phase, Task
from lib.plan_parser import parse
from lib.hermes_plan import render_master_plan, _topo_order

FIX = pathlib.Path(__file__).parent / "fixtures"


def _plan() -> Plan:
    return parse((FIX / "valid.md").read_text(encoding="utf-8"))


def test_frontmatter_has_strict_fields():
    md = render_master_plan(_plan(), plan_id="demo", created="2026-06-09")
    assert md.startswith("---")
    assert "plan_id: demo" in md
    assert "owner: divnjl2" in md
    assert "created: 2026-06-09" in md
    assert md.count("---") >= 2          # frontmatter delimiters


def test_tasks_bind_workflow_and_carry_success_check():
    md = render_master_plan(_plan())
    assert "## Tasks" in md
    assert "- [ ] task_id: T1.1" in md
    assert "workflow: ATHENA_TASK" in md
    m = re.search(r"task_id: T1\.1.*?inputs: (\{.*?\})", md, re.S)
    inputs = json.loads(m.group(1))
    assert inputs["success_check"] == "pytest tests/test_health.py -q"
    assert inputs["files"] == "app/routes.py"


def test_topo_order_respects_dependency():
    md = render_master_plan(_plan())          # phase2 depends on phase1
    assert md.index("task_id: T1.1") < md.index("task_id: T2.1")


def test_topo_order_handles_diamond():
    plan = Plan("D", "o", (), (
        Phase("a", "A", "g", tasks=(Task("T1", "x", "true"),)),
        Phase("b", "B", "g", depends_on=("a",), tasks=(Task("T2", "x", "true"),)),
        Phase("c", "C", "g", depends_on=("a",), tasks=(Task("T3", "x", "true"),)),
        Phase("d", "D", "g", depends_on=("b", "c"), tasks=(Task("T4", "x", "true"),)),
    ))
    order = [p.key for p in _topo_order(plan.phases)]
    assert order.index("a") < order.index("b") < order.index("d")
    assert order.index("a") < order.index("c") < order.index("d")


def test_emitted_task_ids_match_plan():
    md = render_master_plan(_plan())
    ids = re.findall(r"^- \[ \] task_id: (\S+)", md, re.M)
    assert set(ids) == {"T1.1", "T2.1"}


def test_render_is_deterministic():
    p = _plan()
    assert render_master_plan(p, created="2026-06-09") == render_master_plan(p, created="2026-06-09")


def test_parallel_marker_emitted():
    plan = Plan("P", "o", (), (
        Phase("phase1", "P", "g", tasks=(Task("T1.1", "a", "true", parallel=True),)),
    ))
    md = render_master_plan(plan)
    assert "[P] parallelizable" in md
