// seamModel.js — map real SeamRecords (one run) → Seam Spine nodes.
// Data reality: 2-state only (passed true/false → pass/fail); no wait/halt/durations
// in HumanEval runs (those are interactive-CRISP / schema-golden — future).

const SEAM_META = {
  "seam.intent": { label: "intent", sub: "Hermes → CRISP" },
  "seam.ast_wellformed": { label: "ast_wellformed", sub: "front → AST" },
  "seam.compile_pure": { label: "compile_pure", sub: "AST → compiler" },
  "seam.master_plan": { label: "master_plan", sub: "compiler → PLAN_RUN" },
  "seam.gate": { label: "gate", sub: "OpenHands → gate" },
};

export function toSpineNodes(seams) {
  return (seams || []).map((s) => {
    const meta = SEAM_META[s.name] || { label: s.name.replace("seam.", ""), sub: `${s.src} → ${s.dst}` };
    return {
      id: s.name,
      label: meta.label,
      sub: meta.sub,
      status: s.passed ? "pass" : "fail",
      record: s,
    };
  });
}

// task_id "HumanEval/5" → archive safe dir "HumanEval_5"
export function taskSafe(taskId) {
  return (taskId || "").replace(/\//g, "_");
}

// which archived file an inspected seam maps to (gate → the solution + test output)
export function artifactFor(seamId) {
  if (seamId === "seam.gate") return ["solution.py", "gate.txt"];
  return [];
}
