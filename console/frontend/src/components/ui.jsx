// ui.jsx — shared instrument atoms (ported from the prototype to ES modules).
import React from "react";
import { headColorFor } from "../lib/model.js";

const ICONS = {
  run: "M5 4.5v15l13-7.5z",
  trace: "M4 6h7M4 12h12M4 18h9",
  gates: "M5 5h14v6a7 7 0 0 1-7 7 7 7 0 0 1-7-7z M9 9l2.2 2.2L15 7.5",
  graph: "M6 7a2 2 0 1 0 0 .01M18 7a2 2 0 1 0 0 .01M12 18a2 2 0 1 0 0 .01M7.5 8.2l3.2 8M16.5 8.2l-3.2 8M8 7h8",
  health: "M3 12h4l2 6 4-14 2 8h6",
  history: "M4 12a8 8 0 1 0 2.3-5.6M4 4v3h3M12 8v4l3 2",
};
export function Icon({ name, size = 18, stroke = "currentColor", sw = 1.6, style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke}
      strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" style={style} aria-hidden="true">
      {ICONS[name].split("M").filter(Boolean).map((d, i) => <path key={i} d={"M" + d} />)}
    </svg>
  );
}

export function Btn({ children, kind = "default", onClick, disabled, full, small, title }) {
  const base = {
    fontFamily: "var(--font-ui)", fontWeight: 550, fontSize: small ? 12 : 13.5, letterSpacing: "0.01em",
    padding: small ? "6px 11px" : "9px 16px", borderRadius: "var(--r-2)", border: "1px solid var(--line)",
    cursor: disabled ? "not-allowed" : "pointer", background: "var(--panel-2)", color: "var(--ink-100)",
    width: full ? "100%" : "auto", transition: "all .14s ease", opacity: disabled ? 0.45 : 1, whiteSpace: "nowrap",
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 7,
  };
  const kinds = {
    primary: { background: "rgba(79,214,201,0.12)", borderColor: "rgba(79,214,201,0.45)", color: "#7df0e5" },
    danger: { background: "rgba(229,86,75,0.10)", borderColor: "rgba(229,86,75,0.4)", color: "#f08178" },
    halt: { background: "rgba(183,104,230,0.12)", borderColor: "rgba(183,104,230,0.5)", color: "#d49bf0" },
    ghost: { background: "transparent", borderColor: "transparent", color: "var(--ink-60)" },
  };
  return (
    <button title={title} onClick={disabled ? undefined : onClick} disabled={disabled} style={{ ...base, ...(kinds[kind] || {}) }}
      onMouseEnter={(e) => { if (!disabled) e.currentTarget.style.filter = "brightness(1.18)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.filter = "none"; }}>
      {children}
    </button>
  );
}

export function Seg({ value, options, onChange, small }) {
  return (
    <div style={{ display: "inline-flex", background: "var(--ink)", border: "1px solid var(--line)", borderRadius: "var(--r-2)", padding: 2, gap: 2 }}>
      {options.map((o) => {
        const active = o.v === value;
        return (
          <button key={o.v} onClick={() => onChange(o.v)} style={{
            fontFamily: "var(--font-ui)", fontSize: small ? 11.5 : 12.5, fontWeight: 540, padding: small ? "4px 9px" : "5px 12px",
            borderRadius: 4, border: "none", cursor: "pointer", background: active ? "var(--panel-2)" : "transparent",
            color: active ? "var(--ink-100)" : "var(--ink-60)", boxShadow: active ? "inset 0 0 0 1px var(--line)" : "none", transition: "all .12s ease",
          }}>{o.label}</button>
        );
      })}
    </div>
  );
}

const STLABEL = { pass: "прошёл", wait: "ждёт", fail: "упал", halt: "halt", run: "идёт", pending: "в очереди" };
export function StatusChip({ status }) {
  const c = headColorFor(status);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5, whiteSpace: "nowrap",
      color: status === "pending" ? "var(--ink-40)" : c, fontWeight: 500 }}>
      <span style={{ width: 7, height: 7, borderRadius: status === "halt" ? 1 : "50%", background: status === "pending" ? "var(--ink-40)" : c,
        boxShadow: status !== "pending" ? "0 0 6px " + c : "none" }} />
      {STLABEL[status] || status}
    </span>
  );
}

// mini spine for run cards: dots per seam, colored by pass/fail; last dot = state
export function SpineThumb({ run }) {
  const n = run.nseams || 5;
  const failed = run.state === "fail";
  return (
    <span style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
      {Array.from({ length: 5 }).map((_, i) => {
        let st = "pending";
        if (i < n) st = "pass";
        if (failed && i === n - 1) st = "fail";
        if (run.state === "running" && i === n - 1) st = "run";
        const c = headColorFor(st);
        const last = i === n - 1;
        return <span key={i} style={{ width: last ? 6 : 4, height: last ? 6 : 4, borderRadius: st === "halt" ? 1 : "50%",
          background: st === "pending" ? "var(--line)" : c, boxShadow: st !== "pending" && last ? "0 0 5px " + c : "none" }} />;
      })}
    </span>
  );
}
