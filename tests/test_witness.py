"""v3.14 the witness — a worker that has gone silent is ended, and the record says "stalled".

Executable spec of C-7.2 in features/executor-layer/contract.md.
"""
from __future__ import annotations

import sys
import time


def test_a_silent_worker_is_ended_by_the_stall_window_and_reported_as_stalled(tmp_path):
    """C-7.2 — a command that emits one event and then nothing for longer than the stall
    window is ended long before its timeout, and the error says stalled, not timed out; a
    command that keeps emitting events inside the window runs to its end."""
    import athena
    silent = {"argv": [sys.executable, "-u", "-c",
                       "import sys,time; print('{\"type\":\"session\"}'); sys.stdout.flush(); time.sleep(40)"],
              "env": {}, "unset": [], "parse": "pi"}
    t0 = time.perf_counter()
    claim, tokens, err = athena._run_command_executor(silent, cwd=tmp_path, timeout=60, stall=2)
    elapsed = time.perf_counter() - t0
    assert elapsed < 25, f"the stall window did not end the worker: {elapsed:.1f}s"
    assert "stalled" in err.lower() and "timed out" not in err.lower()
    assert claim == ""

    chatty = {"argv": [sys.executable, "-u", "-c",
                       "import sys,time\n"
                       "for i in range(6):\n"
                       "    print('{\"type\":\"tick\"}'); sys.stdout.flush(); time.sleep(0.7)\n"
                       "print('{\"type\":\"message_end\",\"message\":{\"role\":\"assistant\","
                       "\"content\":[{\"type\":\"text\",\"text\":\"DONE\"}],\"usage\":{\"input\":3,\"output\":1},"
                       "\"stopReason\":\"stop\"}}')"],
              "env": {}, "unset": [], "parse": "pi"}
    claim, tokens, err = athena._run_command_executor(chatty, cwd=tmp_path, timeout=60, stall=2)
    assert err == "" and claim == "DONE" and tokens == {"input_tokens": 3, "output_tokens": 1}
