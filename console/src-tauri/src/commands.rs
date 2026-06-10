// commands.rs — the read-mostly "ручки": parse the seam JSONL + archive that the
// Athena pipe writes (lib/seams.py SeamRecord.to_json + batch archive layout).
// Pure file reads via std::fs — no Python import, no fs-plugin; files are the contract.
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

#[derive(Serialize, Deserialize, Clone)]
pub struct SeamRecord {
    pub name: String,
    pub passed: bool,
    #[serde(default)]
    pub issues: Vec<String>,
    #[serde(default)]
    pub hash: String,
    #[serde(default)]
    pub src: String,
    #[serde(default)]
    pub dst: String,
    #[serde(default)]
    pub ts: String,
    #[serde(default)]
    pub context: serde_json::Value,
    #[serde(default)]
    pub run_id: String,
    #[serde(default)]
    pub span_id: String,
    #[serde(default)]
    pub parent_span_id: String,
    #[serde(default)]
    pub ts_ns: i64,
    #[serde(default)]
    pub ts_ns_end: i64,
}

fn read_jsonl(path: &str) -> Result<Vec<SeamRecord>, String> {
    let txt = fs::read_to_string(path).map_err(|e| format!("read {}: {}", path, e))?;
    let mut out = Vec::new();
    for line in txt.lines() {
        let l = line.trim();
        if l.is_empty() {
            continue;
        }
        if let Ok(r) = serde_json::from_str::<SeamRecord>(l) {
            out.push(r); // skip malformed / partially-written lines (live tail)
        }
    }
    Ok(out)
}

/// All seam records (optionally for one run_id).
#[tauri::command]
pub fn read_seams(path: String, run_id: Option<String>) -> Result<Vec<SeamRecord>, String> {
    let mut recs = read_jsonl(&path)?;
    if let Some(rid) = run_id {
        recs.retain(|r| r.run_id == rid);
    }
    Ok(recs)
}

#[derive(Serialize)]
pub struct Run {
    pub id: String,          // run_id
    pub task: String,        // task_id (e.g. HumanEval/5) from results.jsonl, else run_id short
    pub intent: String,      // entry_point / intent
    pub state: String,       // done | fail | running
    pub reached: String,     // last seam name
    pub nseams: usize,
    pub passed_count: usize,
    pub seconds: f64,
}

/// Group seam records by run_id → run cards. `results_path` (optional) enriches
/// each run with task_id / entry_point / seconds from the batch results.jsonl.
#[tauri::command]
pub fn list_runs(path: String, results_path: Option<String>) -> Result<Vec<Run>, String> {
    let recs = read_jsonl(&path)?;
    let mut order: Vec<String> = Vec::new();
    let mut groups: BTreeMap<String, Vec<SeamRecord>> = BTreeMap::new();
    for r in recs {
        if !groups.contains_key(&r.run_id) {
            order.push(r.run_id.clone());
        }
        groups.entry(r.run_id.clone()).or_default().push(r);
    }

    // run_id -> (task_id, entry_point, seconds) from results.jsonl, if provided
    let mut meta: BTreeMap<String, (String, String, f64)> = BTreeMap::new();
    if let Some(rp) = results_path {
        if let Ok(txt) = fs::read_to_string(&rp) {
            for line in txt.lines() {
                if let Ok(v) = serde_json::from_str::<serde_json::Value>(line.trim()) {
                    if let Some(rid) = v.get("run_id").and_then(|x| x.as_str()) {
                        meta.insert(
                            rid.to_string(),
                            (
                                v.get("task_id").and_then(|x| x.as_str()).unwrap_or("").to_string(),
                                v.get("entry_point").and_then(|x| x.as_str()).unwrap_or("").to_string(),
                                v.get("seconds").and_then(|x| x.as_f64()).unwrap_or(0.0),
                            ),
                        );
                    }
                }
            }
        }
    }

    let mut runs = Vec::new();
    for rid in order {
        let ss = &groups[&rid];
        let gate = ss.iter().find(|s| s.name == "seam.gate");
        let state = match gate {
            Some(g) if g.passed => "done",
            Some(_) => "fail",
            None => "running",
        }
        .to_string();
        let reached = ss.last().map(|s| s.name.clone()).unwrap_or_default();
        let (task, entry, seconds) = meta.get(&rid).cloned().unwrap_or_default();
        let short = &rid[..rid.len().min(8)];
        runs.push(Run {
            id: rid.clone(),
            task: if task.is_empty() { format!("run {}", short) } else { task },
            intent: if entry.is_empty() { format!("run {}", short) } else { format!("implement {}", entry) },
            state,
            reached,
            nseams: ss.len(),
            passed_count: ss.iter().filter(|s| s.passed).count(),
            seconds,
        });
    }
    Ok(runs)
}

#[derive(Serialize)]
pub struct RunTrace {
    pub run_id: String,
    pub seams: Vec<SeamRecord>,
}

/// The seam waterfall for one run (the Seam Spine nodes).
#[tauri::command]
pub fn run_trace(path: String, run_id: String) -> Result<RunTrace, String> {
    let seams: Vec<SeamRecord> = read_jsonl(&path)?
        .into_iter()
        .filter(|r| r.run_id == run_id)
        .collect();
    Ok(RunTrace { run_id, seams })
}

/// An archived artifact for a task: solution.py | gate.txt | openhands.log | test_solution.py.
#[tauri::command]
pub fn read_artifact(archive_dir: String, task: String, file: String) -> Result<String, String> {
    // task safe-id e.g. "HumanEval_5"; reject path traversal in `file`.
    if file.contains("..") || file.contains('/') || file.contains('\\') {
        return Err("invalid file name".into());
    }
    let p = Path::new(&archive_dir).join(&task).join(&file);
    fs::read_to_string(&p).map_err(|e| format!("read {:?}: {}", p, e))
}
