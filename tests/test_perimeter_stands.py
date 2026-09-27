"""Perimeter layer, C-2: the external world enters as fixtures. Red until lib/stands.py exists."""
from __future__ import annotations

import importlib.util
import pathlib
import socket
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_a_changed_cassette_taints_the_verdict_like_a_spec_edit():
    """C-2.1 — a path under cassettes/ in the diff is a spec artefact: named in spec_touched, the
    verdict not green; a path that merely contains the word is not."""
    from lib.dispatch import verdict
    checks = [{"cmd": "python -m pytest tests/t.py::a -q", "exit": 0, "tail": "1 passed"}]
    before = {"lib/m.py": (1, 1), "features/x/cassettes/github.yaml": (1, 1), "lib/cassettes_reader.py": (1, 1)}
    after = {"lib/m.py": (2, 2), "features/x/cassettes/github.yaml": (2, 2), "lib/cassettes_reader.py": (2, 2)}
    v = verdict(before, after, checks)
    assert v["green"] is False and v["spec_touched"] == ["features/x/cassettes/github.yaml"]
    clean = verdict({"lib/cassettes_reader.py": (1, 1)}, {"lib/cassettes_reader.py": (2, 2)}, checks)
    assert clean["green"] is True and clean["spec_touched"] == []


def test_a_stale_cassette_is_reported_with_its_age():
    """C-2.2 — cassettes older than the freshness are named with their age in days, oldest first;
    fresh ones are not; the report is advisory."""
    from lib.stands import stale_cassettes
    now = 1_800_000_000.0
    day = 86400.0
    entries = [("features/x/cassettes/a.yaml", now - 3 * day), ("features/x/cassettes/b.yaml", now - 40 * day),
               ("features/x/cassettes/c.yaml", now - 100 * day)]
    rep = stale_cassettes(entries, now=now, days=30)
    assert [r["path"].rsplit("/", 1)[-1] for r in rep] == ["c.yaml", "b.yaml"]
    assert rep[0]["age_days"] == 100 and rep[1]["age_days"] == 40
    assert all(r["advisory"] is True for r in rep)
    assert stale_cassettes(entries, now=now, days=365) == [] and stale_cassettes([], now=now, days=1) == []


def test_an_embedded_postgres_serves_a_spec_and_leaves_nothing_behind(tmp_path):
    """C-2.3 — inside the stand a table is created and read back over a loopback URI; after it the
    data directory is gone and the port refuses connections; without the package the spec skips."""
    if importlib.util.find_spec("embedded_postgres") is None:
        pytest.skip("embedded-postgres is not installed: pip install embedded-postgres")
    from lib.stands import postgres_stand
    with postgres_stand(base_dir=tmp_path) as pg:
        assert pg.uri.startswith("postgresql://") and ("127.0.0.1" in pg.uri or "localhost" in pg.uri)
        assert pathlib.Path(pg.pgdata).is_dir()
        pg.sql("create table t(x int); insert into t values (41), (1);")
        out = pg.sql("select sum(x) from t;")
        assert "42" in out
        port, pgdata = pg.port, pathlib.Path(pg.pgdata)
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
    deadline = time.time() + 30
    while pathlib.Path(pgdata).exists() and time.time() < deadline:
        time.sleep(0.5)
    assert not pathlib.Path(pgdata).exists(), "the data directory outlived the stand"
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=2)


def test_a_red_verdict_becomes_a_reproduction_packet_that_asks_for_the_test_not_the_fix():
    """C-2.4 — the packet carries the failing command, its tail and the changed files; asks first
    for a test that passes on the present behaviour, second for its inversion; forbids editing the
    module under test."""
    from lib.stands import repro_packet
    rec = {"task": "T2.1", "executor": "pi-omni9", "green": False, "changed_files": ["lib/refinery.py", "lib/dispatch.py"],
           "red_full": [{"cmd": "python -m pytest tests/test_refinery.py::test_admit -q", "exit": 1,
                         "tail": "E       assert admit(recs, 'T1')['ok'] is True\nE       assert False is True"}],
           "reason": "python -m pytest tests/test_refinery.py::test_admit -q exit 1"}
    text = repro_packet(rec, task="T2.1", test_path="tests/test_repro_T2_1.py")
    assert "python -m pytest tests/test_refinery.py::test_admit -q" in text and "assert False is True" in text
    assert "lib/refinery.py" in text and "lib/dispatch.py" in text and "tests/test_repro_T2_1.py" in text
    low = text.lower()
    assert low.index("passes on the present behaviour") < low.index("invert")
    assert "do not edit" in low or "do not change" in low or "never the fix" in low
    assert "lib/refinery.py" in text[low.index("do not"):] or "module under test" in low


def test_a_reproduction_is_admitted_only_when_it_passes_as_written_and_fails_inverted():
    """C-2.5 — exits (0, 1) admit; (0, 0), (1, 1) and (1, 0) refuse naming which half failed; both
    exits are in the record."""
    from lib.stands import repro_admit
    ok = repro_admit(0, 1)
    assert ok["ok"] is True and ok["exits"] == [0, 1] and "admitted" in ok["reason"]
    both_green = repro_admit(0, 0)
    assert both_green["ok"] is False and "invert" in both_green["reason"].lower()
    both_red = repro_admit(1, 1)
    assert both_red["ok"] is False and "as written" in both_red["reason"].lower() or "present behaviour" in both_red["reason"].lower()
    flipped = repro_admit(1, 0)
    assert flipped["ok"] is False and flipped["exits"] == [1, 0]
