// App.jsx — Athena Console shell (faithful port): titlebar header, Seam-Spine body, nav.
// Read-mostly over the live seam trace via the ручки; on run-select the signal travels
// down the spine (head animation) then settles to the run's real pass/fail final state.
import React from "react";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Seg, Icon } from "./components/ui.jsx";
import { TraceView, RunView, Inspector } from "./components/screens.jsx";
import { runToSeams, statusesAt, finalStatuses, headColorFor } from "./lib/model.js";

const SEAMS_PATH = "D:/tmp/he164_snapshot.jsonl";
const RESULTS_PATH = "D:/tmp/he164_results.jsonl";
const ARCHIVE_DIR = "D:/tmp/he164_archive/archive";
const mono = { fontFamily: "var(--font-mono)" };

const NAV = [
  { v: "run", label: "Run", icon: "run" },
  { v: "trace", label: "Trace", icon: "trace" },
  { v: "gates", label: "Gates", icon: "gates" },
  { v: "graph", label: "Graph", icon: "graph" },
  { v: "health", label: "Health", icon: "health" },
  { v: "history", label: "History", icon: "history" },
];

export default function App() {
  const [runs, setRuns] = React.useState([]);
  const [err, setErr] = React.useState(null);
  const [view, setView] = React.useState("run");
  const [selRun, setSelRun] = React.useState(null);
  const [trace, setTrace] = React.useState([]);
  const [selSeam, setSelSeam] = React.useState(null);
  const [artifacts, setArtifacts] = React.useState({});
  const [headPos, setHeadPos] = React.useState(0);
  const [tweaks, setTweaks] = React.useState({ spineStyle: "scope", signalMotion: "smooth", nodeLayout: "context" });
  const animRef = React.useRef(null);

  React.useEffect(() => {
    invoke("list_runs", { path: SEAMS_PATH, resultsPath: RESULTS_PATH }).then(setRuns).catch((e) => setErr(String(e)));
    return () => clearInterval(animRef.current);
  }, []);

  function animate(n) {
    clearInterval(animRef.current);
    let hp = 0; setHeadPos(0);
    animRef.current = setInterval(() => {
      hp = Math.min(n, hp + 0.07);
      setHeadPos(hp);
      if (hp >= n - 0.001) clearInterval(animRef.current);
    }, 90);
  }

  function openRun(r) {
    setSelRun(r); setSelSeam(null); setArtifacts({}); setView("trace");
    invoke("run_trace", { path: SEAMS_PATH, runId: r.id }).then((t) => {
      setTrace(t.seams); animate(t.seams.length);
    }).catch((e) => setErr(String(e)));
  }

  const seams = runToSeams(trace);
  const statuses = headPos >= seams.length - 0.001 ? finalStatuses(seams) : statusesAt(seams, headPos);
  const headSeam = seams[Math.min(seams.length - 1, Math.round(headPos))];
  const headSeamStatus = headSeam ? statuses[headSeam.id] : "pending";
  const haltActive = false;

  function selectSeam(id) {
    const node = seams.find((s) => s.id === id) || null;
    setSelSeam(node); setArtifacts({});
    if (node && selRun && id === "gate") {
      ["solution.py", "gate.txt"].forEach((f) =>
        invoke("read_artifact", { archiveDir: ARCHIVE_DIR, task: (selRun.task || "").replace(/\//g, "_"), file: f })
          .then((body) => setArtifacts((a) => ({ ...a, [f]: body })))
          .catch(() => setArtifacts((a) => ({ ...a, [f]: "(artifact not mirrored)" }))));
    }
  }

  const win = getCurrentWindow();
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--ink)", color: "var(--ink-100)", overflow: "hidden" }}>
      {/* header / titlebar */}
      <header data-tauri-drag-region style={{ display: "flex", alignItems: "center", gap: 16, height: 48, padding: "0 14px", borderBottom: "1px solid var(--line)", background: "var(--panel)", flexShrink: 0 }}>
        <span className="display" style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.14em" }}>ATHENA</span>
        <span style={{ color: "var(--line)" }}>·</span>
        <span className="mono" style={{ fontSize: 12.5, color: selRun ? "#5fe3d6" : "var(--ink-60)" }}>{selRun ? "run " + selRun.id.slice(0, 8) : "no run"}</span>
        {selRun && <span className="mono" style={{ fontSize: 11.5, color: headColorFor(selRun.state === "done" ? "pass" : selRun.state === "fail" ? "fail" : "run") }}>{selRun.task} · {selRun.state}</span>}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          <Seg small value={tweaks.spineStyle} onChange={(v) => setTweaks((t) => ({ ...t, spineStyle: v }))}
            options={[{ v: "hairline", label: "hairline" }, { v: "scope", label: "scope" }, { v: "conduit", label: "conduit" }]} />
          {selRun && <button onClick={() => animate(seams.length)} title="replay signal" style={{ width: 28, height: 24, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--ink)", border: "1px solid var(--line)", borderRadius: "var(--r-1)", cursor: "pointer", color: "var(--ink-100)" }}>↻</button>}
          <button onClick={() => win.minimize()} style={ctrl}>—</button>
          <button onClick={() => win.close()} style={ctrl}>✕</button>
        </div>
      </header>

      {err && <pre className="mono" style={{ color: "var(--sig-fail)", fontSize: 12, padding: 12, margin: 0 }}>{err}</pre>}

      {/* body */}
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
          {view === "run" && <RunView runs={runs} onOpenRun={openRun} />}
          {view === "trace" && (selRun
            ? <TraceView seams={seams} statuses={statuses} headPos={headPos} headSeamStatus={headSeamStatus} tweaks={tweaks}
                haltActive={haltActive} selected={selSeam && selSeam.id} onSelect={selectSeam} sub={`${selRun.task} · ${selRun.intent}`} />
            : <Empty label="Выбери прогон во вкладке Run." />)}
          {["gates", "graph", "health", "history"].includes(view) && <Empty label={`${view} — следующая фаза (F4-F7)`} />}
        </main>
        {selSeam && <Inspector seam={selSeam} status={statuses[selSeam.id]} artifacts={artifacts} onClose={() => setSelSeam(null)} />}
      </div>

      {/* nav */}
      <nav style={{ display: "flex", alignItems: "center", gap: 2, height: 46, padding: "0 10px", borderTop: "1px solid var(--line)", background: "var(--panel)", flexShrink: 0 }}>
        {NAV.map((n) => {
          const active = view === n.v;
          return (
            <button key={n.v} onClick={() => setView(n.v)} style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "7px 13px", borderRadius: "var(--r-2)", border: "none", cursor: "pointer",
              background: active ? "var(--panel-2)" : "transparent", color: active ? "var(--ink-100)" : "var(--ink-60)", boxShadow: active ? "inset 0 0 0 1px var(--line)" : "none", transition: "all .12s ease" }}>
              <Icon name={n.icon} size={16} stroke={active ? "#5fe3d6" : "var(--ink-60)"} />
              <span style={{ fontSize: 13, fontWeight: active ? 550 : 450 }}>{n.label}</span>
            </button>
          );
        })}
        <span className="mono" style={{ marginLeft: "auto", fontSize: 10.5, color: "var(--ink-40)" }}>{runs.length} runs · live HumanEval trace</span>
      </nav>
    </div>
  );
}

const ctrl = { background: "transparent", border: "1px solid var(--line)", color: "var(--ink-60)", borderRadius: 4, width: 26, height: 22, cursor: "pointer", fontSize: 12 };
function Empty({ label }) {
  return <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--ink-40)", fontSize: 14 }}>{label}</div>;
}
