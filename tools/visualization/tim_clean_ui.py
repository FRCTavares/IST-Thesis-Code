#!/usr/bin/env python3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import argparse
import json
import html as html_lib
import csv
import re
import subprocess
import sys
from pathlib import Path
import uvicorn

# Import the original backend module, then copy its registered API routes.
# This keeps /clean isolated from the broken old HTML page.
import tim_audit_ui as backend

app = FastAPI(title="TIM-MARS Clean UI")

for route in backend.app.routes:
    if getattr(route, "path", "").startswith("/api/") or getattr(route, "path", "") == "/frame.jpg":
        app.router.routes.append(route)



REPO_ROOT = Path(__file__).resolve().parents[2]


def _safe_name(s: str) -> str:
    s = s.strip().replace("/", "__")
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", s)[:180]


@app.post("/api/evaluate")
async def evaluate_api(request: Request):
    payload = await request.json()
    bag = str(payload.get("bag", "")).strip()
    ann = str(payload.get("ann", "")).strip()

    if not bag:
        return {"ok": False, "error": "No bag selected."}
    if not ann:
        return {"ok": False, "error": "No annotation selected."}

    bag_path = Path(bag)
    ann_path = Path(ann)

    if not bag_path.is_absolute():
        bag_path = REPO_ROOT / bag_path
    if not ann_path.is_absolute():
        ann_path = REPO_ROOT / ann_path

    if not bag_path.exists():
        return {"ok": False, "error": f"Bag does not exist: {bag_path}"}
    if not ann_path.exists():
        return {"ok": False, "error": f"Annotation does not exist: {ann_path}"}

    out_dir = (
        REPO_ROOT
        / "reports"
        / "ui_evaluations"
        / (_safe_name(bag_path.name) + "__" + _safe_name(ann_path.stem))
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "analysis" / "evaluate_tim_target_bbox_correctness.py"),
        str(bag_path),
        "--annotations",
        str(ann_path),
        "--out-dir",
        str(out_dir),
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
    )

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": "Evaluator failed.",
            "cmd": " ".join(cmd),
            "log": proc.stdout,
            "out_dir": str(out_dir),
        }

    summary_csv = out_dir / "summary.csv"
    summary_md = out_dir / "summary.md"

    rows = []
    if summary_csv.exists():
        with summary_csv.open(newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)

    markdown = summary_md.read_text() if summary_md.exists() else ""

    return {
        "ok": True,
        "cmd": " ".join(cmd),
        "out_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "summary_md": str(summary_md),
        "rows": rows,
        "markdown": markdown,
        "log": proc.stdout,
    }



ANNOTATION_FIELDS = [
    "bag_name",
    "start_s",
    "end_s",
    "target_label",
    "target_visible",
    "correct_target_track_id",
    "distractor_track_ids",
    "event_type",
    "notes",
]


def _safe_annotation_relpath(path_text: str) -> Path:
    rel = Path(str(path_text).strip())
    if rel.is_absolute():
        raise ValueError("Annotation path must be relative to repository root")
    if ".." in rel.parts:
        raise ValueError("Annotation path cannot contain '..'")
    if rel.suffix.lower() != ".csv":
        raise ValueError("Annotation path must end with .csv")
    if not str(rel).startswith("docs/annotations/"):
        raise ValueError("Annotation path must be under docs/annotations/")
    return rel


@app.post("/api/annotation/load")
async def annotation_load_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    if not path_text:
        return {"ok": False, "error": "No annotation path provided."}

    try:
        rel = _safe_annotation_relpath(path_text)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    path = REPO_ROOT / rel
    if not path.exists():
        return {"ok": False, "error": f"Annotation does not exist: {rel}"}

    rows = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k: row.get(k, "") for k in ANNOTATION_FIELDS}
            rows.append(clean)

    return {"ok": True, "path": str(rel), "rows": rows, "fields": ANNOTATION_FIELDS}


@app.post("/api/annotation/save")
async def annotation_save_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    rows = payload.get("rows", [])

    if not path_text:
        return {"ok": False, "error": "No output annotation path provided."}
    if not isinstance(rows, list):
        return {"ok": False, "error": "Rows must be a list."}

    try:
        rel = _safe_annotation_relpath(path_text)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    out_path = REPO_ROOT / rel
    out_path.parent.mkdir(parents=True, exist_ok=True)

    normalised = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean = {k: str(row.get(k, "")).strip() for k in ANNOTATION_FIELDS}

        try:
            start_s = float(clean["start_s"])
            end_s = float(clean["end_s"])
        except ValueError:
            return {"ok": False, "error": f"Invalid interval times: {clean}"}

        if end_s <= start_s:
            return {"ok": False, "error": f"Invalid interval with end <= start: {clean}"}

        label = clean["target_label"].strip().upper() or "CORRECT_TARGET"
        clean["target_label"] = label

        visible = clean["target_visible"].strip().lower()
        if visible in {"true", "1", "yes", "y"}:
            clean["target_visible"] = "true"
        elif visible in {"false", "0", "no", "n"}:
            clean["target_visible"] = "false"
        else:
            clean["target_visible"] = "true" if label == "CORRECT_TARGET" else "false"

        if label in {"NO_TARGET_SELECTED", "TARGET_NOT_VISIBLE"}:
            clean["target_visible"] = "false"

        normalised.append(clean)

    normalised.sort(key=lambda r: (float(r["start_s"]), float(r["end_s"])))

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(normalised)

    return {
        "ok": True,
        "path": str(rel),
        "rows": len(normalised),
        "message": f"Saved {len(normalised)} annotation intervals to {rel}",
    }



@app.get("/clean", response_class=HTMLResponse)
def clean_ui():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>TIM-MARS Clean UI</title>
  <style>
    body { margin: 0; padding: 18px; background: #111; color: #eee; font-family: Arial, sans-serif; }
    .panel { border: 1px solid #333; border-radius: 8px; padding: 14px; margin-bottom: 12px; background: #151515; }
    select, input, button {
      padding: 8px 10px;
      margin: 4px;
      font-size: 14px;
      border-radius: 6px;
      border: 1px solid #444;
      background: #202020;
      color: #eee;
      outline: none;
    }

    select {
      width: min(1050px, 92vw);
      background: #202020;
      color: #eee;
    }

    input::placeholder {
      color: #777;
    }

    input:focus, select:focus {
      border-color: #777;
      background: #262626;
    }

    button {
      cursor: pointer;
      font-weight: 700;
      background: #2b2b2b;
      color: #f2f2f2;
      border: 1px solid #555;
    }

    button:hover {
      background: #3a3a3a;
      border-color: #777;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.45;
    }
    #selectedPath { color: #aaa; overflow-wrap: anywhere; font-size: 13px; }
    #meta { background: #222; padding: 10px; border-radius: 6px; margin-bottom: 12px; }

    #compareGrid {
      width: min(1500px, 96vw);
      margin: 0 auto;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .videoPane {
      background: #000;
      border: 1px solid #555;
      border-radius: 6px;
      overflow: hidden;
    }
    .videoTitle {
      padding: 8px 10px;
      background: #222;
      font-weight: 700;
      text-align: center;
    }
    .videoPane canvas {
      width: 100%;
      display: block;
      cursor: pointer;
      background: #000;
    }
    #controls {
      width: min(1500px, 96vw);
      margin: 10px auto 0 auto;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px;
      background: #050505;
      border: 1px solid #333;
      border-radius: 6px;
    }
    #progress { flex: 1; }

    #preloadWrap {
      width: 320px;
      height: 16px;
      border: 1px solid #666;
      border-radius: 999px;
      background: #050505;
      overflow: hidden;
      box-shadow: inset 0 0 0 1px #111;
    }

    #preloadBar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #2f80ed, #55c7ff);
      transition: width 0.08s linear;
    }

    #preloadPct {
      min-width: 48px;
      color: #ccc;
      font-size: 13px;
      text-align: right;
    }

    #annotation {
      width: min(1050px, 92vw);
    }

    .hint {
      color: #aaa;
      font-size: 13px;
      margin-top: 6px;
    }

    #evalStatus {
      margin-left: 10px;
      color: #ccc;
      font-weight: 700;
    }

    #evalTable {
      margin-top: 12px;
      overflow-x: auto;
    }

    table.evalTable {
      border-collapse: collapse;
      width: 100%;
      margin-top: 10px;
      font-size: 13px;
    }

    table.evalTable th,
    table.evalTable td {
      border: 1px solid #333;
      padding: 7px 8px;
      text-align: right;
      white-space: nowrap;
    }

    table.evalTable th:first-child,
    table.evalTable td:first-child {
      text-align: left;
    }

    table.evalTable th {
      background: #222;
      color: #eee;
    }

    table.evalTable td {
      background: #111;
    }

    .goodMetric {
      color: #9be28f;
      font-weight: 700;
    }

    .badMetric {
      color: #ff7777;
      font-weight: 700;
    }

    #evalLog {
      white-space: pre-wrap;
      background: #050505;
      padding: 10px;
      margin-top: 10px;
      max-height: 260px;
      overflow: auto;
      border-radius: 6px;
      border: 1px solid #222;
      color: #bbb;
      font-size: 12px;
    }

    #frontendError {
      display: none;
      margin-top: 10px;
      padding: 10px;
      background: #2a0707;
      border: 1px solid #8a3333;
      color: #ffb3b3;
      white-space: pre-wrap;
      font-family: monospace;
      border-radius: 6px;
    }
    details { margin-top: 12px; }
    summary { cursor: pointer; font-weight: 700; font-size: 17px; }
    #log { white-space: pre-wrap; background: #050505; padding: 10px; max-height: 260px; overflow: auto; }
  
.annotationBox, .annRow, .evalCards, #annRows {{
  font-size:24px;
}}

label {{
  font-size:23px;
}}

small {{
  font-size:20px;
}}

select option {{
  font-size:24px;
}}


/* Annotation editor visual cleanup */
#annCsv, #annStart, #annEnd, #annTargetId, #annLabel, #annEvent, #annNotes {{
  background:#242424;
  color:#f0f0f0;
  border:1px solid #666;
  border-radius:6px;
  padding:10px 12px;
  font-size:24px;
}}

#annNotes.notesInput {{
  width:520px;
  max-width:520px;
}}

button {{
  background:#3a3a3a;
  color:#ffffff;
  border:2px solid #888;
  border-radius:8px;
  padding:11px 16px;
  font-size:24px;
  font-weight:700;
  cursor:pointer;
}}

button:hover {{
  background:#4a4a4a;
  border-color:#bbb;
}}

button:active {{
  background:#5a5a5a;
}}

#annCsv {{
  width:520px;
}}

#annStart, #annEnd, #annTargetId {{
  width:150px;
}}

#annLabel, #annEvent {{
  width:330px;
}}



/* TIM annotation editor override v3 */
#annRows {{
  margin-top:14px;
  max-height:380px;
  overflow:auto;
  font-family:Arial, sans-serif;
  font-size:20px;
  border:1px solid #444;
  border-radius:8px;
  background:#101010;
}}

#annRows table {{
  width:100%;
  border-collapse:collapse;
}}

#annRows th {{
  position:sticky;
  top:0;
  background:#242424;
  z-index:1;
  padding:8px;
  border-bottom:1px solid #555;
}}

#annRows td {{
  padding:6px;
  border-bottom:1px solid #2a2a2a;
}}

#annRows input,
#annRows select {{
  width:100%;
  box-sizing:border-box;
  font-size:18px;
  padding:6px 8px;
  margin:0;
}}

#annRows button {{
  font-size:18px;
  padding:6px 10px;
  margin:0;
}}

#annRows tr.active {{
  outline:2px solid #55c7ff;
}}

#annOutPath {{
  width:min(1100px, 90vw);
}}

#annNotes {{
  width:520px !important;
  max-width:520px;
}}

.annDirty {{
  color:#ffd166;
  font-weight:800;
  margin-left:10px;
}}

.annSaved {{
  color:#9be28f;
  font-weight:800;
  margin-left:10px;
}}


/* Make annotation table expand to show all rows. */
#annotationEditor,
#annotationEditor table,
#annotationEditor tbody,
#annRows,
#annTable,
#annTableWrap,
#annotationRows,
#annotationTable,
#annotationTableWrap {
  max-height: none !important;
  height: auto !important;
  overflow-y: visible !important;
}

#annotationEditor {
  overflow: visible !important;
  padding-bottom: 24px;
}

#annotationEditor table {
  width: 100%;
}

#annotationEditor tbody tr {
  height: 46px;
}

#annotationEditor input,
#annotationEditor select {
  min-height: 36px;
}

</style>
</head>
<body>
  <h2>TIM-MARS Clean UI</h2>

  <div class="panel">
    <h3>1. Load bag</h3>
    filter <input id="filter" placeholder="hard, seq03, bytetrack..." oninput="renderBags()">
    <button onclick="loadList()">Refresh</button>
    <br>
    <select id="bag" onchange="showSelected()"></select>
    <div id="selectedPath"></div>

    <div class="hint">annotation, auto-selected from bag + tracker</div>
    <select id="annotation" onchange="showAnnotation()"></select>
    <div id="annotationPath" class="hint"></div>

    <br>
    <button onclick="loadBag()">Load selected bag</button>
    <button onclick="evaluateBag()">Evaluate RAW vs TIM</button>
    <span id="status"></span>
    <span id="evalStatus"></span>
    <div id="frontendError"></div>
  </div>

  <div class="panel">
    <h3>2. Viewer</h3>
    <div id="meta">Load a bag.</div>

    <div id="compareGrid">
      <div class="videoPane">
        <div id="rawTitle" class="videoTitle">RAW selector output /target</div>
        <canvas id="rawCanvas" onclick="togglePlay()"></canvas>
      </div>
      <div class="videoPane">
        <div id="timTitle" class="videoTitle">TIM-MARS output /target_memory_mars</div>
        <canvas id="timCanvas" onclick="togglePlay()"></canvas>
      </div>
    </div>

    <div id="controls">
      <button id="playBtn" onclick="togglePlay()">▶</button>
      <span id="time">0:00 / 0:00</span>
      <input id="progress" type="range" min="0" max="0" value="0" oninput="seek()" disabled>
      <span id="preloadStatus">not loaded</span>
      <div id="preloadWrap"><div id="preloadBar"></div></div>
      <span id="preloadPct">0%</span>
    </div>

    <details open>
      <summary>Overlay options</summary>
      mode
      <select id="viewMode" onchange="reloadViewCache()" style="width:220px">
        <option value="compare">RAW vs TIM-MARS</option>
        <option value="tracks">Tracks only, all IDs</option>
      </select>
      <label><input id="det" type="checkbox" onchange="reloadViewCache()"> detections</label>
      <label><input id="tracks" type="checkbox" onchange="reloadViewCache()"> tracks</label>
      only IDs <input id="ids" value="1,42" oninput="reloadViewCache()">
    </details>
  </div>

  <div class="panel">
    <details open>
      <summary>3. Evaluation result</summary>
      
<div class="annotationBox">
  <h3>Annotation editor</h3>
  <div class="hint">
    Creates evaluator-compatible interval CSVs. Use tracks-only view, scrub to the frame, set interval start/end, then add the correct target ID.
  </div>

  <div class="annotationControls">
    <label>output CSV
      <input id="annOutPath" value="docs/annotations/ui_created/new_annotation.csv">
    </label>
    <label>start s
      <input id="annStart" type="number" step="0.001" value="0.000">
    </label>
    <label>end s
      <input id="annEnd" type="number" step="0.001" value="1.000">
    </label>
    <label>target ID
      <input id="annTargetId" type="number" step="1" value="1">
    </label>
    <label>label
      <select id="annLabel">
        <option value="CORRECT_TARGET">CORRECT_TARGET</option>
        <option value="TARGET_NOT_VISIBLE">TARGET_NOT_VISIBLE</option>
        <option value="NO_TARGET_SELECTED">NO_TARGET_SELECTED</option>
      </select>
    </label>
    <label>event
      <select id="annEvent">
              <option value="manual_interval">manual_interval</option>
              <option value="id_switch">id_switch</option>
              <option value="target_occluded">target_occluded</option>
              <option value="target_exits_frame">target_exits_frame</option>
              <option value="target_reappears">target_reappears</option>
              <option value="uncertain">uncertain</option>
            </select>
    </label>
  </div>

  <label>notes
    <input id="annNotes" style="width:100%" value="created in TIM clean UI">
  </label>

  <div class="annotationButtons">
    <button onclick="annAddInterval()">Add / update interval</button>
    <button onclick="annDeleteActive()">Delete active</button>
    <button onclick="annLoadSelected()">Load selected CSV</button>
    <button onclick="annSave()">Save CSV</button>
  </div>

  <div class="hint" id="annStatus">No annotation rows loaded.</div>
  <div id="annRows"></div>
</div>

<div id="evalTable"></div>
      <div id="evalLog"></div>
    </details>
  </div>

  <div class="panel">
    <details>
      <summary>4. Run TIM-MARS replay</summary>
      target <input id="targetId" value="1" style="width:70px">
      tracker
      <select id="tracker" style="width:130px">
        <option value="bytetrack">bytetrack</option>
        <option value="ocsort">ocsort</option>
        <option value="deepsort">deepsort</option>
      </select>
      rate <input id="rate" value="1.0" style="width:70px">
      <button onclick="runTim()">Run TIM-MARS on selected bag</button>
      <button onclick="loadLast()">Load last output bag</button>
      <div id="log"></div>
    </details>
  </div>

<script>
let allBags = __BAGS_JSON__;
let allAnnotations = __ANNOTATIONS_JSON__;
let loadedFrames = 0;
let loadedDuration = 0;
let loadedBag = "";
let playing = false;
let timer = null;

let rawFrameCache = [];
let timFrameCache = [];
let rawDecodedCache = [];
let timDecodedCache = [];
let preloadReady = false;
let preloadInProgress = false;
let preloadToken = 0;

function label(path) {
  const name = path.split("/").pop();
  const l = path.toLowerCase();
  let p = "bag";
  if (l.includes("/ui_replays/")) p = "ui";
  else if (l.includes("/datasets/")) p = "dataset";
  else if (l.includes("/eval_matrix/")) p = "eval";
  else if (l.includes("/source_video/")) p = "source";
  else if (l.includes("/live_camera/")) p = "live";

  let s = name;
  if (l.includes("hard_reentry")) s = "hard re-entry / ID switch";
  else if (l.includes("two_person_no_crossing")) s = "two-person no crossing";
  else if (l.includes("seq01")) s = "seq01 clean four-person";
  else if (l.includes("seq02")) s = "seq02 target re-entry";
  else if (l.includes("seq03")) s = "seq03 crossing ambiguity";
  else if (l.includes("seq04")) s = "seq04 occlusion / no exit";

  const parts = ["[" + p + "]", s];
  if (l.includes("tracker_bytetrack")) parts.push("ByteTrack");
  if (l.includes("tracker_ocsort")) parts.push("OCSORT");
  if (l.includes("tracker_deepsort")) parts.push("DeepSORT");
  if (l.includes("tim_mars")) parts.push("TIM-MARS");
  if (l.includes("tim_off")) parts.push("TIM off");
  const m = name.match(/target_([0-9]+)/);
  if (m) parts.push("target " + m[1]);
  const r = name.match(/__r([0-9]+)$/);
  if (r) parts.push("r" + r[1]);
  return parts.join(" | ");
}

function fmt(sec) {
  sec = Math.max(0, sec || 0);
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ":" + String(s).padStart(2, "0");
}


function annotationLabel(path) {
  if (!path) return "[none] no annotation";

  const name = path.split("/").pop();
  const l = path.toLowerCase();

  let bits = [];

  if (l.includes("hard_reentry")) bits.push("hard re-entry");
  else if (l.includes("seq01")) bits.push("seq01");
  else if (l.includes("seq02")) bits.push("seq02");
  else if (l.includes("seq03")) bits.push("seq03");
  else if (l.includes("seq04")) bits.push("seq04");
  else bits.push(name);

  if (l.includes("bytetrack")) bits.push("ByteTrack");
  if (l.includes("ocsort")) bits.push("OCSORT");
  if (l.includes("deepsort")) bits.push("DeepSORT");

  if (l.includes("track_time")) bits.push("track-time");
  else if (l.includes("header_time")) bits.push("header-time");
  else if (l.includes("ros_time")) bits.push("ROS-time");
  else bits.push("manual");

  if (l.includes("corrected")) bits.push("corrected");
  if (l.includes("_r1_") || l.endsWith("_r1_header_time_corrected.csv") || l.endsWith("_r1.csv")) bits.push("r1");
  if (l.includes("_r2_") || l.endsWith("_r2_header_time_corrected.csv")) bits.push("r2");

  return bits.join(" | ");
}

function annotationScoreForBag(bag, ann) {
  const b = bag.toLowerCase();
  const a = ann.toLowerCase();
  let s = 0;

  // Hard re-entry, tracker-specific.
  if (b.includes("hard_reentry") && a.includes("hard_reentry")) {
    s += 100;

    if (b.includes("bytetrack") && a.includes("bytetrack")) s += 80;
    if (b.includes("ocsort") && a.includes("ocsort")) s += 80;
    if (b.includes("deepsort") && a.includes("deepsort")) s += 80;

    // Fresh replay corrected annotations are preferred for recent UI replay bags.
    if (a.includes("fresh_replay_corrected")) s += 50;
    if (a.includes("corrected")) s += 40;
    if (a.includes("header_time")) s += 30;

    // Prefer the corrected annotation that uses target_label=CORRECT_TARGET.
    // This is more important than matching the replay suffix.
    if (b.includes("bytetrack") && a.includes("_r2_") && a.includes("corrected")) s += 60;

    // r1 corrected uses black_shirt labels, which can break reference/evaluation logic.
    if (b.includes("bytetrack") && a.includes("_r1_") && a.includes("corrected")) s -= 40;

    // Match replay suffix only as a weak tie-breaker.
    if (b.includes("__r1") && a.includes("_r1_")) s += 5;
    if (b.includes("__r2") && a.includes("_r2_")) s += 5;

    return s;
  }

  // Official field sequences, prefer manual_track_time.
  for (const seq of ["seq01", "seq02", "seq03", "seq04"]) {
    if (b.includes(seq) && a.includes(seq)) {
      s += 100;
      if (a.includes("manual_track_time")) s += 80;
      else if (a.includes("manual_ros_time")) s += 20;
      else if (a.includes("target_id_only")) s -= 50;
      else if (a.endsWith("_manual.csv")) s += 10;
      return s;
    }
  }

  return s;
}

function renderAnnotationsForBag(bag) {
  const sel = document.getElementById("annotation");
  if (!sel) return;

  sel.innerHTML = "";

  const none = document.createElement("option");
  none.value = "";
  none.text = "[none] no annotation";
  sel.add(none);

  const scored = allAnnotations
    .map(a => ({path: a, score: annotationScoreForBag(bag || "", a)}))
    .filter(x => x.score > 0)
    .sort((x, y) => y.score - x.score || x.path.localeCompare(y.path));

  for (const item of scored) {
    const o = document.createElement("option");
    o.value = item.path;
    o.text = annotationLabel(item.path);
    o.title = item.path;
    sel.add(o);
  }

  if (scored.length > 0) {
    sel.value = scored[0].path;
  }

  showAnnotation();
}

function selectedAnnotation() {
  const el = document.getElementById("annotation");
  return el ? (el.value || "") : "";
}

function showAnnotation() {
  const el = document.getElementById("annotationPath");
  if (!el) return;
  const ann = selectedAnnotation();
  el.innerText = ann ? ann : "No annotation selected.";
}

function setPreloadProgress(done, total) {
  const bar = document.getElementById("preloadBar");
  const pctText = document.getElementById("preloadPct");
  if (!bar) return;

  const pct = total > 0 ? Math.max(0, Math.min(100, 100 * done / total)) : 0;
  bar.style.width = pct.toFixed(1) + "%";

  if (pctText) {
    pctText.innerText = Math.round(pct) + "%";
  }
}

async function loadList() {
  const res = await fetch("/api/list?ts=" + Date.now());
  const data = await res.json();
  allBags = data.bags || [];
  allAnnotations = data.annotations || [];
  renderBags();
  document.getElementById("status").innerText = "found " + allBags.length + " bags";
}

function renderBags() {
  const f = document.getElementById("filter").value.toLowerCase();
  const sel = document.getElementById("bag");
  sel.innerHTML = "";
  for (const b of allBags) {
    const lab = label(b);
    if (f && !(b.toLowerCase() + " " + lab.toLowerCase()).includes(f)) continue;
    const o = document.createElement("option");
    o.value = b;
    o.text = lab;
    o.title = b;
    sel.add(o);
  }
  showSelected();
}

function showSelected() {
  const b = document.getElementById("bag").value;
  document.getElementById("selectedPath").innerText = b || "";
  renderAnnotationsForBag(b || "");
}

async function loadBag(path) {
  const b = path || document.getElementById("bag").value;
  if (!b) return alert("Select a bag first.");

  playing = false;
  clearTimeout(timer);
  document.getElementById("playBtn").innerText = "▶";

  loadedBag = b;
  preloadReady = false;
  preloadInProgress = false;
  preloadToken += 1;
  rawFrameCache = [];
  timFrameCache = [];

  document.getElementById("progress").disabled = true;
  document.getElementById("playBtn").disabled = true;
  document.getElementById("status").innerText = "loading bag...";
  document.getElementById("preloadStatus").innerText = "loading bag...";

  const res = await fetch("/api/load", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({bag: b, ann: selectedAnnotation()})
  });

  const data = await res.json();

  if (!data.ok) {
    document.getElementById("status").innerText = "failed: " + (data.error || "unknown");
    document.getElementById("preloadStatus").innerText = "load failed";
    return;
  }

  loadedFrames = data.frames || 0;
  loadedDuration = data.duration_s || 0;

  document.getElementById("progress").max = Math.max(0, loadedFrames - 1);
  document.getElementById("progress").value = 0;

  const ann = selectedAnnotation();

  document.getElementById("meta").innerText =
    "Watching: " + label(b) +
    " | frames: " + loadedFrames +
    " | duration: " + loadedDuration.toFixed(2) + " s" +
    " | annotation: " + (ann ? annotationLabel(ann) : "none");

  document.getElementById("status").innerText = "loaded, mandatory preload running...";

  await preloadAllFrames(preloadToken);

  if (preloadReady) {
    document.getElementById("status").innerText = "ready";
    document.getElementById("progress").disabled = false;
    document.getElementById("playBtn").disabled = false;
    updateFrame();
  }
}

function currentMode() {
  const el = document.getElementById("viewMode");
  return el ? el.value : "compare";
}

function updateTitles() {
  const mode = currentMode();

  if (mode === "tracks") {
    document.getElementById("rawTitle").innerText = "Tracks only, all IDs";
    document.getElementById("timTitle").innerText = "Tracks only, all IDs";
    document.getElementById("ids").disabled = true;
    document.getElementById("tracks").checked = true;
    return;
  }

  document.getElementById("rawTitle").innerText = "RAW selector output /target";
  document.getElementById("timTitle").innerText = "TIM-MARS output /target_memory_mars";
  document.getElementById("ids").disabled = false;
}

function frameUrl(idx, side) {
  const q = new URLSearchParams();
  const mode = currentMode();

  q.set("idx", String(idx));

  if (mode === "tracks") {
    q.set("draw_detections", document.getElementById("det").checked ? "1" : "0");
    q.set("draw_tracks", "1");
    q.set("only_ids", "");
    q.set("draw_raw", "0");
    q.set("draw_tim", "0");
    return "/frame.jpg?" + q.toString();
  }

  q.set("draw_detections", document.getElementById("det").checked ? "1" : "0");
  q.set("draw_tracks", document.getElementById("tracks").checked ? "1" : "0");
  q.set("only_ids", document.getElementById("ids").value || "");

  if (side === "raw") {
    q.set("draw_raw", "1");
    q.set("draw_tim", "0");
  } else {
    q.set("draw_raw", "0");
    q.set("draw_tim", "1");
  }

  return "/frame.jpg?" + q.toString();
}

function loadDecodedImage(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url + "&ts=" + Date.now();
  });
}

function drawImageToCanvas(canvas, img) {
  if (!img) return;

  if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
  }

  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0);
}

async function preloadAllFrames(token) {
  updateTitles();

  if (loadedFrames <= 0) {
    document.getElementById("preloadStatus").innerText = "no frames";
    return;
  }

  preloadReady = false;
  preloadInProgress = true;

  rawFrameCache = new Array(loadedFrames);
  timFrameCache = new Array(loadedFrames);
  rawDecodedCache = new Array(loadedFrames);
  timDecodedCache = new Array(loadedFrames);

  const status = document.getElementById("preloadStatus");
  status.innerText = "preloading 0/" + loadedFrames;
  setPreloadProgress(0, loadedFrames);

  for (let i = 0; i < loadedFrames; i++) {
    if (token !== preloadToken) return;

    rawDecodedCache[i] = await loadDecodedImage(frameUrl(i, "raw"));

    if (currentMode() === "tracks") {
      // In tracks-only mode both panes use the same decoded image.
      timDecodedCache[i] = rawDecodedCache[i];
    } else {
      timDecodedCache[i] = await loadDecodedImage(frameUrl(i, "tim"));
    }

    rawFrameCache[i] = rawDecodedCache[i] ? rawDecodedCache[i].src : "";
    timFrameCache[i] = timDecodedCache[i] ? timDecodedCache[i].src : "";

    if (i % 10 === 0 || i === loadedFrames - 1) {
      status.innerText = "preloading " + (i + 1) + "/" + loadedFrames;
      setPreloadProgress(i + 1, loadedFrames);
      await new Promise(r => setTimeout(r, 1));
    }
  }

  preloadInProgress = false;
  preloadReady = true;
  status.innerText = "preloaded " + loadedFrames + "/" + loadedFrames;
  setPreloadProgress(loadedFrames, loadedFrames);
}

async function reloadViewCache() {
  if (!loadedBag || loadedFrames <= 0) {
    updateTitles();
    return;
  }

  playing = false;
  clearTimeout(timer);
  document.getElementById("playBtn").innerText = "▶";
  document.getElementById("playBtn").disabled = true;
  document.getElementById("progress").disabled = true;

  preloadReady = false;
  preloadToken += 1;

  document.getElementById("status").innerText = "reloading view cache...";
  await preloadAllFrames(preloadToken);

  if (preloadReady) {
    document.getElementById("status").innerText = "ready";
    document.getElementById("playBtn").disabled = false;
    document.getElementById("progress").disabled = false;
    updateFrame();
  }
}

function updateFrame() {
  const idx = parseInt(document.getElementById("progress").value || "0");
  const t = loadedFrames > 1 ? idx / (loadedFrames - 1) * loadedDuration : 0;

  document.getElementById("time").innerText = fmt(t) + " / " + fmt(loadedDuration);

  if (!preloadReady) {
    document.getElementById("preloadStatus").innerText = "wait for preload";
    return;
  }

  drawImageToCanvas(document.getElementById("rawCanvas"), rawDecodedCache[idx]);
  drawImageToCanvas(document.getElementById("timCanvas"), timDecodedCache[idx]);
}

function seek() {
  if (!preloadReady) {
    document.getElementById("preloadStatus").innerText = "wait for preload";
    return;
  }
  updateFrame();
}

function togglePlay() {
  if (playing) {
    playing = false;
    clearTimeout(timer);
    document.getElementById("playBtn").innerText = "▶";
    return;
  }

  if (loadedFrames <= 1) {
    alert("Load a bag first.");
    return;
  }

  if (!preloadReady) {
    alert("Frames are still preloading. Wait until it says preloaded.");
    return;
  }

  playing = true;
  document.getElementById("playBtn").innerText = "⏸";
  step();
}

function step() {
  if (!playing) return;

  const p = document.getElementById("progress");
  let v = parseInt(p.value || "0");

  if (v >= loadedFrames - 1) {
    v = 0;
  } else {
    v += 1;
  }

  p.value = v;
  updateFrame();

  const naturalDelay = loadedFrames > 1 ? loadedDuration * 1000 / loadedFrames : 100;
  const delay = Math.max(40, Math.min(140, naturalDelay));

  timer = setTimeout(step, delay);
}


function metric(row, ...keys) {
  for (const key of keys) {
    if (row[key] !== undefined && row[key] !== null && row[key] !== "") {
      const v = parseFloat(row[key]);
      if (Number.isFinite(v)) return v;
    }
  }
  return null;
}

function fmtMetric(v, digits = 3) {
  if (v === null || v === undefined || !Number.isFinite(v)) return "";
  return v.toFixed(digits);
}

function renderEvalTable(rows) {
  const host = document.getElementById("evalTable");
  if (!host) return;

  if (!rows || rows.length === 0) {
    host.innerHTML = "<p>No evaluation rows returned.</p>";
    return;
  }

  let html = "";
  html += '<table class="evalTable">';
  html += "<thead><tr>";
  html += "<th>stream</th>";
  html += "<th>correct [s]</th>";
  html += "<th>wrong [s]</th>";
  html += "<th>lost [s]</th>";
  html += "<th>absent-output [s]</th>";
  html += "<th>ref missing [s]</th>";
  html += "<th>correct ratio</th>";
  html += "<th>wrong ratio</th>";
  html += "<th>lost ratio</th>";
  html += "</tr></thead><tbody>";

  for (const row of rows) {
    const stream = row.stream || "";

    const correct = metric(row, "correct_target_duration_s");
    const wrong = metric(row, "wrong_target_duration_s");
    const lost = metric(row, "lost_target_duration_s");
    const absent = metric(row,
      "target_absent_but_output_valid_duration_s",
      "target_absent_but_output_valid_s"
    );
    const refMissing = metric(row, "reference_missing_duration_s");
    const correctRatio = metric(row, "correct_target_ratio");
    const wrongRatio = metric(row, "wrong_target_ratio");
    const lostRatio = metric(row, "lost_target_ratio");

    html += "<tr>";
    html += "<td>" + stream + "</td>";
    html += '<td class="goodMetric">' + fmtMetric(correct) + "</td>";
    html += '<td class="' + ((wrong || 0) > 0.001 ? "badMetric" : "") + '">' + fmtMetric(wrong) + "</td>";
    html += "<td>" + fmtMetric(lost) + "</td>";
    html += '<td class="' + ((absent || 0) > 0.001 ? "badMetric" : "") + '">' + fmtMetric(absent) + "</td>";
    html += "<td>" + fmtMetric(refMissing) + "</td>";
    html += '<td class="goodMetric">' + fmtMetric(correctRatio) + "</td>";
    html += '<td class="' + ((wrongRatio || 0) > 0.001 ? "badMetric" : "") + '">' + fmtMetric(wrongRatio) + "</td>";
    html += "<td>" + fmtMetric(lostRatio) + "</td>";
    html += "</tr>";
  }

  html += "</tbody></table>";
  host.innerHTML = html;
}

async function evaluateBag() {
  const bagEl = document.getElementById("bag");
  const b = loadedBag || (bagEl ? bagEl.value : "");
  const ann = selectedAnnotation();

  const status = document.getElementById("evalStatus");
  const table = document.getElementById("evalTable");
  const log = document.getElementById("evalLog");

  if (!b) {
    alert("Select or load a bag first.");
    return;
  }

  if (!ann) {
    alert("Select an annotation first.");
    return;
  }

  if (status) status.innerText = "evaluating...";
  if (table) table.innerHTML = "";
  if (log) log.innerText = "";

  try {
    const res = await fetch("/api/evaluate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({bag: b, ann: ann})
    });

    const data = await res.json();

    if (!data.ok) {
      if (status) status.innerText = "failed";
      if (log) {
        log.innerText =
          "ERROR: " + (data.error || "unknown error") + "\n\n" +
          (data.log || "") + "\n\n" +
          (data.cmd || "");
      }
      return;
    }

    if (status) status.innerText = "done";
    renderEvalTable(data.rows || []);

    if (log) {
      log.innerText =
        "out_dir: " + data.out_dir + "\n" +
        "summary_csv: " + data.summary_csv + "\n" +
        "summary_md: " + data.summary_md + "\n\n" +
        (data.markdown || "");
    }
  } catch (err) {
    if (status) status.innerText = "failed";
    if (log) log.innerText = String(err);
  }
}


async function runTim() {
  const b = loadedBag || document.getElementById("bag").value;
  if (!b) return alert("Select and load a bag first.");
  document.getElementById("log").innerText = "Starting TIM-MARS replay...";
  const payload = {
    bag: b,
    target_id: parseInt(document.getElementById("targetId").value || "1"),
    tracker: document.getElementById("tracker").value,
    tim_mode: "mars",
    rate: parseFloat(document.getElementById("rate").value || "1.0"),
    absence_min_total: 0.60,
    absence_min_distance: 0.35,
    absence_min_scale: 0.45,
    absence_min_similarity: 0.70,
    absence_appearance_margin: 0.25,
    absence_confirm_frames: 4,
    rank_aware_lost_min_total: 0.60,
    rank_aware_lost_min_geom: 0.25,
    rank_aware_lost_min_app: 0.10,
    rank_aware_lost_app_margin: 0.10,
    rank_aware_confirm_frames: 4
  };
  const res = await fetch("/api/replay", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!data.ok) {
    document.getElementById("log").innerText = JSON.stringify(data, null, 2);
    return;
  }
  pollJob();
}

async function pollJob() {
  const res = await fetch("/api/job?ts=" + Date.now());
  const data = await res.json();
  document.getElementById("log").innerText = data.log || "";
  if (data.running) {
    setTimeout(pollJob, 1500);
    return;
  }
  if (data.last_output_bag) {
    await loadList();
    await loadBag(data.last_output_bag);
  }
}

async function loadLast() {
  const res = await fetch("/api/job?ts=" + Date.now());
  const data = await res.json();
  if (data.last_output_bag) loadBag(data.last_output_bag);
  else alert("No last output bag.");
}

window.addEventListener("load", loadList);

function showFrontendError(err) {
  const box = document.getElementById("frontendError");
  if (!box) return;
  box.style.display = "block";
  box.innerText = String(err && err.stack ? err.stack : err);
}

window.addEventListener("error", function(e) {
  showFrontendError("JavaScript error: " + e.message + "\n" + e.filename + ":" + e.lineno);
});

window.addEventListener("unhandledrejection", function(e) {
  showFrontendError("Unhandled promise rejection:\n" + String(e.reason));
});


let annotationRows = [];
let activeAnnotationIndex = -1;

function currentTimeS() {
  const idx = parseInt(document.getElementById("progress").value || "0");
  return loadedFrames > 1 ? idx / (loadedFrames - 1) * loadedDuration : 0;
}

function annSetStartNow() {
  document.getElementById("annStart").value = currentTimeS().toFixed(3);
}

function annSetEndNow() {
  document.getElementById("annEnd").value = currentTimeS().toFixed(3);
}

function currentBagNameForAnnotation() {
  return (loadedBag || document.getElementById("bag").value || "").split("/").pop();
}

function normaliseAnnRow(row) {
  const label = (row.target_label || "CORRECT_TARGET").toUpperCase();
  const visible = label === "CORRECT_TARGET";
  return {
    bag_name: row.bag_name || currentBagNameForAnnotation(),
    start_s: String(row.start_s ?? "0"),
    end_s: String(row.end_s ?? "0"),
    target_label: label,
    target_visible: String(row.target_visible ?? (visible ? "true" : "false")),
    correct_target_track_id: String(row.correct_target_track_id ?? ""),
    distractor_track_ids: String(row.distractor_track_ids ?? ""),
    event_type: String(row.event_type ?? "manual_interval"),
    notes: String(row.notes ?? "created in TIM clean UI")
  };
}

function annRenderRows() {
  const host = document.getElementById("annRows");
  const status = document.getElementById("annStatus");
  annotationRows.sort((a, b) => parseFloat(a.start_s) - parseFloat(b.start_s));

  status.innerText = annotationRows.length + " annotation intervals loaded.";

  if (!annotationRows.length) {
    host.innerHTML = "";
    return;
  }

  let html = "<table><thead><tr>";
  html += "<th>#</th><th>start</th><th>end</th><th>label</th><th>visible</th><th>ID</th><th>event</th><th>notes</th>";
  html += "</tr></thead><tbody>";

  annotationRows.forEach((r, i) => {
    const cls = i === activeAnnotationIndex ? " class='active'" : "";
    html += "<tr" + cls + " onclick='annSelectRow(" + i + ")'>";
    html += "<td>" + i + "</td>";
    html += "<td>" + Number(r.start_s).toFixed(3) + "</td>";
    html += "<td>" + Number(r.end_s).toFixed(3) + "</td>";
    html += "<td>" + r.target_label + "</td>";
    html += "<td>" + r.target_visible + "</td>";
    html += "<td>" + r.correct_target_track_id + "</td>";
    html += "<td>" + r.event_type + "</td>";
    html += "<td>" + r.notes + "</td>";
    html += "</tr>";
  });

  html += "</tbody></table>";
  host.innerHTML = html;
}

function annSelectRow(i) {
  activeAnnotationIndex = i;
  const r = annotationRows[i];
  if (!r) return;

  document.getElementById("annStart").value = Number(r.start_s).toFixed(3);
  document.getElementById("annEnd").value = Number(r.end_s).toFixed(3);
  document.getElementById("annTargetId").value = r.correct_target_track_id || "";
  document.getElementById("annLabel").value = r.target_label || "CORRECT_TARGET";
  document.getElementById("annEvent").value = r.event_type || "manual_interval";
  document.getElementById("annNotes").value = r.notes || "";

  annRenderRows();
}

function annAddInterval() {
  const label = document.getElementById("annLabel").value;
  const start = parseFloat(document.getElementById("annStart").value || "0");
  const end = parseFloat(document.getElementById("annEnd").value || "0");
  const targetId = document.getElementById("annTargetId").value.trim();

  if (!(end > start)) {
    alert("Invalid interval: end must be greater than start.");
    return;
  }

  const visible = label === "CORRECT_TARGET";
  const row = normaliseAnnRow({
    bag_name: currentBagNameForAnnotation(),
    start_s: start.toFixed(3),
    end_s: end.toFixed(3),
    target_label: label,
    target_visible: visible ? "true" : "false",
    correct_target_track_id: visible ? targetId : "",
    distractor_track_ids: "",
    event_type: document.getElementById("annEvent").value || "manual_interval",
    notes: document.getElementById("annNotes").value || "created in TIM clean UI"
  });

  if (visible && !row.correct_target_track_id) {
    alert("CORRECT_TARGET needs a target ID.");
    return;
  }

  if (activeAnnotationIndex >= 0 && annotationRows[activeAnnotationIndex]) {
    annotationRows[activeAnnotationIndex] = row;
  } else {
    annotationRows.push(row);
    activeAnnotationIndex = annotationRows.length - 1;
  }

  annRenderRows();
}

function annDeleteActive() {
  if (activeAnnotationIndex < 0) return;
  annotationRows.splice(activeAnnotationIndex, 1);
  activeAnnotationIndex = -1;
  annRenderRows();
}

async function annLoadSelected() {
  const ann = selectedAnnotation();
  if (!ann) {
    alert("Select an annotation CSV first.");
    return;
  }

  const res = await fetch("/api/annotation/load", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({path: ann})
  });
  const data = await res.json();
  if (!data.ok) {
    alert(data.error || "Failed to load annotation.");
    return;
  }

  annotationRows = (data.rows || []).map(normaliseAnnRow);
  activeAnnotationIndex = -1;
  document.getElementById("annOutPath").value = ann.replace(".csv", "_edited.csv");
  document.getElementById("annStatus").innerText = "Loaded " + annotationRows.length + " intervals from " + ann;
  annRenderRows();
}

async function annSave() {
  const outPath = document.getElementById("annOutPath").value.trim();
  if (!outPath) {
    alert("Set output CSV path.");
    return;
  }
  if (!annotationRows.length) {
    alert("No annotation rows to save.");
    return;
  }

  const res = await fetch("/api/annotation/save", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({path: outPath, rows: annotationRows})
  });
  const data = await res.json();
  if (!data.ok) {
    alert(data.error || "Failed to save annotation.");
    return;
  }

  document.getElementById("annStatus").innerText = data.message || "Saved.";
}

window.addEventListener("keydown", function(e) {
  if (e.target && ["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;

  if (e.key === "a" || e.key === "A") {
    annAddInterval();
  } else if (e.key === "s" || e.key === "S") {
    e.preventDefault();
    annSave();
  } else if (e.key === "[") {
    annSetStartNow();
  } else if (e.key === "]") {
    annSetEndNow();
  } else if (e.key === "Delete" || e.key === "Backspace") {
    annDeleteActive();
  }
});


window.addEventListener("DOMContentLoaded", async function() {
  try {
    await loadList();
  } catch (err) {
    showFrontendError(err);
  }
});

</script>
</body>
</html>
"""




def _load_bag_inventory_for_ui() -> list[dict]:
    inv = REPO_ROOT / "docs" / "catalogue" / "bag_inventory.yaml"
    if not inv.exists():
        return []

    bags = []
    cur = None

    for line in inv.read_text().splitlines():
        if line.startswith("  - path:"):
            if cur:
                bags.append(cur)
            cur = {"path": line.split(":", 1)[1].strip().strip('"')}
        elif cur is not None and line.startswith("    "):
            key, _, value = line.strip().partition(":")
            if not key or key == "topics":
                continue
            cur[key] = value.strip().strip('"')

    if cur:
        bags.append(cur)

    return bags


def _ui_bag_label_from_inventory(item: dict) -> str:
    path = str(item.get("path", ""))
    name = Path(path).name

    bits = [
        str(item.get("status", "") or "review"),
        str(item.get("source_kind", "") or "bag"),
    ]

    for key in ["category", "sequence", "tracker"]:
        value = str(item.get(key, ""))
        if value:
            bits.append(value)

    tim = str(item.get("tim_mode", ""))
    if tim:
        bits.append(f"tim={tim}")

    target = str(item.get("target_id", ""))
    if target:
        bits.append(f"target={target}")

    duration = str(item.get("duration", ""))
    if duration:
        bits.append(duration)

    return " | ".join(bits) + f" :: {name}"


@app.get("/clean-static", response_class=HTMLResponse)
def clean_static_ui():
    bag_roots = [
        REPO_ROOT / "artifacts" / "bags" / "OFFICIAL_BAGS",
        REPO_ROOT / "artifacts" / "bags" / "ANNOTATION_BAGS",
        REPO_ROOT / "artifacts" / "bags" / "TIM_EVAL_QUEUE",
        REPO_ROOT / "artifacts" / "bags" / "TIM_GOOD",
    ]

    bags = []
    for root in bag_roots:
        if root.exists():
            for meta in sorted(root.rglob("metadata.yaml")):
                bags.append(str(meta.parent.relative_to(REPO_ROOT)))

    annotations_root = REPO_ROOT / "docs" / "annotations"
    annotations = []
    if annotations_root.exists():
        annotations = [
            str(path.relative_to(REPO_ROOT))
            for path in sorted(annotations_root.rglob("*.csv"))
        ]

    def bag_label(path: str) -> str:
        name = Path(path).name
        lower = name.lower()

        prefix = "[bag]"
        if "OFFICIAL_BAGS" in path:
            prefix = "[OFFICIAL BAGS]"
        elif "ANNOTATION_BAGS" in path:
            prefix = "[annotation]"
        elif "TIM_EVAL_QUEUE" in path:
            prefix = "[TIM EVAL QUEUE]"
        elif "TIM_GOOD" in path:
            prefix = "[TIM GOOD]"
        elif "official" in lower:
            prefix = "[official]"

        seq = ""
        if "seq01" in lower:
            seq = "seq01 clean"
        elif "seq02" in lower:
            seq = "seq02 re-entry"
        elif "seq03" in lower:
            seq = "seq03 crossing"
        elif "seq04" in lower:
            seq = "seq04 occlusion"
        elif "hard_reentry" in lower:
            seq = "hard re-entry / ID switch"

        tracker = ""
        if "bytetrack" in lower:
            tracker = "ByteTrack"
        elif "ocsort" in lower:
            tracker = "OCSORT"
        elif "deepsort" in lower:
            tracker = "DeepSORT"

        mode = ""
        if "tim_mars" in lower:
            mode = "TIM-MARS"
        elif "tim_on" in lower:
            mode = "TIM"
        elif "tim_off" in lower:
            mode = "raw"

        target = "target 1" if "target_1" in lower else ""
        replay = "r1" if lower.endswith("__r1") or "_r1" in lower else ("r2" if lower.endswith("__r2") or "_r2" in lower else "")

        parts = [prefix]
        for x in (seq, tracker, mode, target, replay):
            if x:
                parts.append(x)
        return " | ".join(parts)

    def annotation_label(path: str) -> str:
        lower = path.lower()
        parts = []

        if "hard_reentry" in lower:
            parts.append("hard re-entry")
        elif "seq01" in lower:
            parts.append("seq01 clean")
        elif "seq02" in lower:
            parts.append("seq02 re-entry")
        elif "seq03" in lower:
            parts.append("seq03 crossing")
        elif "seq04" in lower:
            parts.append("seq04 occlusion")

        if "bytetrack" in lower:
            parts.append("ByteTrack")
        elif "ocsort" in lower:
            parts.append("OCSORT")
        elif "deepsort" in lower:
            parts.append("DeepSORT")

        if "track_time" in lower:
            parts.append("track-time")
        elif "header_time" in lower:
            parts.append("header-time")
        elif "ros_time" in lower:
            parts.append("ROS-time")
        else:
            parts.append("manual")

        if "corrected" in lower:
            parts.append("corrected")
        if "_r1_" in lower:
            parts.append("r1")
        if "_r2_" in lower:
            parts.append("r2")

        return " | ".join(parts)

    bags = sorted(
        bags,
        key=lambda b: (
            0 if "ui_replays" in b else
            1 if "hard_reentry" in b.lower() else
            2 if "official" in b.lower() else
            3,
            b.lower(),
        ),
    )

    inventory = _load_bag_inventory_for_ui()
    bag_label_map = {}
    if inventory:
        visible_statuses = {"canonical", "review"}
        inventory_visible = [
            item for item in inventory
            if (
                str(item.get("source_kind", "")) == "raw_capture"
                and str(item.get("status", "")) in {"canonical", "review"}
            )
            or str(item.get("category", "")) == "full_pipeline_from_image_raw"
            or "full_pipeline_from_image_raw" in str(item.get("path", ""))
        ]
        inventory_bags = [
            str(item.get("path", ""))
            for item in inventory_visible
            if item.get("path")
        ]

        visible_bag_prefixes = (
            "artifacts/bags/OFFICIAL_BAGS/",
            "artifacts/bags/ANNOTATION_BAGS/",
            "artifacts/bags/TIM_EVAL_QUEUE/",
            "artifacts/bags/TIM_GOOD/",
        )
        inventory_bags = [
            b for b in inventory_bags
            if b.startswith(visible_bag_prefixes)
        ]

        # Keep catalogue labels, but do not hide newly generated/evaluated bags.
        discovered_bags = []
        extra_roots = [
            REPO_ROOT / "artifacts" / "bags" / "OFFICIAL_BAGS",
            REPO_ROOT / "artifacts" / "bags" / "ANNOTATION_BAGS",
            REPO_ROOT / "artifacts" / "bags" / "TIM_EVAL_QUEUE",
            REPO_ROOT / "artifacts" / "bags" / "TIM_GOOD",
        ]

        for root in extra_roots:
            if root.exists():
                for meta in sorted(root.rglob("metadata.yaml")):
                    discovered_bags.append(str(meta.parent.relative_to(REPO_ROOT)))

        bags = sorted(set(inventory_bags + discovered_bags))

        bag_label_map = {
            str(item.get("path", "")): _ui_bag_label_from_inventory(item)
            for item in inventory_visible
            if item.get("path")
        }

    bag_options = "\n".join(
        f'<option value="{html_lib.escape(b)}" title="{html_lib.escape(b)}">'
        f'{html_lib.escape(bag_label_map.get(b, bag_label(b)))}'
        f'</option>'
        for b in bags
    )

    bags_json = json.dumps(bags)
    annotation_options = "\n".join(
        f'<option value="{html_lib.escape(a)}" title="{html_lib.escape(a)}">{html_lib.escape(annotation_label(a))}</option>'
        for a in annotations
    )

    annotations_json = json.dumps(annotations)

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>TIM-MARS Clean Static UI</title>
<style>
body {{ background:#111; color:#eee; font-family:Arial, sans-serif; margin:12px; font-size:24px; }}
h2 {{ margin:10px 0 16px 0; font-size:34px; }}
h3 {{ margin:0 0 12px 0; font-size:26px; }}

.panel {{ border:1px solid #333; border-radius:8px; padding:10px; margin:10px 0; background:#151515; }}

select, input, button {{
  background:#222;
  color:#eee;
  border:1px solid #555;
  border-radius:6px;
  padding:13px 16px;
  margin:6px;
  font-size:24px;
}}

select {{ width:min(980px, 88vw); }}
button {{ font-weight:700; cursor:pointer; }}

#status, #evalStatus {{ margin-left:8px; color:#ccc; font-weight:700; }}
#path, #annPath {{ color:#888; font-size:11px; margin:2px 4px 6px 4px; word-break:break-all; }}

.viewer {{
  display:flex;
  gap:16px;
  justify-content:center;
  align-items:flex-start;
  flex-wrap:nowrap;
  width:100%;
}}

.pane {{
  width:calc((100vw - 58px) / 2);
  max-width:none;
  min-width:0;
  background:#000;
  border:1px solid #333;
  border-radius:6px;
  overflow:hidden;
}}

.pane h3 {{
  margin:0;
  padding:7px;
  background:#222;
  text-align:center;
  font-size:14px;
}}


.annotationBox {{
  margin-top: 12px;
  padding: 10px;
  border: 1px solid #333;
  border-radius: 10px;
  background: #111;
}}
.annotationBox h3 {{
  margin: 0 0 8px 0;
}}
.annotationControls {{
  display: grid;
  grid-template-columns: repeat(6, minmax(90px, 1fr));
  gap: 6px;
  align-items: end;
}}
.annotationControls input,
.annotationControls select {{
  width: 100%;
  box-sizing: border-box;
}}
.annotationButtons {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}}
#annRows {{
  margin-top: 8px;
  max-height: 190px;
  overflow: auto;
  font-family: monospace;
  font-size: 12px;
  border: 1px solid #333;
  border-radius: 8px;
}}
#annRows table {{
  width: 100%;
  border-collapse: collapse;
}}
#annRows th,
#annRows td {{
  border-bottom: 1px solid #222;
  padding: 4px 6px;
  text-align: left;
}}
#annRows tr.active {{
  outline: 2px solid #55c7ff;
}}

canvas {{
  width:100%;
  aspect-ratio:16/9;
  height:auto;
  display:block;
  background:#000;
}}

.controls {{
  display:flex;
  gap:8px;
  align-items:center;
  justify-content:center;
  margin-top:9px;
  width:100%;
}}

#slider {{ width:min(760px, 56vw); }}

#preloadWrap {{ width:280px; height:15px; border:1px solid #666; border-radius:999px; background:#050505; overflow:hidden; }}
#preloadBar {{ height:100%; width:0%; background:linear-gradient(90deg,#2f80ed,#55c7ff); }}
#evalTable {{ margin-top:12px; }}
.evalCards {{ display:grid; grid-template-columns:repeat(2, minmax(320px, 1fr)); gap:14px; margin-top:10px; }}
.evalCard {{ background:#101010; border:1px solid #333; border-radius:10px; overflow:hidden; }}
.evalCardHeader {{ padding:10px 12px; background:#202020; font-weight:800; display:flex; justify-content:space-between; align-items:center; }}
.evalBadge {{ font-size:12px; padding:3px 8px; border-radius:999px; background:#333; color:#ccc; }}
.evalBadgeSafe {{ background:#12351a; color:#9be28f; }}
.evalBadgeUnsafe {{ background:#3a1111; color:#ff8b8b; }}
.metricGrid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:#262626; }}
.metricBox {{ background:#131313; padding:12px; }}
.metricLabel {{ color:#aaa; font-size:12px; margin-bottom:5px; }}
.metricValue {{ font-size:20px; font-weight:800; }}
.metricRatio {{ color:#888; font-size:12px; margin-top:3px; }}
.good {{ color:#9be28f; font-weight:700; }}
.bad {{ color:#ff7777; font-weight:700; }}
.neutral {{ color:#ddd; }}
.evalSummary {{ margin-top:12px; padding:10px 12px; border-radius:8px; background:#181818; border:1px solid #333; color:#ddd; line-height:1.45; }}
#log {{ display:none; white-space:pre-wrap; background:#050505; padding:10px; margin-top:10px; max-height:260px; overflow:auto; color:#bbb; border:1px solid #333; border-radius:8px; }}
#error {{ display:none; white-space:pre-wrap; background:#2a0707; color:#ffb3b3; border:1px solid #8a3333; padding:10px; border-radius:6px; }}

.annotationBox, .annRow, .evalCards, #annRows {{
  font-size:24px;
}}

label {{
  font-size:23px;
}}

small {{
  font-size:20px;
}}

select option {{
  font-size:24px;
}}


/* Annotation editor visual cleanup */
#annCsv, #annStart, #annEnd, #annTargetId, #annLabel, #annEvent, #annNotes {{
  background:#242424;
  color:#f0f0f0;
  border:1px solid #666;
  border-radius:6px;
  padding:10px 12px;
  font-size:24px;
}}

#annNotes.notesInput {{
  width:520px;
  max-width:520px;
}}

button {{
  background:#3a3a3a;
  color:#ffffff;
  border:2px solid #888;
  border-radius:8px;
  padding:11px 16px;
  font-size:24px;
  font-weight:700;
  cursor:pointer;
}}

button:hover {{
  background:#4a4a4a;
  border-color:#bbb;
}}

button:active {{
  background:#5a5a5a;
}}

#annCsv {{
  width:520px;
}}

#annStart, #annEnd, #annTargetId {{
  width:150px;
}}

#annLabel, #annEvent {{
  width:330px;
}}

</style>
</head>
<body>
<h2>TIM-MARS Clean Static UI</h2>
<div id="error"></div>

<div class="panel">
<h3>1. Load bag</h3>
<label>filter</label>
<input id="filter" placeholder="hard, seq03, bytetrack..." oninput="renderBags()">
<br>
<select id="bag" onchange="onBagChange()">{bag_options}</select>
<div id="path"></div>

<label>annotation, auto-selected from bag + tracker</label><br>
<select id="ann" onchange="showAnn()">{annotation_options}</select>
<div id="annPath"></div>

<button onclick="loadBag()">Load selected bag</button>
<button onclick="evaluateBag()">Evaluate RAW vs TIM</button>
<span id="status">ready, {len(bags)} bags, {len(annotations)} annotations</span>
<span id="evalStatus"></span>
</div>

<div class="panel">
<h3>2. Viewer</h3>
<div id="meta">Load a bag.</div>
<div class="viewer">
  <div class="pane"><h3>RAW selector output /target</h3><canvas id="rawCanvas" width="960" height="540"></canvas></div>
  <div class="pane"><h3>TIM-MARS output /target_memory_mars</h3><canvas id="timCanvas" width="960" height="540"></canvas></div>
</div>
<div class="controls">
  <button id="playBtn" onclick="togglePlay()" disabled>▶</button>
  <span id="time">0s / 0s</span>
  <input id="slider" type="range" min="0" max="0" value="0" oninput="seek(this.value)" disabled>
  <span id="preloadStatus">not loaded</span>
  <div id="preloadWrap"><div id="preloadBar"></div></div>
  <span id="pct">0%</span>
</div>
</div>

<div class="panel">
<h3>3. Evaluation result</h3>

<div class="annotationBox">
  <h3>4. Annotation editor</h3>
  <div class="hint">
    Creates evaluator-compatible interval CSVs. Use the viewer to find the correct time range, then set start/end and target ID.
  </div>

  <div class="annotationControls">
    <label>output CSV
      <input id="annOutPath" value="docs/annotations/ui_created/new_annotation.csv">
    </label>
    <label>start s
      <input id="annStart" type="number" step="0.001" value="0.000">
    </label>
    <label>end s
      <input id="annEnd" type="number" step="0.001" value="1.000">
    </label>
    <label>target ID
      <input id="annTargetId" type="number" step="1" value="1">
    </label>
    <label>label
      <select id="annLabel">
        <option value="CORRECT_TARGET">CORRECT_TARGET</option>
        <option value="TARGET_NOT_VISIBLE">TARGET_NOT_VISIBLE</option>
        <option value="NO_TARGET_SELECTED">NO_TARGET_SELECTED</option>
      </select>
    </label>
    <label>event
      <select id="annEvent">
              <option value="manual_interval">manual_interval</option>
              <option value="id_switch">id_switch</option>
              <option value="target_occluded">target_occluded</option>
              <option value="target_exits_frame">target_exits_frame</option>
              <option value="target_reappears">target_reappears</option>
              <option value="uncertain">uncertain</option>
            </select>
    </label>
  </div>

  <label>notes
    <input id="annNotes" style="width:100%" value="created in TIM clean UI">
  </label>

  <div class="annotationButtons">
    <button onclick="annAddInterval()">Add / update interval</button>
    <button onclick="annDeleteActive()">Delete active</button>
    <button onclick="annLoadSelected()">Load selected CSV</button>
    <button onclick="annSave()">Save CSV</button>
  </div>

  <div class="hint" id="annStatus">No annotation rows loaded.</div>
  <div id="annRows"></div>
</div>

<div id="evalTable"></div>
<div id="log"></div>
</div>

<script>
var allBags = {bags_json};
var allAnnotations = {annotations_json};
var loadedBag = "";
var loadedFrames = 0;
var loadedDuration = 0;
var currentFrame = 0;
var playing = false;
var timer = null;
var rawCache = [];
var timCache = [];

function fail(e) {{
  console.error(e);
  var box = document.getElementById("error");
  box.style.display = "block";
  box.innerText = String(e && e.stack ? e.stack : e);
}}

function cleanLabel(p) {{
  var name = p.split("/").pop();
  return name.replaceAll("__", " | ").replace("hard_reentry_id_switch_raw", "hard re-entry / ID switch");
}}

function annotationScore(bag, ann) {{
  var b = (bag || "").toLowerCase();
  var a = (ann || "").toLowerCase();
  var s = 0;
  if (b.includes("hard_reentry") && a.includes("hard_reentry")) {{
    s += 100;
    if (b.includes("bytetrack") && a.includes("bytetrack")) s += 80;
    if (a.includes("fresh_replay_corrected")) s += 50;
    if (a.includes("corrected")) s += 40;
    if (a.includes("header_time")) s += 30;
    if (a.includes("_r2_")) s += 80;
    if (a.includes("_r1_")) s -= 40;
    return s;
  }}
  for (var seq of ["seq01","seq02","seq03","seq04"]) {{
    if (b.includes(seq) && a.includes(seq)) {{
      s += 100;
      if (a.includes("manual_track_time")) s += 80;
      else if (a.includes("target_id_only")) s -= 50;
      return s;
    }}
  }}
  return s;
}}

function renderBags() {{
  var f = document.getElementById("filter").value.toLowerCase();
  var sel = document.getElementById("bag");
  var current = sel.value;
  sel.innerHTML = "";
  var shown = allBags.filter(function(b) {{ return !f || b.toLowerCase().includes(f); }});
  for (var b of shown) {{
    var o = document.createElement("option");
    o.value = b;
    o.text = cleanLabel(b);
    o.title = b;
    sel.add(o);
  }}
  if (current && shown.includes(current)) sel.value = current;
  onBagChange();
}}

function onBagChange() {{
  var b = document.getElementById("bag").value || "";
  document.getElementById("path").innerText = b;
  var annSel = document.getElementById("ann");
  annSel.innerHTML = "";
  var ranked = allAnnotations.map(function(a) {{ return {{path:a, score:annotationScore(b,a)}}; }})
    .filter(function(x) {{ return x.score > 0; }})
    .sort(function(x,y) {{ return y.score - x.score || x.path.localeCompare(y.path); }});
  if (!ranked.length) ranked = allAnnotations.map(function(a) {{ return {{path:a, score:0}}; }});
  for (var x of ranked) {{
    var o = document.createElement("option");
    o.value = x.path;
    o.text = x.path.split("/").pop();
    o.title = x.path;
    annSel.add(o);
  }}
  showAnn();
}}

function showAnn() {{
  document.getElementById("annPath").innerText = document.getElementById("ann").value || "";
}}

function setProgress(done, total) {{
  var pct = total > 0 ? Math.max(0, Math.min(100, 100 * done / total)) : 0;
  document.getElementById("preloadBar").style.width = pct.toFixed(1) + "%";
  document.getElementById("pct").innerText = Math.round(pct) + "%";
}}

function frameUrl(idx, side) {{
  var ann = document.getElementById("ann").value || "";
  var url = new URL("/frame.jpg", window.location.origin);
  url.searchParams.set("idx", idx);
  url.searchParams.set("side", side);
  if (ann) url.searchParams.set("ann", ann);
  url.searchParams.set("draw_ref", "1");
  url.searchParams.set("draw_raw", side === "raw" ? "1" : "0");
  url.searchParams.set("draw_tim", side === "tim" ? "1" : "0");
  return url.toString();
}}

function loadImg(url) {{
  return new Promise(function(resolve, reject) {{
    var img = new Image();
    img.onload = function() {{ resolve(img); }};
    img.onerror = reject;
    img.src = url;
  }});
}}

function draw(canvasId, img) {{
  var c = document.getElementById(canvasId);
  var ctx = c.getContext("2d");
  ctx.clearRect(0,0,c.width,c.height);
  ctx.drawImage(img,0,0,c.width,c.height);
}}

async function preloadAll() {{
  rawCache = new Array(loadedFrames);
  timCache = new Array(loadedFrames);
  setProgress(0, loadedFrames);
  for (var i = 0; i < loadedFrames; i++) {{
    rawCache[i] = await loadImg(frameUrl(i, "raw"));
    timCache[i] = await loadImg(frameUrl(i, "tim"));
    document.getElementById("preloadStatus").innerText = "preloading " + (i+1) + "/" + loadedFrames;
    setProgress(i+1, loadedFrames);
    await new Promise(function(r) {{ setTimeout(r, 1); }});
  }}
  document.getElementById("preloadStatus").innerText = "preloaded " + loadedFrames + "/" + loadedFrames;
}}

function updateFrame() {{
  if (!loadedFrames) return;
  currentFrame = Math.max(0, Math.min(loadedFrames - 1, currentFrame));
  document.getElementById("slider").value = currentFrame;
  var t = loadedFrames > 1 ? loadedDuration * currentFrame / (loadedFrames - 1) : 0;
  document.getElementById("time").innerText = Math.round(t) + "s / " + Math.round(loadedDuration) + "s";
  if (rawCache[currentFrame]) draw("rawCanvas", rawCache[currentFrame]);
  if (timCache[currentFrame]) draw("timCanvas", timCache[currentFrame]);
}}

async function loadBag() {{
  try {{
    var bag = document.getElementById("bag").value;
    var ann = document.getElementById("ann").value || "";
    if (!bag) return alert("Select a bag first.");
    document.getElementById("status").innerText = "loading bag...";
    var res = await fetch("/api/load", {{
      method:"POST",
      headers:{{"Content-Type":"application/json"}},
      body:JSON.stringify({{bag:bag, ann:ann}})
    }});
    var data = await res.json();
    if (!data.ok) throw new Error(data.error || "load failed");

    loadedBag = bag;
    loadedFrames = data.frames || data.n_frames || 0;
    loadedDuration = data.duration_s || 0;
    currentFrame = 0;

    document.getElementById("meta").innerText =
      "Watching: " + cleanLabel(bag) + " | frames: " + loadedFrames + " | duration: " + loadedDuration.toFixed(2) + " s";

    document.getElementById("slider").max = Math.max(0, loadedFrames - 1);
    document.getElementById("slider").disabled = true;
    document.getElementById("playBtn").disabled = true;

    await preloadAll();

    document.getElementById("slider").disabled = false;
    document.getElementById("playBtn").disabled = false;
    document.getElementById("status").innerText = "loaded";
    updateFrame();
  }} catch (e) {{
    fail(e);
    document.getElementById("status").innerText = "failed";
  }}
}}

function seek(v) {{
  currentFrame = parseInt(v);
  updateFrame();
}}

function togglePlay() {{
  if (!loadedFrames) return;
  playing = !playing;
  document.getElementById("playBtn").innerText = playing ? "pause" : "play";
  if (playing) {{
    timer = setInterval(function() {{
      currentFrame += 1;
      if (currentFrame >= loadedFrames) {{
        currentFrame = loadedFrames - 1;
        togglePlay();
      }}
      updateFrame();
    }}, 1000 * loadedDuration / Math.max(1, loadedFrames));
  }} else {{
    clearInterval(timer);
  }}
}}

function fmt(v) {{
  var x = parseFloat(v);
  return Number.isFinite(x) ? x.toFixed(3) : "";
}}

function n(v) {{
  var x = parseFloat(v);
  return Number.isFinite(x) ? x : 0;
}}

function metricBox(label, value, ratio, cls) {{
  return '<div class="metricBox"><div class="metricLabel">' + label + '</div><div class="metricValue ' + cls + '">' + fmt(value) + ' s</div><div class="metricRatio">ratio ' + fmt(ratio) + '</div></div>';
}}

function renderEval(rows) {{
  var html = '<div class="evalCards">';
  for (var r of rows) {{
    var wrong = n(r.wrong_target_duration_s);
    var absent = n(r.target_absent_but_output_valid_s || r.target_absent_but_output_valid_duration_s);
    var unsafe = wrong > 0.001 || absent > 0.001;
    var title = r.stream === "raw_target" ? "RAW selector" : (r.stream === "tim_target_memory" ? "TIM-MARS memory" : r.stream);
    html += '<div class="evalCard">';
    html += '<div class="evalCardHeader"><span>' + title + '</span><span class="evalBadge ' + (unsafe ? 'evalBadgeUnsafe' : 'evalBadgeSafe') + '">' + (unsafe ? 'unsafe output' : 'no wrong target') + '</span></div>';
    html += '<div class="metricGrid">';
    html += metricBox("correct", n(r.correct_target_duration_s), n(r.correct_target_ratio), "good");
    html += metricBox("wrong", wrong, n(r.wrong_target_ratio), wrong > 0.001 ? "bad" : "neutral");
    html += metricBox("lost", n(r.lost_target_duration_s), n(r.lost_target_ratio), "neutral");
    html += '</div></div>';
  }}
  html += '</div>';
  var raw = rows.find(function(r) {{ return r.stream === "raw_target"; }});
  var tim = rows.find(function(r) {{ return r.stream === "tim_target_memory"; }});
  if (raw && tim) {{
    var dc = n(tim.correct_target_duration_s) - n(raw.correct_target_duration_s);
    var dw = n(tim.wrong_target_duration_s) - n(raw.wrong_target_duration_s);
    var dl = n(tim.lost_target_duration_s) - n(raw.lost_target_duration_s);
    html += '<div class="evalSummary"><b>Delta TIM - RAW:</b> correct ' + (dc >= 0 ? "+" : "") + fmt(dc) + ' s, wrong ' + (dw >= 0 ? "+" : "") + fmt(dw) + ' s, lost ' + (dl >= 0 ? "+" : "") + fmt(dl) + ' s.';
    html += dw > 0.001 ? '<br><span class="bad"><b>Safety verdict:</b> rejected, TIM introduces wrong-target output.</span>' : '<br><span class="good"><b>Safety verdict:</b> acceptable on wrong-target criterion.</span>';
    html += '</div>';
  }}
  document.getElementById("evalTable").innerHTML = html;
}}

async function evaluateBag() {{
  var bag = loadedBag || document.getElementById("bag").value;
  var ann = document.getElementById("ann").value || "";
  if (!bag) return alert("Select a bag first.");
  if (!ann) return alert("Select an annotation first.");

  document.getElementById("evalStatus").innerText = "evaluating...";
  document.getElementById("evalTable").innerHTML = "";
  var log = document.getElementById("log");
  log.style.display = "none";
  log.innerText = "";

  var res = await fetch("/api/evaluate", {{
    method:"POST",
    headers:{{"Content-Type":"application/json"}},
    body:JSON.stringify({{bag:bag, ann:ann}})
  }});
  var data = await res.json();

  if (!data.ok) {{
    document.getElementById("evalStatus").innerText = "failed";
    log.style.display = "block";
    log.innerText = (data.error || "error") + "\\n\\n" + (data.log || "");
    return;
  }}

  document.getElementById("evalStatus").innerText = "done";
  renderEval(data.rows || []);
}}




/* TIM annotation editor JS v4 */
window.annManualRows = [];
window.annSelectedRow = null;
window.annDirty = false;

function annStatusMsg(msg, cls) {{
  var el = document.getElementById("annSaveStatus");
  if (!el) {{
    el = document.createElement("span");
    el.id = "annSaveStatus";
    var btns = document.querySelector(".annotationButtons");
    if (btns) btns.appendChild(el);
  }}
  el.className = cls || "";
  el.innerText = msg || "";
}}

function annMarkDirty() {{
  window.annDirty = true;
  annStatusMsg("unsaved changes", "annDirty");
}}

function annCurrentBagName() {{
  var bag = document.getElementById("bag");
  if (!bag || !bag.value) return "";
  return bag.value.split("/").pop();
}}

function annNormaliseRow(row) {{
  var label = row.target_label || row.label || "CORRECT_TARGET";
  var visible = label === "CORRECT_TARGET";
  return {{
    bag_name: row.bag_name || annCurrentBagName(),
    start_s: String(row.start_s !== undefined ? row.start_s : "0.000"),
    end_s: String(row.end_s !== undefined ? row.end_s : "0.000"),
    target_label: label,
    target_visible: visible ? "true" : "false",
    correct_target_track_id: visible ? String(row.correct_target_track_id || row.target_id || "") : "",
    distractor_track_ids: String(row.distractor_track_ids || ""),
    event_type: String(row.event_type || row.event || "manual_interval"),
    notes: String(row.notes || "")
  }};
}}

function annGetFormRow() {{
  var label = document.getElementById("annLabel").value;
  var start = Number(document.getElementById("annStart").value);
  var end = Number(document.getElementById("annEnd").value);
  var visible = label === "CORRECT_TARGET";

  return annNormaliseRow({{
    bag_name: annCurrentBagName(),
    start_s: start.toFixed(3),
    end_s: end.toFixed(3),
    target_label: label,
    correct_target_track_id: visible ? document.getElementById("annTargetId").value.trim() : "",
    event_type: document.getElementById("annEvent").value,
    notes: document.getElementById("annNotes").value || ""
  }});
}}

function annValidateRow(row) {{
  var start = Number(row.start_s);
  var end = Number(row.end_s);

  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {{
    alert("Invalid interval: end must be greater than start.");
    return false;
  }}

  if (row.target_label === "CORRECT_TARGET" && String(row.correct_target_track_id).trim() === "") {{
    alert("CORRECT_TARGET needs a target ID.");
    return false;
  }}

  return true;
}}

function annEscapeHtml(x) {{
  return String(x || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}}

function annRenderRows() {{
  var host = document.getElementById("annRows");
  if (!host) return;

  if (!window.annManualRows.length) {{
    host.innerHTML = "<div style='padding:10px;'>No annotation rows loaded.</div>";
    return;
  }}

  var labelValues = ["CORRECT_TARGET", "TARGET_NOT_VISIBLE", "NO_TARGET_SELECTED"];
  var eventValues = [
    "manual_interval",
    "id_switch",
    "target_occluded",
    "target_exits_frame",
    "target_reappears",
    "uncertain",
    "clean_follow",
    "bad_follow",
    "crossing_ambiguity",
    "pre_selection"
  ];

  var html = "";
  html += "<table>";
  html += "<thead><tr>";
  html += "<th>#</th><th>start s</th><th>end s</th><th>label</th><th>target ID</th><th>event</th><th>notes</th><th>action</th>";
  html += "</tr></thead><tbody>";

  for (var i = 0; i < window.annManualRows.length; i++) {{
    var r = window.annManualRows[i];

    var labelOptions = "";
    for (var li = 0; li < labelValues.length; li++) {{
      var lv = labelValues[li];
      labelOptions += "<option value='" + lv + "'" + (r.target_label === lv ? " selected" : "") + ">" + lv + "</option>";
    }}

    var eventOptions = "";
    for (var ei = 0; ei < eventValues.length; ei++) {{
      var ev = eventValues[ei];
      eventOptions += "<option value='" + ev + "'" + (r.event_type === ev ? " selected" : "") + ">" + ev + "</option>";
    }}

    html += "<tr class='" + (window.annSelectedRow === i ? "active" : "") + "'>";
    html += "<td><button type='button' onclick='annSelectRow(" + i + ")'>" + (i + 1) + "</button></td>";
    html += "<td><input value='" + annEscapeHtml(r.start_s) + "' onchange='annEditCell(" + i + ", &quot;start_s&quot;, this.value)'></td>";
    html += "<td><input value='" + annEscapeHtml(r.end_s) + "' onchange='annEditCell(" + i + ", &quot;end_s&quot;, this.value)'></td>";
    html += "<td><select onchange='annEditCell(" + i + ", &quot;target_label&quot;, this.value)'>" + labelOptions + "</select></td>";
    html += "<td><input value='" + annEscapeHtml(r.correct_target_track_id) + "' onchange='annEditCell(" + i + ", &quot;correct_target_track_id&quot;, this.value)'></td>";
    html += "<td><select onchange='annEditCell(" + i + ", &quot;event_type&quot;, this.value)'>" + eventOptions + "</select></td>";
    html += "<td><input value='" + annEscapeHtml(r.notes) + "' onchange='annEditCell(" + i + ", &quot;notes&quot;, this.value)'></td>";
    html += "<td><button type='button' onclick='annDeleteRow(" + i + ")'>delete</button></td>";
    html += "</tr>";
  }}

  html += "</tbody></table>";
  host.innerHTML = html;
}}

function annSelectRow(i) {{
  var r = window.annManualRows[i];
  if (!r) return;

  window.annSelectedRow = i;
  document.getElementById("annStart").value = r.start_s;
  document.getElementById("annEnd").value = r.end_s;
  document.getElementById("annLabel").value = r.target_label;
  document.getElementById("annTargetId").value = r.correct_target_track_id;
  document.getElementById("annEvent").value = r.event_type;
  document.getElementById("annNotes").value = r.notes || "";
  annRenderRows();
}}

function annEditCell(i, field, value) {{
  if (!window.annManualRows[i]) return;

  window.annManualRows[i][field] = String(value);

  if (field === "target_label") {{
    window.annManualRows[i].target_visible = value === "CORRECT_TARGET" ? "true" : "false";
    if (value !== "CORRECT_TARGET") window.annManualRows[i].correct_target_track_id = "";
  }}

  window.annManualRows.sort(function(a, b) {{ return Number(a.start_s) - Number(b.start_s); }});
  annMarkDirty();
  annRenderRows();
}}

function annAddInterval() {{
  var row = annGetFormRow();
  if (!annValidateRow(row)) return;

  if (window.annSelectedRow !== null && window.annManualRows[window.annSelectedRow]) {{
    window.annManualRows[window.annSelectedRow] = row;
  }} else {{
    window.annManualRows.push(row);
  }}

  window.annManualRows.sort(function(a, b) {{ return Number(a.start_s) - Number(b.start_s); }});
  window.annSelectedRow = null;
  annMarkDirty();
  annRenderRows();
}}

function annDeleteRow(i) {{
  window.annManualRows.splice(i, 1);
  window.annSelectedRow = null;
  annMarkDirty();
  annRenderRows();
}}

function annDeleteActive() {{
  if (window.annSelectedRow !== null && window.annManualRows[window.annSelectedRow]) {{
    annDeleteRow(window.annSelectedRow);
    return;
  }}
  alert("Select a row in the table first.");
}}

async function annLoadSelected() {{
  var annSel = document.getElementById("ann");
  var path = annSel ? annSel.value : "";

  if (!path) {{
    alert("No selected annotation CSV.");
    return;
  }}

  var res = await fetch("/api/annotation/load", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{path: path}})
  }});

  if (!res.ok) {{
    alert("Failed to load CSV: " + await res.text());
    return;
  }}

  var data = await res.json();
  window.annManualRows = (data.rows || []).map(annNormaliseRow);
  window.annSelectedRow = null;
  window.annDirty = false;
  annStatusMsg("loaded selected CSV", "annSaved");
  annRenderRows();
}}

async function annSave() {{
  var outEl = document.getElementById("annOutPath");
  var out = outEl ? outEl.value.trim() : "";

  if (!out) {{
    alert("Output CSV path is empty.");
    return;
  }}

  if (!out.startsWith("docs/annotations/")) {{
    alert("Output path must be under docs/annotations/");
    return;
  }}

  if (!window.annManualRows.length) {{
    alert("No annotation rows to save.");
    return;
  }}

  for (var i = 0; i < window.annManualRows.length; i++) {{
    if (!annValidateRow(window.annManualRows[i])) return;
  }}

  var res = await fetch("/api/annotation/save", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{
      path: out,
      rows: window.annManualRows
    }})
  }});

  var txt = await res.text();

  if (!res.ok) {{
    alert("Save failed: " + txt);
    return;
  }}

  window.annDirty = false;
  annStatusMsg("saved to Pi", "annSaved");
  alert("Saved annotation CSV:\\n" + out);
}}

window.addEventListener("DOMContentLoaded", function() {{
  onBagChange();
}});
window.addEventListener("error", function(e) {{ fail(e.message + "\\n" + e.filename + ":" + e.lineno); }});
window.addEventListener("unhandledrejection", function(e) {{ fail(e.reason); }});

</script>


</body>
</html>"""
    return html


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
