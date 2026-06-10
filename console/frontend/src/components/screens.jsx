// screens.jsx — ScreenHead, TraceView (spine waterfall), RunView, Inspector. Ported from the
// prototype, fed real run data. Frames mark framework boundaries; the gate rupture reads instantly.
import React from "react";
import SpineGutter from "./SpineGutter.jsx";
import { StatusChip, SpineThumb, Icon } from "./ui.jsx";
import { FRAMES, headColorFor, ROW_H } from "../lib/model.js";

export function ScreenHead({ title, sub, children }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", padding: "20px 24px 14px", borderBottom: "1px solid var(--line)" }}>
      <div>
        <h1 className="display" style={{ margin: 0, fontSize: 22, fontWeight: 600, color: "var(--ink-100)", letterSpacing: "-0.02em" }}>{title}</h1>
        {sub && <div style={{ fontSize: 12.5, color: "var(--ink-60)", marginTop: 3 }}>{sub}</div>}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>{children}</div>
    </div>
  );
}

function TraceRow({ seam, status, rowH, gutter, selected, onSelect, newFrame }) {
  const c = headColorFor(status);
  const reached = status !== "pending";
  const onKey = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(seam.id); } };
  return (
    <div role="button" tabIndex={0} onClick={() => onSelect(seam.id)} onKeyDown={onKey}
      style={{ height: rowH, paddingLeft: gutter + 14, paddingRight: 20, display: "flex", alignItems: "center", gap: 14, cursor: "pointer", position: "relative",
        background: selected ? "linear-gradient(90deg, rgba(79,214,201,0.05), transparent 60%)" : "transparent", borderTop: newFrame ? "1px solid var(--line-soft)" : "none" }}
      onMouseEnter={(e) => { if (!selected) e.currentTarget.style.background = "rgba(255,255,255,0.012)"; }}
      onMouseLeave={(e) => { if (!selected) e.currentTarget.style.background = "transparent"; }}>
      {newFrame && (
        <span className="mono" style={{ position: "absolute", left: gutter + 14, top: 6, fontSize: 9, letterSpacing: "0.1em", color: reached ? c : "var(--ink-40)", opacity: 0.8 }}>
          ┌ {FRAMES[seam.frame].label}
        </span>
      )}
      <div style={{ flex: 1, minWidth: 0, marginTop: newFrame ? 10 : 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span className="mono" style={{ fontSize: 13.5, fontWeight: 500, color: reached ? "var(--ink-100)" : "var(--ink-40)" }}>{seam.id}</span>
          <span style={{ fontSize: 12.5, color: reached ? "var(--ink-60)" : "var(--ink-40)", whiteSpace: "nowrap" }}>{seam.human}</span>
        </div>
        <div style={{ marginTop: 5, display: "flex", gap: 14 }}>
          <span className="mono" style={{ fontSize: 11, color: reached ? "var(--ink-60)" : "var(--ink-40)" }}>{seam.artifact}{seam.hash ? " · #" + seam.hash : ""}</span>
          <span style={{ fontSize: 11, color: status === "fail" ? "var(--sig-fail)" : "var(--ink-60)" }}>
            {status === "fail" ? (seam.issues[0] || "не прошёл") : reached ? "прошёл" : "ожидает"}
          </span>
        </div>
      </div>
      <StatusChip status={status} />
    </div>
  );
}

export function TraceView({ seams, statuses, headPos, headSeamStatus, tweaks, haltActive, selected, onSelect, sub }) {
  const rowH = ROW_H[tweaks.nodeLayout] || 74;
  const W = 64;
  const passed = seams.filter((s) => statuses[s.id] === "pass").length;
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <ScreenHead title="Trace" sub={sub || "поток швов через границы фреймов"}>
        <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-60)" }}>{passed}/{seams.length} прошло</span>
      </ScreenHead>
      <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden", padding: "6px 0 40px" }}>
        <div style={{ position: "relative" }}>
          <div style={{ position: "absolute", left: 18, top: 6, width: W }}>
            <SpineGutter seams={seams} statuses={statuses} headPos={headPos} headSeamStatus={headSeamStatus}
              spineStyle={tweaks.spineStyle} signalMotion={tweaks.signalMotion} haltActive={haltActive} selected={selected} rowH={rowH} width={W} />
          </div>
          <div style={{ paddingTop: 6 }}>
            {seams.map((s, i) => (
              <TraceRow key={s.id} seam={s} status={statuses[s.id] || "pending"} rowH={rowH} gutter={18 + W}
                selected={selected === s.id} onSelect={onSelect} newFrame={i === 0 || s.frame !== seams[i - 1].frame} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function RunView({ runs, onOpenRun }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <ScreenHead title="Run" sub="живой HumanEval-прогон через пайп Athena" >
        <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-60)" }}>{runs.length} прогонов</span>
      </ScreenHead>
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px 40px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {runs.map((r) => (
            <button key={r.id} onClick={() => onOpenRun(r)} style={{ display: "flex", alignItems: "center", gap: 16, textAlign: "left", cursor: "pointer",
              background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "var(--r-3)", padding: "13px 16px", transition: "border-color .14s ease", animation: "fade-up .25s ease both" }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--ink-40)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--line)")}>
              <span className="mono" style={{ fontSize: 12.5, color: "var(--ink-100)", minWidth: 96 }}>{r.task}</span>
              <span style={{ flex: 1, fontSize: 13, color: "var(--ink-60)", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.intent}</span>
              <SpineThumb run={r} />
              <span style={{ fontSize: 11, color: headColorFor(r.state === "done" ? "pass" : r.state === "fail" ? "fail" : "run") }}>{r.state}</span>
              {r.seconds ? <span className="mono" style={{ fontSize: 11, color: "var(--ink-40)", minWidth: 44, textAlign: "right" }}>{r.seconds.toFixed(0)}s</span> : null}
              <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-40)" }}>{r.id.slice(0, 6)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function Inspector({ seam, status, artifacts, onClose }) {
  if (!seam) return null;
  const r = seam.record || {};
  return (
    <div style={{ width: 460, borderLeft: "1px solid var(--line)", background: "var(--panel)", display: "flex", flexDirection: "column",
      animation: "fade-up .2s ease both" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px", borderBottom: "1px solid var(--line)" }}>
        <span className="mono" style={{ fontSize: 14, color: headColorFor(status) }}>{seam.id} <span style={{ color: "var(--ink-60)" }}>[{status}]</span></span>
        <button onClick={onClose} style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--ink-60)", borderRadius: 4, width: 24, height: 22, cursor: "pointer" }}>✕</button>
      </div>
      <div style={{ overflowY: "auto", padding: 16 }}>
        <div style={{ fontSize: 12.5, color: "var(--ink-60)" }}>{seam.human}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-60)", marginTop: 8 }}>{seam.artifact}{r.hash ? " · #" + r.hash : ""} · {r.ts || ""}</div>
        {seam.issues && seam.issues.length > 0 && <div className="mono" style={{ fontSize: 12, color: "var(--sig-fail)", marginTop: 8 }}>issues: {seam.issues.join("; ")}</div>}
        {Object.entries(artifacts || {}).map(([name, body]) => (
          <div key={name} style={{ marginTop: 14 }}>
            <div className="mono" style={{ fontSize: 11, color: "var(--ink-60)", marginBottom: 4 }}>{name}</div>
            <pre className="mono" style={{ fontSize: 11.5, color: "var(--ink-100)", background: "var(--ink)", border: "1px solid var(--line)",
              borderRadius: 4, padding: 10, whiteSpace: "pre-wrap", maxHeight: 380, overflow: "auto" }}>{body}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
