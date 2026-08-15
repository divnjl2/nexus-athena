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
instead of reasoning for 500 and being cut off mid-thought; temperature is 0 so a re-run is
comparable; and every decision carries the pin, so a model swap shows up in the artifact.
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
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lib.judge import Pair, pin, prompt_for, template_fingerprint  # noqa: E402

_JSON = re.compile(r"\{[^{}]*\}", re.DOTALL)


def ask(endpoint: str, model: str, system: str, user: str, *, timeout: int = 180,
        max_tokens: int = 400) -> dict:
    """One judgement. Returns the parsed JSON, or {} when the model produced nothing usable."""
    body = {
        "model": model, "temperature": 0, "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
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
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--variant", default="v2", choices=("v1", "v2"),
                    help="which pinned prompt to measure")
    a = ap.parse_args(argv)

    payload = json.loads(pathlib.Path(a.corpus).read_text(encoding="utf-8"))
    pairs = [Pair(**p) for p in payload["pairs"]]
    if a.limit:
        pairs = pairs[:a.limit]

    def judge(p: Pair) -> tuple[str, dict]:
        system, user = prompt_for(p, variant=a.variant)
        got = ask(a.endpoint, a.model, system, user, timeout=a.timeout)
        if "_error" in got:
            # a failed call is NOT a verdict: it must not read as "the spec is fine"
            return p.id, {"decision": "error", "error": got["_error"]}
        # v1 answers a boolean named `refuted`; v2 answers a categorical `verdict`.
        vacuous = (str(got.get("verdict", "")).lower() == "vacuous" if "verdict" in got
                   else bool(got.get("refuted")))
        return p.id, {"decision": "vacuous" if vacuous else "proves",
                      "counterexample": str(got.get("counterexample", ""))[:300],
                      "reason": str(got.get("reason", ""))[:200]}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        decisions = dict(pool.map(judge, pairs))
    elapsed = time.time() - t0

    # Pin the TEMPLATE, not one pair's rendered prompt: the first cut hashed the system
    # prompt twice and the user template never, so v1 -> v2 (recall 0.056 -> 0.417) left
    # the pin byte-identical — a prompt change the record could not see.
    out = {"schema": "athena.judge_decisions/1",
           "pin": {**pin(model=a.model, prompt=template_fingerprint(a.variant),
                         temperature=0.0), "variant": a.variant},
           "endpoint": a.endpoint, "variant": a.variant, "pairs": len(pairs),
           "seconds": round(elapsed, 1), "decisions": decisions}
    pathlib.Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False,
                                              sort_keys=True) + "\n", encoding="utf-8")
    errs = sum(1 for d in decisions.values() if d["decision"] == "error")
    withce = sum(1 for d in decisions.values()
                 if d["decision"] == "vacuous" and d.get("counterexample", "").strip())
    print(json.dumps({"out": a.out, "pairs": len(pairs), "seconds": round(elapsed, 1),
                      "errors": errs, "refutations_with_counterexample": withce}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
