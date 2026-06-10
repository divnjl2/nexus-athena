// SpineGutter.jsx — the signature SVG, ported from the prototype (scope/hairline/conduit
// styles × smooth/discrete/noise motions). Animated head travels down to each seam; node
// pulses on arrival; failed seam shows a visible RUPTURE; halt lights the spine magenta.
import React from "react";
import { headColorFor } from "../lib/model.js";

function energized(st) { return st === "pass" || st === "run" || st === "wait" || st === "fail" || st === "halt"; }

function zigzag(cx, y0, y1, amp, step, seed = 0) {
  const pts = [];
  const dir = y1 >= y0 ? 1 : -1;
  let y = y0, i = 0;
  while ((dir > 0 && y < y1) || (dir < 0 && y > y1)) {
    const r = Math.sin((i + seed) * 1.7) * 0.5 + Math.sin((i + seed) * 0.6) * 0.5;
    pts.push(`${(cx + r * amp).toFixed(1)},${y.toFixed(1)}`);
    y += step * dir; i++;
  }
  pts.push(`${cx},${y1.toFixed(1)}`);
  return pts.join(" ");
}

export default function SpineGutter({ seams, statuses, headPos, headSeamStatus, spineStyle = "scope",
  signalMotion = "smooth", haltActive, selected, rowH = 64, width = 64 }) {
  const cx = width / 2;
  const N = seams.length;
  const total = N * rowH;
  const nodeY = (i) => i * rowH + rowH / 2;
  const reduced = typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let hp = headPos;
  if (signalMotion === "discrete") hp = Math.round(headPos);
  const headY = nodeY(0) + hp * rowH;
  const headColor = headColorFor(headSeamStatus);
  const failIdx = seams.findIndex((s) => statuses[s.id] === "fail" || statuses[s.id] === "halt");

  const isScope = spineStyle === "scope";
  const isConduit = spineStyle === "conduit";
  const baseW = isConduit ? 7 : isScope ? 1.4 : 1.6;
  const litW = isConduit ? 7 : isScope ? 2 : 2.2;

  const segs = [];
  for (let i = 0; i < N - 1; i++) {
    const y0 = nodeY(i), y1 = nodeY(i + 1);
    const broken = failIdx >= 0 && i >= failIdx;
    if (broken) {
      const gap = 16;
      segs.push(<polyline key={"b" + i} points={`${cx + 5},${y0 + gap} ${cx + 5},${y1}`} fill="none"
        stroke="var(--line)" strokeWidth={baseW} strokeDasharray="2 5" opacity="0.5" />);
      if (i === failIdx) {
        segs.push(<line key={"t" + i} x1={cx} y1={y0 + 5} x2={cx - 4} y2={y0 + 11} stroke={headColorFor(statuses[seams[i].id])} strokeWidth="2" strokeLinecap="round" />);
        segs.push(<line key={"t2" + i} x1={cx + 5} y1={y0 + gap} x2={cx + 9} y2={y0 + gap + 5} stroke="var(--line)" strokeWidth="2" strokeLinecap="round" opacity="0.6" />);
      }
      continue;
    }
    segs.push(<line key={"base" + i} x1={cx} y1={y0} x2={cx} y2={y1} stroke="var(--line)" strokeWidth={baseW} strokeLinecap={isConduit ? "butt" : "round"} />);
    const litFrac = Math.max(0, Math.min(1, hp - i));
    if (litFrac > 0) {
      const ly1 = y0 + (y1 - y0) * litFrac;
      const litColor = haltActive ? "#B768E6" : "#4FD6C9";
      if (isScope) {
        segs.push(<polyline key={"lit" + i} points={zigzag(cx, y0, ly1, 5, 7, i)} fill="none" stroke={litColor} strokeWidth={litW} strokeLinejoin="round" opacity="0.95" style={{ filter: "drop-shadow(0 0 4px " + litColor + ")" }} />);
      } else {
        segs.push(<line key={"lit" + i} x1={cx} y1={y0} x2={cx} y2={ly1} stroke={litColor} strokeWidth={litW} strokeLinecap={isConduit ? "butt" : "round"} style={{ filter: "drop-shadow(0 0 5px " + litColor + ")" }} />);
      }
    }
  }

  const nodes = seams.map((s, i) => {
    const st = statuses[s.id] || "pending";
    const col = headColorFor(st);
    const on = energized(st);
    const y = nodeY(i);
    const sel = selected === s.id;
    const arriving = !reduced && st === "run";
    if (isConduit) {
      const sz = 13;
      return (
        <g key={s.id}>
          {s.boundary && <rect x={cx - 13} y={y - 1.5} width="26" height="3" fill={on ? col : "var(--line)"} opacity="0.9" />}
          <rect x={cx - sz / 2} y={y - sz / 2} width={sz} height={sz} rx="2" fill={on ? col : "var(--panel)"} stroke={on ? col : "var(--line)"} strokeWidth="1.5" style={on ? { filter: "drop-shadow(0 0 6px " + col + ")" } : null} />
          {sel && <rect x={cx - sz / 2 - 4} y={y - sz / 2 - 4} width={sz + 8} height={sz + 8} rx="4" fill="none" stroke={col} strokeWidth="1.2" opacity="0.6" />}
          {arriving && <rect x={cx - sz / 2} y={y - sz / 2} width={sz} height={sz} rx="2" fill="none" stroke={col} strokeWidth="2" style={{ transformOrigin: cx + "px " + y + "px", animation: "sig-pulse 1.1s ease-in-out infinite" }} />}
        </g>
      );
    }
    const r = isScope ? 4.5 : 5;
    return (
      <g key={s.id}>
        {isScope && s.boundary && <line x1={cx - 8} y1={y} x2={cx + 8} y2={y} stroke={on ? col : "var(--line)"} strokeWidth="1.4" />}
        {!isScope && s.boundary && <circle cx={cx} cy={y} r="10" fill="none" stroke={on ? col : "var(--line)"} strokeWidth="1" opacity="0.5" />}
        {sel && <circle cx={cx} cy={y} r={r + 5} fill="none" stroke={col} strokeWidth="1.2" opacity="0.6" />}
        <circle cx={cx} cy={y} r={r} fill={on ? col : "var(--ink)"} stroke={on ? col : "var(--line)"} strokeWidth="1.6" style={on ? { filter: "drop-shadow(0 0 5px " + col + ")" } : null} />
        {arriving && <circle cx={cx} cy={y} r={r} fill="none" stroke={col} strokeWidth="2" style={{ transformOrigin: cx + "px " + y + "px", animation: "sig-pulse 1.1s ease-in-out infinite" }} />}
      </g>
    );
  });

  const showHead = headPos < N - 0.001 && headSeamStatus !== "pending" && failIdx < 0;
  const jitter = signalMotion === "noise" && !reduced;

  return (
    <svg width={width} height={total} viewBox={`0 0 ${width} ${total}`} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }} aria-hidden="true">
      {haltActive && <line x1={cx} y1={nodeY(0)} x2={cx} y2={total - rowH / 2} stroke="#B768E6" strokeWidth={baseW + 6} opacity="0.18" style={!reduced ? { animation: "halt-breathe 1.8s ease-in-out infinite" } : null} />}
      {segs}
      {jitter && showHead && (
        <polyline points={zigzag(cx, Math.max(nodeY(0), headY - rowH * 0.8), headY, 6, 6, Math.floor(headPos * 9))} fill="none" stroke={headColor} strokeWidth="1.6" opacity="0.85" />
      )}
      {nodes}
      {showHead && (
        <g style={{ transform: `translateY(${headY - nodeY(0)}px)`, transition: signalMotion === "smooth" && !reduced ? "transform 90ms linear" : "none" }}>
          <circle cx={cx} cy={nodeY(0)} r="7" fill="none" stroke={headColor} strokeWidth="1.5" opacity="0.5" style={!reduced ? { transformOrigin: cx + "px " + nodeY(0) + "px", animation: "sig-pulse 0.9s ease-in-out infinite" } : null} />
          <circle cx={cx + (jitter ? Math.sin(headPos * 40) * 1.5 : 0)} cy={nodeY(0)} r="3.4" fill={headColor} style={{ filter: "drop-shadow(0 0 7px " + headColor + ")" }} />
        </g>
      )}
    </svg>
  );
}
