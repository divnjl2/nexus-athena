// model.js — adapt real SeamRecords (one run) → the prototype's node/status model.
// Our pipeline is 5 seams; map them to frames + human labels + artifacts so the
// faithful Trace/Spine components render real data. 2-state only (pass/fail).

export const FRAMES = {
  crisp: { id: "crisp", label: "CRISP", sub: "Hermes · намерение" },
  build: { id: "build", label: "COMPILE", sub: "AST → master-plan" },
  exec:  { id: "exec",  label: "EXEC", sub: "OpenHands → gate" },
};

// seam.name → node metadata (frame, human label, boundary = first node of a new frame)
export const SEAM_NODE = {
  "seam.intent":         { id: "intent",         frame: "crisp", human: "Намерение принято",       boundary: true,  artifact: "intent" },
  "seam.ast_wellformed": { id: "ast_wellformed", frame: "build", human: "AST корректен",           boundary: true,  artifact: "plan.ast" },
  "seam.compile_pure":   { id: "compile_pure",   frame: "build", human: "Компиляция детерминирована", boundary: false, artifact: "plan.json" },
  "seam.master_plan":    { id: "master_plan",    frame: "build", human: "Master-plan собран",       boundary: false, artifact: "master.md" },
  "seam.gate":           { id: "gate",           frame: "exec",  human: "Гейт — HumanEval-тест",    boundary: true,  artifact: "solution.py" },
};

export function headColorFor(st) {
  if (st === "wait") return "var(--sig-wait)";
  if (st === "fail") return "var(--sig-fail)";
  if (st === "halt") return "var(--sig-halt)";
  if (st === "pending") return "var(--ink-40)";
  return "var(--sig-pass)"; // pass / run
}

export const ROW_H = { compact: 60, context: 74, expanded: 108, rail: 64 };

// SeamRecords (one run, ordered) → prototype node shape
export function runToSeams(records) {
  return (records || []).map((r) => {
    const meta = SEAM_NODE[r.name] || { id: r.name.replace("seam.", ""), frame: "build", human: `${r.src} → ${r.dst}`, boundary: false, artifact: "" };
    return {
      ...meta,
      record: r,
      hash: r.hash || "",
      ctx: 0, // no context% in HumanEval data
      passed: r.passed,
      issues: r.issues || [],
    };
  });
}

// final-state statuses (no animation): pass/fail straight from the record
export function finalStatuses(seams) {
  const m = {};
  seams.forEach((s) => { m[s.id] = s.passed ? "pass" : "fail"; });
  return m;
}

// animated statuses given a head position (0..N): nodes before head = settled,
// node at head = run (or its final pass/fail), nodes after = pending.
export function statusesAt(seams, headPos) {
  const m = {};
  const fail = seams.findIndex((s) => !s.passed);
  seams.forEach((s, i) => {
    if (fail >= 0 && i >= fail && headPos >= fail) {
      m[s.id] = i === fail ? "fail" : "pending";
    } else if (i < headPos - 0.02) {
      m[s.id] = "pass";
    } else if (i <= headPos + 0.5) {
      m[s.id] = headPos >= seams.length - 0.001 ? (s.passed ? "pass" : "fail") : "run";
    } else {
      m[s.id] = "pending";
    }
  });
  return m;
}
