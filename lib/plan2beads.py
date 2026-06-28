"""
Athena plan2beads — DETERMINISTIC compiler: Plan AST -> bd commands (v3+v3.1).

Invariants (do not break):
  * No LLM calls. Pure AST -> commands transformation.
  * Pure core (compile): no I/O, no time, no randomness. Idempotency via existing_keys.
  * Strict deterministic order: document order + explicit sorted() for edges.
  * External keys (athena:<slug>:...) = upsert mechanism over Beads hash-IDs.

v3 additions (active when plan.provenance.spec_version is non-empty):
  * spec-node (kind:spec) — idempotent per spec_version
  * design-node (kind:design) — parent=spec-node, idempotent per design_version
  * epics get parent=design-node (instead of floating)
  * derived-from chain: spec -> design -> epic -> task

v3.1 additions (active when plan.scenarios is non-empty):
  * scenario-node (kind:scenario) per Scenario
  * verifies edge: scenario -> spec-node
  * satisfies edge: task -> scenario (for each Task.verifies entry)
  * CompileError if Task.verifies is non-empty but scenario id not found in plan.scenarios

Backward compat: when provenance.spec_version == "" (v2 plans / tests), spec/design/scenario
nodes are NOT emitted and epic parent is not set — output is identical to v2.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from lib.ast import Plan, Task, Scenario  # noqa: F401

EXTERNAL_KEY_PREFIX = "athena"


class CompileError(ValueError):
    """Compile error (not a warning) — the plan is invalid for the graph."""


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]

    def __str__(self) -> str:
        return " ".join(shlex.quote(a) for a in self.argv)


@dataclass(frozen=True)
class CompileResult:
    commands: tuple[Command, ...]
    epic_keys: tuple[str, ...]
    issue_count: int


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _epic_key(slug: str, phase_key: str) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:{phase_key}"


def _task_key(slug: str, t: Task) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:{t.id}"


def _spec_key(slug: str, spec_version: str) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:spec:{spec_version}"


def _design_key(slug: str, design_version: str) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:design:{design_version}"


def _scenario_key(slug: str, scenario_id: str) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:scenario:{scenario_id}"


def _issue_body(t: Task) -> str:
    lines = [t.title, "", f"success_check: {t.success_check}"]
    if t.files:
        lines.append("files: " + ", ".join(t.files))
    if t.verifies:
        lines.append("verifies: " + ", ".join(t.verifies))
    return "\n".join(lines)


def compile(plan: Plan, *, existing_keys: frozenset[str] = frozenset()) -> CompileResult:
    """
    Pure function: Plan AST (+ set of already-existing external keys) -> deterministic
    list of bd commands. existing_keys empty on first compile; on replan the effectful
    layer fills it so creates/edges already in the graph are skipped (idempotent upsert).

    Idempotency tracks NODE labels only, not edge presence. If a prior run crashed between
    node creates and `bd dep add`, a re-run skips the edge — recover with manual `bd dep add`.
    """
    # --- hard validation ---
    phase_keys = {ph.key for ph in plan.phases}
    if len(phase_keys) != len(plan.phases):
        raise CompileError("duplicate phase key")
    for ph in plan.phases:
        if not ph.tasks:
            raise CompileError(f"phase {ph.key!r} has no tasks — dangling epic")
        for d in ph.depends_on:
            if d not in phase_keys:
                raise CompileError(f"phase {ph.key} depends on missing phase {d}")
        for t in ph.tasks:
            if not t.success_check.strip():
                raise CompileError(f"task {t.id} missing success_check")

    slug = _slugify(plan.title)
    if not slug:
        raise CompileError("plan title produces an empty slug — add alphanumeric characters")

    # v3.1: when scenarios are attached, every Task.verifies ref MUST resolve. When no
    # scenarios are attached (the flat plan.md path), `verifies:` lines are unbound
    # annotations — not validated and not compiled into edges — so a bare front that
    # carries scenario ids still compiles. parse_with_provenance() is what attaches the
    # scenarios and flips this on.
    if plan.scenarios:
        scenario_ids = {s.id for s in plan.scenarios}
        for ph in plan.phases:
            for t in ph.tasks:
                for sid in t.verifies:
                    if sid not in scenario_ids:
                        raise CompileError(
                            f"task {t.id} verifies unknown scenario {sid!r}"
                        )

    use_provenance = bool(plan.provenance.spec_version)

    cmds: list[Command] = []
    epic_keys: list[str] = []
    issue_count = 0

    # --- v3: provenance nodes (spec, design) ---
    spec_key: str | None = None
    design_key: str | None = None

    if use_provenance:
        spec_key = _spec_key(slug, plan.provenance.spec_version)
        if spec_key not in existing_keys:
            cmds.append(Command((
                "bd", "create",
                "--title", f"spec:{plan.provenance.spec_version}",
                "--label", spec_key,
                "--label", EXTERNAL_KEY_PREFIX,
                "--label", "kind:spec",
                "--label", f"athena:spec:{plan.provenance.spec_version}",
            )))

        if plan.provenance.design_version:
            design_key = _design_key(slug, plan.provenance.design_version)
            if design_key not in existing_keys:
                cmds.append(Command((
                    "bd", "create",
                    "--parent", spec_key,
                    # bd inherits parent labels by default; without this the design node
                    # would carry kind:spec too and `bd list --label kind:spec` would
                    # return the whole subtree. Every node carries only its own labels.
                    "--no-inherit-labels",
                    "--title", f"design:{plan.provenance.design_version}",
                    "--label", design_key,
                    "--label", EXTERNAL_KEY_PREFIX,
                    "--label", "kind:design",
                    "--label", f"athena:design:{plan.provenance.design_version}",
                )))

    # --- v3.1: scenario nodes + verifies edges ---
    # Guard also on scenario_version: empty scenario_version would produce malformed
    # "athena:scenario:" label (trailing colon). Scenarios require a pinned version.
    if use_provenance and plan.scenarios and plan.provenance.scenario_version:
        for sc in plan.scenarios:
            skey = _scenario_key(slug, sc.id)
            if skey not in existing_keys:
                cmds.append(Command((
                    "bd", "create",
                    "--title", f"scenario:{sc.id} {sc.requirement_key}",
                    "--label", skey,
                    "--label", EXTERNAL_KEY_PREFIX,
                    "--label", "kind:scenario",
                    "--label", f"athena:scenario:{plan.provenance.scenario_version}",
                    "--description", f"{sc.gwt_text}\n\nrun_cmd: {sc.run_cmd}",
                )))
            # verifies: scenario --[validates]--> spec-node. bd has no labeled "related"
            # command; the native typed edge for "X verifies/validates Y" is
            # `bd dep add <scenario> <spec> --type validates` (verified against bd v1.0.4).
            # skip if both endpoints already exist (idempotent).
            if spec_key is not None and not (skey in existing_keys and spec_key in existing_keys):
                cmds.append(Command((
                    "bd", "dep", "add", skey, spec_key, "--type", "validates",
                )))

    # --- epics + issues, strict document order ---
    epic_parent = design_key or spec_key  # v3: epics under design; v2: no parent

    for ph in plan.phases:
        ekey = _epic_key(slug, ph.key)
        epic_keys.append(ekey)
        if ekey not in existing_keys:
            desc = ph.goal
            if ph.checkpoint:
                desc = f"{ph.goal}\n\ncheckpoint: {ph.checkpoint}"
            create_argv: list[str] = ["bd", "create", "--type", "epic"]
            if epic_parent is not None:
                # provenance mode: epic is parented under design -> suppress label
                # inheritance so kind:design/kind:spec don't leak onto the epic.
                create_argv += ["--parent", epic_parent, "--no-inherit-labels"]
            create_argv += [
                "--title", ph.title,
                "--label", ekey, "--label", EXTERNAL_KEY_PREFIX,
                "--description", desc,
            ]
            cmds.append(Command(tuple(create_argv)))

        for t in ph.tasks:
            issue_count += 1
            tkey = _task_key(slug, t)
            if tkey in existing_keys:
                continue
            argv: list[str] = [
                "bd", "create", "--parent", ekey,
                "--title", f"{t.id} {t.title}",
                "--label", tkey, "--label", EXTERNAL_KEY_PREFIX,
            ]
            if use_provenance:
                # suppress inherited kind:*/version labels from the epic->design->spec chain
                # so kind-based queries stay precise. (v2 path leaves output byte-identical.)
                argv.append("--no-inherit-labels")
            if t.autonomy and t.autonomy != "default":
                argv += ["--label", f"autonomy:{t.autonomy}"]
            argv += ["--description", _issue_body(t)]
            cmds.append(Command(tuple(argv)))

    # --- intra-phase task ordering: sequential (non-[P]) tasks chain ---
    for ph in plan.phases:
        prev_seq: str | None = None
        for t in ph.tasks:
            if t.parallel:
                continue
            tkey = _task_key(slug, t)
            if prev_seq is not None and not (tkey in existing_keys and prev_seq in existing_keys):
                cmds.append(Command(("bd", "dep", "add", tkey, "--blocked-by", prev_seq)))
            prev_seq = tkey

    # --- inter-phase dependency edges (epic level), CANONICAL sorted order ---
    for ph in plan.phases:
        ekey = _epic_key(slug, ph.key)
        for d in sorted(ph.depends_on):
            dkey = _epic_key(slug, d)
            if ekey in existing_keys and dkey in existing_keys:
                continue
            cmds.append(Command(("bd", "dep", "add", ekey, "--blocked-by", dkey)))

    # --- v3.1: satisfies edges: task -> scenario (skip if both endpoints already exist) ---
    if use_provenance and plan.scenarios:
        for ph in plan.phases:
            for t in ph.tasks:
                tkey = _task_key(slug, t)
                for sid in t.verifies:
                    skey = _scenario_key(slug, sid)
                    # satisfies: task --[tracks]--> scenario (bd native typed edge;
                    # task and scenario share no parent-child chain so no hierarchy deadlock).
                    if not (tkey in existing_keys and skey in existing_keys):
                        cmds.append(Command((
                            "bd", "dep", "add", tkey, skey, "--type", "tracks",
                        )))

    return CompileResult(tuple(cmds), tuple(epic_keys), issue_count)
