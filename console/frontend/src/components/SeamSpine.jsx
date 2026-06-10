// SeamSpine.jsx — the signature, ported from the prototype to an ES module and made
// data-driven over real SeamRecords. Static final-state (no head animation — that's the
// LIVE phase): a vertical signal line, a node per seam, lit teal on pass, a visible
// RUPTURE at the first failed seam, magenta glow on halt. Click a node → onSelect.
import React from "react";

const ROW_H = 64;

function headColorFor(st) {
  if (st === "wait") return "var(--sig-wait)";
  if (st === "fail") return "var(--sig-fail)";
  if (st === "halt") return "var(--sig-halt)";
  if (st === "pending") return "var(--ink-40)";
  return "var(--sig-pass)";
}
function lit(st) {
  return st === "pass" || st === "fail" || st === "halt" || st === "wait";
}

function zigzag(cx, y0, y1, amp, step, seed = 0) {
  const pts = [];
  let y = y0, i = 0;
  while (y < y1) {
    const r = Math.sin((i + seed) * 1.7) * 0.5 + Math.sin((i + seed) * 0.6) * 0.5;
    pts.push(`${(cx + r * amp).toFixed(1)},${y.toFixed(1)}`);
    y += step; i++;
  }
  pts.push(`${cx},${y1.toFixed(1)}`);
  return pts.join(" ");
}

function Gutter({ seams, width }) {
  const cx = width / 2;
  const N = seams.length;
  const total = N * ROW_H;
  const nodeY = (i) => i * ROW_H + ROW_H / 2;
  const failIdx = seams.findIndex((s) => s.status === "fail" || s.status === "halt");
  const haltActive = seams.some((s) => s.status === "halt");

  const segs = [];
  for (let i = 0; i < N - 1; i++) {
    const y0 = nodeY(i), y1 = nodeY(i + 1);
    const broken = failIdx >= 0 && i >= failIdx;
    if (broken) {
      const gap = 16;
      segs.push(
        <polyline key={"b" + i} points={`${cx + 5},${y0 + gap} ${cx + 5},${y1}`}
          fill="none" stroke="var(--line)" strokeWidth="1.4" strokeDasharray="2 5" opacity="0.5" />
      );
      if (i === failIdx) {
        segs.push(<line key={"t" + i} x1={cx} y1={y0 + 5} x2={cx - 4} y2={y0 + 11}
          stroke={headColorFor(seams[i].status)} strokeWidth="2" strokeLinecap="round" />);
      }
      continue;
    }
    segs.push(<line key={"base" + i} x1={cx} y1={y0} x2={cx} y2={y1} stroke="var(--line)" strokeWidth="1.4" strokeLinecap="round" />);
    // lit (both endpoints passed)
    if (lit(seams[i].status) && lit(seams[i + 1].status) && seams[i].status === "pass") {
      const col = haltActive ? "var(--sig-halt)" : "var(--sig-pass)";
      segs.push(
        <polyline key={"lit" + i} points={zigzag(cx, y0, y1, 5, 7, i)} fill="none" stroke={col}
          strokeWidth="2" strokeLinejoin="round" opacity="0.95" style={{ filter: `drop-shadow(0 0 4px ${col})` }} />
      );
    }
  }

  const nodes = seams.map((s, i) => {
    const col = headColorFor(s.status);
    const on = lit(s.status);
    const y = nodeY(i);
    return (
      <g key={s.id}>
        <circle cx={cx} cy={y} r="4.5" fill={on ? col : "var(--ink)"} stroke={on ? col : "var(--line)"}
          strokeWidth="1.6" style={on ? { filter: `drop-shadow(0 0 5px ${col})` } : null} />
      </g>
    );
  });

  return (
    <svg width={width} height={total} viewBox={`0 0 ${width} ${total}`}
      style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }} aria-hidden="true">
      {haltActive && (
        <line x1={cx} y1={nodeY(0)} x2={cx} y2={total - ROW_H / 2} stroke="var(--sig-halt)" strokeWidth="8" opacity="0.18" />
      )}
      {segs}
      {nodes}
    </svg>
  );
}

export default function SeamSpine({ seams, selected, onSelect, width = 220 }) {
  return (
    <div style={{ position: "relative" }}>
      <Gutter seams={seams} width={48} />
      <div>
        {seams.map((s) => {
          const col = headColorFor(s.status);
          const sel = selected === s.id;
          return (
            <div key={s.id} onClick={() => onSelect && onSelect(s.id)}
              style={{
                height: ROW_H, paddingLeft: 56, display: "flex", flexDirection: "column", justifyContent: "center",
                cursor: "pointer", borderRadius: 4,
                background: sel ? "var(--panel)" : "transparent",
                boxShadow: sel ? "inset 2px 0 0 " + col : "none",
              }}>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: lit(s.status) ? "var(--ink-100)" : "var(--ink-60)" }}>
                {s.label}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-60)" }}>
                {s.sub} <span style={{ color: col }}>· {s.status}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export { headColorFor };
