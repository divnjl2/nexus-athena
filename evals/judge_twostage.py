"""
Drive a LOCAL model over the judge corpus in TWO calls, and keep the reasoning as an artifact.

Why two: the single-call driver ran 9% of the corpus into the context ceiling. Measured on
one such pair, all three variants against the same lane:

    as it was              932s   finish=length   30475 tokens   cut off mid-"Wait, I need"
    frequency_penalty 0.3  454s   finish=stop     14839 tokens   degenerated into rows of dots
    <think> + stop         32s    finish=stop      1067 tokens   closed with a conclusion

So the cure is not a token budget (the operator rule is that the model is not cut, and the
ceiling was cutting it anyway, silently) and not a sampling penalty (it broke the loop by
breaking the language). It is giving the reasoning somewhere to END:

    stage 1   the pinned prompt + "think inside <think></think>", stop=["</think>"]
    stage 2   that analysis handed back as data, and only the JSON shape to fill

vLLM's own `--reasoning-parser` would do the splitting server-side, but this model reasons in
prose and tags nothing on its own, so there is nothing for the parser to split — the tag has
to be asked for. Both prompts are built by `lib.judge`, pinned, so the measurement cannot be
tuned from here.

Stage 2 goes through `instructor` when it is installed: a Pydantic schema plus retry-with-the-
error, which turns an unparseable reply into another attempt instead of a lost pair. Without
it the driver falls back to plain JSON parsing and says so in the record.
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

from lib.judge import (THINK_CLOSE, Pair, judgement_record, looping, pin,  # noqa: E402
                       resume_split, stage1_prompt, stage2_prompt,
                       template_fingerprint)

_JSON = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _post(endpoint: str, body: dict, timeout: int) -> dict:
    req = urllib.request.Request(f"{endpoint}/v1/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def think(endpoint: str, model: str, pair: Pair, *, variant: str, timeout: int,
          detect_loop: bool = True) -> dict:
    """Stage 1: reasoning, stopped at the closing tag — or at a detected LOOP.

    Streamed so the loop can be seen while it happens. The runaway is not long thinking, it
    is repeated thinking, and a pair that cycles holds one of the lane's eight slots for
    twenty minutes producing the same four sentences. Stopping THAT is not a token budget:
    the cut is recorded per pair as `stop_reason`, so it lives in the data instead of being
    the silent truncation the context ceiling was already doing.
    """
    system, user = stage1_prompt(pair, variant=variant)
    body = {"model": model, "temperature": 0, "stop": [THINK_CLOSE], "stream": bool(detect_loop),
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
    if detect_loop:
        # a stream returns no usage block by default, and losing the token count would
        # cost the one number that says whether the reasoning is getting shorter
        body["stream_options"] = {"include_usage": True}
    if not detect_loop:
        try:
            got = _post(endpoint, body, timeout)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as e:
            return {"error": f"{type(e).__name__}: {str(e)[:120]}"}
        ch = got["choices"][0]
        return {"text": ch["message"]["content"] or "", "stop_reason": ch.get("finish_reason"),
                "finish_reason": ch.get("finish_reason"),
                "tokens": got.get("usage", {}).get("completion_tokens")}

    req = urllib.request.Request(f"{endpoint}/v1/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    parts: list[str] = []
    finish, chunks, used = None, 0, None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if ev.get("usage"):
                    used = ev["usage"].get("completion_tokens")
                if not ev.get("choices"):
                    continue
                choice = ev["choices"][0]
                parts.append(choice.get("delta", {}).get("content") or "")
                finish = choice.get("finish_reason") or finish
                chunks += 1
                # checked periodically, not per token: the detector scans a 2.4k tail and
                # doing that on every delta would cost more than the generation it guards
                if chunks % 64 == 0 and looping("".join(parts)):
                    return {"text": "".join(parts), "stop_reason": "loop",
                            "finish_reason": "loop", "tokens": chunks, "chunks": chunks}
    except (urllib.error.URLError, TimeoutError) as e:
        if not parts:
            return {"error": f"{type(e).__name__}: {str(e)[:120]}"}
        finish = finish or "interrupted"
    return {"text": "".join(parts), "stop_reason": finish, "finish_reason": finish,
            "tokens": used if used is not None else chunks, "chunks": chunks}


def _verdict_plain(endpoint: str, model: str, pair: Pair, reasoning: str, *,
                   variant: str, timeout: int) -> dict:
    system, user = stage2_prompt(pair, reasoning, variant=variant)
    body = {"model": model, "temperature": 0, "max_tokens": 300,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
    try:
        got = _post(endpoint, body, timeout)
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as e:
        return {"decision": "error", "error": f"{type(e).__name__}: {str(e)[:120]}"}
    text = got["choices"][0]["message"]["content"] or ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        found = _JSON.findall(text)
        if not found:
            return {"decision": "error", "error": "no json in verdict call"}
        try:
            parsed = json.loads(found[-1])
        except json.JSONDecodeError:
            return {"decision": "error", "error": "unparseable verdict json"}
    vacuous = (str(parsed.get("verdict", "")).lower() == "vacuous" if "verdict" in parsed
               else bool(parsed.get("refuted")))
    return {"decision": "vacuous" if vacuous else "proves",
            "counterexample": str(parsed.get("counterexample", "")),
            "reason": str(parsed.get("reason", ""))}


def _verdict_instructor(client, model: str, pair: Pair, reasoning: str, *,
                        variant: str, retries: int) -> dict:
    """Stage 2 through instructor: a schema, and a retry that carries the error back."""
    from pydantic import BaseModel, Field

    class Judgement(BaseModel):
        verdict: str = Field(description='either "vacuous" or "proves"')
        counterexample: str = Field(default="", description="a concrete change, or empty")
        reason: str = Field(default="", description="at most 12 words")

    system, user = stage2_prompt(pair, reasoning, variant=variant)
    try:
        got = client.chat.completions.create(
            model=model, temperature=0, max_retries=retries, response_model=Judgement,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
    except Exception as exc:                       # noqa: BLE001 - a failed call is a record
        return {"decision": "error", "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return {"decision": "vacuous" if got.verdict.lower() == "vacuous" else "proves",
            "counterexample": got.counterexample, "reason": got.reason}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="features/contract-layer/judge_corpus.json")
    ap.add_argument("--endpoint", default="http://127.0.0.1:8001")
    ap.add_argument("--model", default="qwen9b-opus")
    ap.add_argument("--out", default="judge_decisions.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--variant", default="v2", choices=("v1", "v2"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--checkpoint", type=int, default=8)
    ap.add_argument("--retries", type=int, default=2,
                    help="instructor re-asks with the validation error (0 disables)")
    ap.add_argument("--no-instructor", dest="instructor", action="store_false", default=True)
    ap.add_argument("--no-loop-guard", dest="detect_loop", action="store_false",
                    default=True,
                    help="do not stop stage 1 on a detected repetition loop")
    a = ap.parse_args(argv)

    payload = json.loads(pathlib.Path(a.corpus).read_text(encoding="utf-8"))
    pairs = [Pair(**p) for p in payload["pairs"]]
    if a.limit:
        pairs = pairs[:a.limit]

    client = None
    if a.instructor:
        try:
            import instructor
            from openai import OpenAI
            client = instructor.from_openai(
                OpenAI(base_url=f"{a.endpoint}/v1", api_key="local"),
                mode=instructor.Mode.JSON)
        except Exception as exc:                   # noqa: BLE001 - fall back, but say so
            print(f"[instructor unavailable: {type(exc).__name__}] plain JSON parsing",
                  flush=True)

    stamp = {**pin(model=a.model, prompt=template_fingerprint(a.variant), temperature=0.0),
             "variant": a.variant, "driver": "twostage",
             "instructor": bool(client), "loop_guard": bool(a.detect_loop)}
    dest = pathlib.Path(a.out)
    previous = json.loads(dest.read_text(encoding="utf-8")) if a.resume and dest.exists() else {}
    todo, decisions = resume_split(tuple(pairs), previous, expected_pin=stamp)
    records: dict = dict((previous.get("records") or {})) if previous else {}
    reasoning_store: dict = dict((previous.get("reasoning") or {})) if previous else {}
    if previous:
        print(f"[resume] {len(decisions)} kept, {len(todo)} to judge", flush=True)

    def one(p: Pair) -> tuple[str, dict, dict, str]:
        first = think(a.endpoint, a.model, p, variant=a.variant, timeout=a.timeout,
                      detect_loop=a.detect_loop)
        if "error" in first:
            return p.id, {"decision": "error", "error": first["error"]}, {}, ""
        text = first["text"]
        if client is not None:
            got = _verdict_instructor(client, a.model, p, text,
                                      variant=a.variant, retries=a.retries)
        else:
            got = _verdict_plain(a.endpoint, a.model, p, text,
                                 variant=a.variant, timeout=a.timeout)
        got["stage1_tokens"] = first.get("tokens")
        got["stage1_finish"] = first.get("finish_reason")
        got["stage1_stop_reason"] = first.get("stop_reason")
        got["stage1_chunks"] = first.get("chunks")
        return p.id, got, judgement_record(p, text, got), text

    def flush(elapsed: float) -> None:
        out = {"schema": "athena.judge_decisions/2", "pin": stamp,
               "endpoint": a.endpoint, "variant": a.variant, "driver": "twostage",
               "pairs": len(pairs), "judged": len(decisions),
               "seconds": round(elapsed, 1), "decisions": decisions,
               "records": records, "reasoning": reasoning_store}
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                       encoding="utf-8")
        tmp.replace(dest)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        futures = [pool.submit(one, p) for p in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            pid, verdict, record, reasoning = fut.result()
            decisions[pid] = verdict
            if record:
                records[pid] = record
                reasoning_store[pid] = reasoning
            if n % a.checkpoint == 0:
                flush(time.time() - t0)
                print(f"[{n}/{len(todo)}] {round(time.time() - t0)}s", flush=True)
    elapsed = time.time() - t0
    flush(elapsed)

    errs = sum(1 for d in decisions.values() if d.get("decision") == "error")
    cut = sum(1 for d in decisions.values() if d.get("stage1_finish") == "length")
    looped = sum(1 for d in decisions.values() if d.get("stage1_stop_reason") == "loop")
    toks = [d["stage1_tokens"] for d in decisions.values() if d.get("stage1_tokens")]
    print(json.dumps({"out": a.out, "pairs": len(pairs), "seconds": round(elapsed, 1),
                      "errors": errs, "stage1_hit_ceiling": cut,
                      "stage1_stopped_on_loop": looped,
                      "stage1_tokens_mean": round(sum(toks) / len(toks)) if toks else 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
