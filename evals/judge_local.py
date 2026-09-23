"""
Drive a LOCAL model over the labelled judge corpus and write decisions for `athena judge eval`.

This is the only place in the pilot that talks to a model, and it is deliberately outside
`lib/`: the freeze-line stays model-free. Everything it needs — the prompt, the labels, the
thresholds — comes from `lib.judge`, so the measurement cannot be tuned by editing the driver.

Usage:
    python evals/judge_local.py --corpus features/contract-layer/judge_corpus.json \
        --endpoint http://127.0.0.1:8001 --model qwen9b-opus --out decisions.json [--limit N]

Notes learned on the way, kept because they are the difference between a measurement and a
mess: `response_format={"type":"json_object"}` is what makes this model answer in ~30 tokens
DEFAULT IS UNMUZZLED: no max_tokens, no response_format. Forcing a JSON grammar made this
model answer in ~30 tokens instead of ~500 and measured the grammar rather than the model —
the operator rule this repeatedly violated is in memory/feedback_dont_cap_reasoning_be_patient.
Temperature is 0 so a re-run is comparable; every decision carries the pin.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lib.judge import Pair, pin, prompt_for, resume_split, template_fingerprint  # noqa: E402

_JSON = re.compile(r"\{[^{}]*\}", re.DOTALL)


def ask(endpoint: str, model: str, system: str, user: str, *, timeout: int = 600,
        max_tokens: int = 0, reason: bool = True) -> dict:
    """One judgement. Returns the parsed JSON, or {} when the model produced nothing usable.

    `reason=True` drops the JSON grammar and lets the model think first, then extracts the
    trailing object. Forcing `response_format` makes it answer in ~30 tokens instead of
    ~500 — fast, and possibly at the cost of the very reasoning the task needs. Which of
    those matters more is a measurement, not an opinion, so both modes exist.
    """
    body = {
        "model": model, "temperature": 0,
        # No cap by default and no decoding grammar: this is a reasoning distillate, and
        # both of those muzzle the thinking rather than the answer. Operator rule, broken
        # three times: see memory/feedback_dont_cap_reasoning_be_patient.md. Parse the
        # trailing JSON out of the tail instead.
        **({"max_tokens": max_tokens} if max_tokens else {}),
        **({} if reason else {"response_format": {"type": "json_object"}}),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    req = urllib.request.Request(f"{endpoint}/v1/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = json.load(resp)["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as e:
        return {"_error": f"{type(e).__name__}: {str(e)[:120]}"}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        found = _JSON.findall(text)
        if not found:
            return {"_error": "no json in reply", "_tail": text[-160:]}
        try:
            return json.loads(found[-1])
        except json.JSONDecodeError:
            return {"_error": "unparseable json", "_tail": found[-1][:160]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="features/contract-layer/judge_corpus.json")
    ap.add_argument("--endpoint", default="http://127.0.0.1:8001")
    ap.add_argument("--model", default="qwen9b-opus")
    ap.add_argument("--out", default="judge_decisions.json")
    ap.add_argument("--limit", type=int, default=0, help="first N pairs (0 = all)")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--resume", action="store_true",
                    help="keep the verdicts already in --out that were recorded under this "
                         "exact pin, and judge only the rest")
    ap.add_argument("--checkpoint", type=int, default=20,
                    help="write the partial record every N verdicts")
    ap.add_argument("--muzzle", dest="reason", action="store_false", default=True,
                    help="force a JSON grammar and skip reasoning (measures the grammar, "
                         "not the model — kept only to reproduce the old numbers)")
    ap.add_argument("--variant", default="v2", choices=("v1", "v2"),
                    help="which pinned prompt to measure")
    a = ap.parse_args(argv)

    payload = json.loads(pathlib.Path(a.corpus).read_text(encoding="utf-8"))
    pairs = [Pair(**p) for p in payload["pairs"]]
    if a.limit:
        pairs = pairs[:a.limit]

    def judge(p: Pair) -> tuple[str, dict]:
        system, user = prompt_for(p, variant=a.variant)
        started = time.time()
        got = ask(a.endpoint, a.model, system, user, timeout=a.timeout,
                  reason=a.reason)
        took = round(time.time() - started, 1)
        if "_error" in got:
            # a failed call is NOT a verdict: it must not read as "the spec is fine"
            return p.id, {"decision": "error", "error": got["_error"], "seconds": took}
        # v1 answers a boolean named `refuted`; v2 answers a categorical `verdict`.
        vacuous = (str(got.get("verdict", "")).lower() == "vacuous" if "verdict" in got
                   else bool(got.get("refuted")))
        return p.id, {"decision": "vacuous" if vacuous else "proves",
                      "counterexample": str(got.get("counterexample", ""))[:300],
                      "reason": str(got.get("reason", ""))[:200], "seconds": took}

    # Pin the TEMPLATE, not one pair's rendered prompt: the first cut hashed the system
    # prompt twice and the user template never, so v1 -> v2 (recall 0.056 -> 0.417) left
    # the pin byte-identical — a prompt change the record could not see.
    stamp = {**pin(model=a.model, prompt=template_fingerprint(a.variant),
                   temperature=0.0), "variant": a.variant}
    dest = pathlib.Path(a.out)
    previous = {}
    if a.resume and dest.exists():
        previous = json.loads(dest.read_text(encoding="utf-8"))
    todo, decisions = resume_split(tuple(pairs), previous, expected_pin=stamp)
    if previous:
        print(f"[resume] {len(decisions)} kept, {len(todo)} to judge", flush=True)

    def flush(elapsed: float) -> None:
        out = {"schema": "athena.judge_decisions/1", "pin": stamp,
               "endpoint": a.endpoint, "variant": a.variant, "reason": a.reason,
               "pairs": len(pairs), "judged": len(decisions),
               "seconds": round(elapsed, 1), "decisions": decisions}
        # Write beside the target and replace: a kill during the write must not shred the
        # partial record it is there to protect.
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                       encoding="utf-8")
        tmp.replace(dest)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        # as_completed, NOT `pool.map`: map yields in SUBMISSION order, so one slow pair at
        # the front holds back every verdict behind it. An hour into the first attempt,
        # dozens of pairs were done and the checkpoint file did not exist yet.
        futures = [pool.submit(judge, p) for p in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            pid, verdict = fut.result()
            decisions[pid] = verdict
            # Checkpoint. This run was killed twice at a session boundary with an hour of
            # model time on the floor, because the driver only wrote at the end.
            if n % a.checkpoint == 0:
                flush(time.time() - t0)
                print(f"[{n}/{len(todo)}] {round(time.time() - t0)}s", flush=True)
    elapsed = time.time() - t0
    flush(elapsed)

    errs = sum(1 for d in decisions.values() if d["decision"] == "error")
    withce = sum(1 for d in decisions.values()
                 if d["decision"] == "vacuous" and d.get("counterexample", "").strip())
    print(json.dumps({"out": a.out, "pairs": len(pairs), "seconds": round(elapsed, 1),
                      "errors": errs, "refutations_with_counterexample": withce}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
