#!/usr/bin/env python3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import argparse
import json
import html as html_lib
import csv
import re
import subprocess
import sys
from pathlib import Path
from tim_ui_discovery import discover_annotations as shared_discover_annotations, discover_bags as shared_discover_bags
from tim_ui_annotations import (
    ANNOTATION_EVENT_TYPES,
    ANNOTATION_FIELDS,
    load_annotation_rows,
    save_annotation_rows,
)
import uvicorn

# Import the original backend module, then copy its registered API routes.
# This keeps /clean isolated from the broken old HTML page.
import tim_ui_backend as backend

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



@app.post("/api/annotation/load")
async def annotation_load_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    if not path_text:
        return {"ok": False, "error": "No annotation path provided."}

    try:
        rel, rows = load_annotation_rows(path_text, REPO_ROOT)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {
        "ok": True,
        "path": str(rel),
        "rows": rows,
        "fields": ANNOTATION_FIELDS,
        "event_types": ANNOTATION_EVENT_TYPES,
    }


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
        rel, normalised = save_annotation_rows(path_text, rows, REPO_ROOT)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {
        "ok": True,
        "path": str(rel),
        "rows": len(normalised),
        "message": f"Saved {len(normalised)} annotation intervals to {rel}",
    }



@app.get("/")
def root():
    return RedirectResponse(url="/clean")

@app.get("/clean", response_class=HTMLResponse)
def clean_ui():
    bags = shared_discover_bags(REPO_ROOT)
    annotations = shared_discover_annotations(REPO_ROOT)
    bags_json = json.dumps(bags)
    annotations_json = json.dumps(annotations)

    template_path = Path(__file__).with_name("static") / "tim_clean_ui.html"
    html = template_path.read_text()
    html = html.replace("__BAGS_JSON__", bags_json)
    html = html.replace("__ANNOTATIONS_JSON__", annotations_json)
    return HTMLResponse(html)


def _load_bag_inventory_for_ui() -> list[dict]:
    inv = REPO_ROOT / "docs" / "data" / "catalogue" / "bag_inventory.yaml"
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
            "bags/source/curated/",
            "bags/annotation_inputs/",
            "bags/review/tim_queues/TIM_EVAL_QUEUE/",
            "bags/reference/tim_good/",
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

    bags = shared_discover_bags(REPO_ROOT)
    bags_json = json.dumps(bags)
    annotation_options = "\n".join(
        f'<option value="{html_lib.escape(a)}" title="{html_lib.escape(a)}">{html_lib.escape(annotation_label(a))}</option>'
        for a in annotations
    )

    annotations = shared_discover_annotations(REPO_ROOT)
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
<h3>3. Visual annotation tools</h3>

<div class="annotationBox">
  <h3>4. Annotation editor</h3>
  <div class="hint">
    Creates evaluator-compatible interval CSVs. Use the viewer to find the correct time range, then set start/end and target ID.
  </div>

  <div class="annotationControls">
    <label>output CSV
      <input id="annOutPath" value="docs/data/annotations/ui_created/new_annotation.csv">
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
              <option value="clean_visible">Clean visible</option>
              <option value="target_absent">Target absent</option>
              <option value="reentry">Re-entry</option>
              <option value="occlusion_ambiguity">Occlusion / ambiguity</option>
              <option value="id_switch_fragmentation">ID switch / fragmentation</option>
              <option value="other">Other</option>
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
    <button onclick="annNewInterval()">+ New interval</button>
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
  var label = getValueOrDefault("annLabel", "CORRECT_TARGET");
  var start = Number(getValueOrDefault("annStart", "0"));
  var end = Number(getValueOrDefault("annEnd", "0"));
  var visible = label === "CORRECT_TARGET";

  return annNormaliseRow({{
    bag_name: annCurrentBagName(),
    start_s: start.toFixed(3),
    end_s: end.toFixed(3),
    target_label: label,
    correct_target_track_id: visible ? getValueOrDefault("annTargetId", "").trim() : "",
    event_type: getValueOrDefault("annEvent", "manual_interval"),
    notes: getValueOrDefault("annNotes", "created in TIM clean UI") || ""
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
  setValueIfPresent("annStart", r.start_s);
  setValueIfPresent("annEnd", r.end_s);
  setValueIfPresent("annLabel", r.target_label);
  setValueIfPresent("annTargetId", r.correct_target_track_id);
  setValueIfPresent("annEvent", r.event_type);
  setValueIfPresent("annNotes", r.notes || "");
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

  if (!out.startsWith("docs/data/annotations/")) {{
    alert("Output path must be under docs/data/annotations/");
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
    parser.add_argument("--port", type=int, default=8888)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
