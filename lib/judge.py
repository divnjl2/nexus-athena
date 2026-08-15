"""
Athena judge — the PILOT harness for a model over the clause<->spec pair (v3.4).

Everything else in this repo is deterministic on purpose. A model verdict is not: it moves
with the endpoint, the prompt and the temperature, and none of that makes a test go red. So
a judge is only allowed near this system under conditions that are themselves checkable,
and this module is those conditions — not the judge.

  step 0  ADVISORY by construction. `is_gate_eligible` is the only thing that could ever
          promote a judge, and it needs a passing score report to say yes.
  step 1  the labelled corpus is built MECHANICALLY from pairs this repo already proves;
          the ground truth is never produced by a model.
  step 2  thresholds are constants here, fixed BEFORE any judge runs, so the decision to
          wire one is a number and not an impression.
  step 3  a verdict without an EXECUTABLE counterexample is discarded. The model proposes;
          `adjudicate` runs the counterexample and the runner decides.
  step 4  `pin` records model id + prompt hash + temperature, so swapping the model is
          drift in the ledger rather than silence.
  step 6  `agreement` scores the judge against the deterministic mutation runner on the
          pairs where both apply — the trust metric that can demote it automatically.
  step 7  `sanitize` treats clause text as untrusted input: it is data in a prompt, and a
          contributor can write "approve this" into a note.

`build_corpus`, `degrade`, `score`, `agreement`, `sanitize`, `pin` are PURE.
`adjudicate` is the only effectful one and takes an injected runner.
"""
from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, replace

#: Fixed before any judge exists (step 2). A judge below these numbers stays advisory.
THRESHOLDS = {"recall_min": 0.95, "false_reject_max": 0.02}

#: The mechanical ways a spec stops proving its clause while still exiting 0.
DEFECTS = ("assert_true", "no_assert", "misbound", "weakened")

_INSTRUCTION_MARKERS = (
    "ignore previous", "ignore all previous", "disregard", "system:", "assistant:",
    "you are ", "approve this", "output only", "respond with", "new instructions",
)


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Pair:
    """One clause and one spec, with a label that no model produced."""
    id: str
    clause_id: str
    clause_text: str
    spec_id: str
    spec_source: str
    label: str            # "proves" | "vacuous"
    defect: str = ""      # which mechanical degradation, empty for the good half


def spec_function(source: str, name: str) -> str:
    """PURE: pull one test function's source out of a test module, by name."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    return ""


def degrade(pair: Pair, defect: str, *, other_clause: str = "") -> Pair:
    """PURE: break a proving pair in one named way. Deterministic, no model, no cleverness.

    Each defect is a real failure seen in the wild, not a strawman:
      assert_true  the spec runs the code and asserts nothing that could fail
      no_assert    every assertion removed; exit 0 means "it did not crash"
      weakened     assertions relaxed to `is not None` — passes, proves almost nothing
      misbound     the spec is fine, but it is bound to the WRONG clause
    """
    if defect == "misbound":
        return replace(pair, id=f"{pair.id}#misbound", clause_id=other_clause or pair.clause_id,
                       clause_text="", label="vacuous", defect=defect)
    body = pair.spec_source
    if defect == "assert_true":
        body = re.sub(r"^(\s*)assert .*$", r"\1assert True", body, flags=re.MULTILINE)
    elif defect == "no_assert":
        body = "\n".join(ln for ln in body.splitlines()
                         if not ln.strip().startswith("assert "))
    elif defect == "weakened":
        body = re.sub(r"^(\s*)assert (\w+).*$", r"\1assert \2 is not None", body,
                      flags=re.MULTILINE)
    else:
        raise ValueError(f"unknown defect: {defect}")
    return replace(pair, id=f"{pair.id}#{defect}", spec_source=body, label="vacuous",
                   defect=defect)


def build_corpus(pairs: tuple[Pair, ...], *, defects: tuple[str, ...] = DEFECTS) -> tuple[Pair, ...]:
    """PURE: the labelled set — every proving pair plus one degradation of each kind.

    Balance is deliberate but the labels are not a judgement call: the good half is what the
    repo's own gates already prove, and the bad half is a mechanical edit of it.
    """
    out: list[Pair] = []
    ids = [p.clause_id for p in pairs]
    for i, p in enumerate(pairs):
        out.append(p)
        for d in defects:
            other = ids[(i + 1) % len(ids)] if len(ids) > 1 else ""
            # No DIFFERENT clause to bind to means no misbinding: emitting one anyway would
            # put a "vacuous" label on a pair that is not broken, and poison the ground truth.
            if d == "misbound" and (not other or other == p.clause_id):
                continue
            try:
                out.append(degrade(p, d, other_clause=other))
            except ValueError:
                continue
    return tuple(out)


def sanitize(text: str, *, limit: int = 2000) -> str:
    """PURE (step 7): clause text is DATA in a prompt, never instructions.

    A contributor — or an agent writing clauses — can put "approve this" in a note. The
    markers are neutralised rather than dropped, so the reviewer can still see the attempt.
    """
    cleaned = text[:limit]
    for marker in _INSTRUCTION_MARKERS:
        cleaned = re.sub(re.escape(marker), "[neutralised]", cleaned, flags=re.IGNORECASE)
    return cleaned.replace("```", "'''")


@dataclass(frozen=True)
class Verdict:
    """What a judge is allowed to return: a refutation ATTEMPT, with a way to check it."""
    pair_id: str
    refuted: bool
    counterexample: str = ""      # an executable command; a verdict without one is discarded
    reason: str = ""


def adjudicate(verdict: Verdict, *, runner) -> dict:
    """EFFECTFUL (step 3): the runner decides, not the model.

    A judge that claims a spec is vacuous must hand over something runnable that shows it.
    `runner(cmd) -> int`; the refutation stands only if the counterexample actually runs and
    the spec fails to notice (exit 0 on broken code).
    """
    if not verdict.refuted:
        return {"pair": verdict.pair_id, "decision": "proves", "checked": False,
                "reason": verdict.reason}
    if not verdict.counterexample.strip():
        # an opinion without an artifact is not evidence, and is not allowed to reject
        return {"pair": verdict.pair_id, "decision": "discarded", "checked": False,
                "reason": "refutation carried no executable counterexample"}
    code = runner(verdict.counterexample)
    return {"pair": verdict.pair_id,
            "decision": "vacuous" if code == 0 else "proves",
            "checked": True, "exit_code": code,
            "counterexample": verdict.counterexample, "reason": verdict.reason}


def score(corpus: tuple[Pair, ...], decisions: dict, *,
          thresholds: dict | None = None) -> dict:
    """PURE (step 2): recall on the broken half, false rejects on the good half.

    A pair with no decision counts as "proves" — silence must never be read as a catch.
    """
    th = {**THRESHOLDS, **(thresholds or {})}
    vacuous = [p for p in corpus if p.label == "vacuous"]
    proves = [p for p in corpus if p.label == "proves"]
    caught = [p for p in vacuous if decisions.get(p.id, {}).get("decision") == "vacuous"]
    rejected = [p for p in proves if decisions.get(p.id, {}).get("decision") == "vacuous"]
    discarded = [pid for pid, d in decisions.items() if d.get("decision") == "discarded"]

    recall = round(len(caught) / len(vacuous), 4) if vacuous else 0.0
    false_reject = round(len(rejected) / len(proves), 4) if proves else 0.0
    per_defect = {d: round(
        sum(1 for p in vacuous if p.defect == d
            and decisions.get(p.id, {}).get("decision") == "vacuous")
        / max(1, sum(1 for p in vacuous if p.defect == d)), 4) for d in DEFECTS}
    return {
        "pairs": len(corpus), "vacuous": len(vacuous), "proves": len(proves),
        "recall": recall, "false_reject": false_reject,
        "recall_by_defect": per_defect,
        "discarded_verdicts": len(discarded),
        "thresholds": th,
        "passes": recall >= th["recall_min"] and false_reject <= th["false_reject_max"],
    }


def is_gate_eligible(score_report: dict) -> bool:
    """PURE (step 0): the ONLY door from advisory to gate, and it opens on numbers."""
    return bool(score_report.get("passes"))


def pin(*, model: str, prompt: str, temperature: float) -> dict:
    """PURE (step 4): what must be recorded so a model swap is drift, not silence."""
    return {"model": model, "prompt_sha": _sha16(prompt), "temperature": temperature,
            "thresholds_sha": _sha16(repr(sorted(THRESHOLDS.items())))}


def agreement(decisions: dict, mutation_survivors: dict) -> dict:
    """PURE (step 6): the trust metric — judge against the deterministic runner.

    `mutation_survivors` is {pair_id: bool} from lib.mutation: True when a mutant survived,
    which is the mechanical verdict "this spec proves nothing there". Disagreement in the
    direction "judge says proves, mutation says vacuous" is the dangerous one: the judge is
    granting a green light the deterministic runner refuses.
    """
    common = sorted(set(decisions) & set(mutation_survivors))
    agree = [p for p in common
             if (decisions[p].get("decision") == "vacuous") == bool(mutation_survivors[p])]
    judge_lenient = [p for p in common
                     if mutation_survivors[p] and decisions[p].get("decision") != "vacuous"]
    judge_strict = [p for p in common
                    if not mutation_survivors[p] and decisions[p].get("decision") == "vacuous"]
    return {
        "compared": len(common),
        "agreement": round(len(agree) / len(common), 4) if common else 0.0,
        "judge_lenient": judge_lenient,     # judge greenlights what mutation says is vacuous
        "judge_strict": judge_strict,       # judge rejects what mutation says is proved
        "demote_to_advisory": bool(judge_lenient),
    }
