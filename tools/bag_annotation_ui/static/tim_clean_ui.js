function setValueIfPresent(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value;
}

function getValueOrDefault(id, fallback) {
  const el = document.getElementById(id);
  return el ? el.value : fallback;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

let allBags = __BAGS_JSON__;
let allAnnotations = __ANNOTATIONS_JSON__;
let loadedFrames = 0;
let loadedDuration = 0;
let loadedBag = "";
let currentBagFilter = "";
let playing = false;
let timer = null;

let rawFrameCache = [];
let timFrameCache = [];
let rawDecodedCache = [];
let timDecodedCache = [];
let preloadReady = false;
let preloadInProgress = false;
let preloadToken = 0;
let loadedCacheToken = 0;

function paperNeedEmoji(path) {
  const l = String(path || "").toLowerCase();

  // First-choice paper visualization bags / aliases.
  if (l.includes("video__paper_seq01") || l.includes("two_person_crossing")) return "🎯";
  if (l.includes("video__paper_seq03") || l.includes("dense_group_ambiguity")) return "🎯";
  if (l.includes("det_app_v5_bytetrack_seq03_target1")) return "🎯";
  if (l.includes("det_app_v5_bytetrack_seq04_target5")) return "🎯";

  // Annotation aliases are useful, but they are usually not the final TIM-MARS replay.
  if (l.includes("annotate__")) return "⭐";

  // Candidate/replay alternatives.
  if (l.includes("/replay/") || l.includes("__tim_") || l.includes("memory_tim")) return "🧪";

  // Source/archive bags are useful for provenance, not first-choice figure export.
  if (l.includes("/source/") || l.includes("/archive/")) return "🗄️";

  return "";
}

function label(path) {
  const l = String(path || "").toLowerCase();
  const rawPath = String(path || "");
  const baseName = rawPath.split("/").filter(Boolean).slice(-1)[0] || rawPath;

  let p = "bag";
  if (l.includes("/final_tim_safety_eval_2026-06-30/memory_only/")) p = "memory-only";
  else if (l.includes("/source/")) p = "source";
  else if (l.includes("/reference/")) p = "reference";
  else if (l.includes("/eval_matrix/")) p = "eval";
  else if (l.includes("/annotation_inputs/")) p = "annotation";

  let name = baseName;
  if (l.includes("may") || l.includes("2026-05-14")) name = "May hard re-entry";

  if (l.includes("video__paper_seq01") || l.includes("two_person_crossing")) name = "PAPER Seq. 1 two-person crossing";
  else if (l.includes("video__paper_seq02") || l.includes("distractor_reentry")) name = "PAPER Seq. 2 distractor re-entry";
  else if (l.includes("video__paper_seq03") || l.includes("dense_group_ambiguity")) name = "PAPER Seq. 3 dense-group ambiguity";
  else if (l.includes("seq01")) name = "seq01 clean four-person";
  else if (l.includes("seq02") || l.includes("target_reentry")) name = "seq02 target re-entry";
  else if (l.includes("seq03") || l.includes("crossing_ambiguity")) name = "seq03 crossing ambiguity";
  else if (l.includes("seq04") || l.includes("occlusion_no_exit")) name = "seq04 occlusion no-exit";

  if (l.includes("annotate__")) {
    const base = path.split("/").pop();
    return paperNeedEmoji(path) + " ANNOTATE | " + base
      .replace(/^ANNOTATE__/, "")
      .replace(/__/g, " | ")
      .replace(/_/g, " ");
  }

  if (l.includes("/final_tim_safety_eval_2026-06-30/memory_only/")) {
    name = name + " | " + baseName;
  }

  let tim = "";
  if (l.includes("raw_vs_tim")) tim = " | raw vs TIM";
  else if (l.includes("tim_mars") || l.includes("target_memory") || l.includes("memory")) tim = " | TIM-MARS";
  else if (l.includes("tim_off") || l.includes("raw")) tim = " | raw";

  const emoji = paperNeedEmoji(path);
  return (emoji ? emoji + " " : "") + "[" + p + "] | " + name + tim;
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

  // Paper video aliases are intentionally renamed for the paper narrative.
  // Do not let PAPER_SEQ01/02/03 accidentally match the old June seq01/02/03 annotations.
  if (b.includes("video__paper_seq01") || b.includes("det_app_v5_bytetrack_may_target1")) {
    if (a.includes("may_hard_reentry") && a.includes("bytetrack_hard_reentry")) return 1000;
    if (a.includes("hard_reentry") && a.includes("bytetrack")) return 900;
    return 0;
  }

  if (b.includes("video__paper_seq02") || b.includes("det_app_v5_bytetrack_seq03_target1")) {
    if (a.includes("june_hard_sequences/seq03_bytetrack.csv")) return 1000;
    if (a.includes("seq03") && a.includes("bytetrack")) return 900;
    return 0;
  }

  if (b.includes("video__paper_seq03") || b.includes("det_app_v5_bytetrack_seq04_target5")) {
    if (a.includes("june_hard_sequences/seq04_bytetrack.csv")) return 1000;
    if (a.includes("seq04") && a.includes("bytetrack")) return 900;
    return 0;
  }

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
  none.textContent = "no annotation";
  none.selected = true;
  sel.appendChild(none);

  for (const ann of allAnnotations) {
    const opt = document.createElement("option");
    opt.value = ann;
    opt.textContent = annotationLabel(ann);
    sel.appendChild(opt);
  }
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



function bagTokens(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/seq0([1-9])/g, "seq$1 seq0$1")
    .replace(/paper_seq0([1-9])/g, "paper seq$1 paper_seq0$1")
    .replace(/[_/.-]+/g, " ");
}

function bagMatchesFilter(bag, filterText) {
  const f = String(filterText || "").trim().toLowerCase();
  if (!f) return true;

  const hay = bagTokens(bag + " " + label(bag));
  const terms = f.split(/\s+/).filter(Boolean).map(t => bagTokens(t).trim());

  return terms.every(term => {
    if (!term) return true;
    return hay.includes(term);
  });
}

function bagPaperScore(bag) {
  const s = bagTokens(bag + " " + label(bag));
  let score = 0;

  if (s.includes("annotation inputs")) score += 30;
  if (s.includes("annotate")) score += 25;
  if (s.includes("video")) score += 20;
  if (s.includes("view")) score += 12;

  if (s.includes("paper")) score += 30;
  if (s.includes("seq1") || s.includes("seq01") || s.includes("crossing")) score += 25;
  if (s.includes("seq2") || s.includes("seq02") || s.includes("reentry") || s.includes("re entry")) score += 20;
  if (s.includes("seq3") || s.includes("seq03") || s.includes("dense") || s.includes("group")) score += 25;
  if (s.includes("seq4") || s.includes("seq04")) score += 18;

  if (s.includes("bytetrack")) score += 18;
  if (s.includes("tim mars") || s.includes("tim")) score += 12;
  if (s.includes("final")) score += 10;

  if (s.includes("bad") || s.includes("trash")) score -= 40;

  return score;
}

function renderBagOptions(filterText = "") {
  const sel = document.getElementById("bag");
  const status = document.getElementById("bagFilterStatus");
  if (!sel) {
    console.warn("bag select not found");
    return;
  }

  const previous = sel.value;
  const f = String(filterText || "").trim();

  let bags = Array.isArray(allBags) ? allBags.slice() : [];

  if (f) {
    bags = bags.filter(b => bagMatchesFilter(b, f));
  }

  bags.sort((a, b) => {
    const ds = bagPaperScore(b) - bagPaperScore(a);
    if (ds !== 0) return ds;
    return String(label(a)).localeCompare(String(label(b)));
  });

  sel.innerHTML = "";

  if (bags.length === 0) {
    const o = document.createElement("option");
    o.value = "";
    o.text = "No bags match: " + f;
    sel.add(o);
  } else {
    for (const b of bags) {
      const o = document.createElement("option");
      o.value = b;
      o.text = label(b) + "  —  " + b;
      o.title = b;
      sel.add(o);
    }
  }

  if (previous && bags.includes(previous)) {
    sel.value = previous;
  } else if (bags.length > 0) {
    sel.selectedIndex = 0;
  }

  if (status) {
    status.innerText = bags.length + " / " + (Array.isArray(allBags) ? allBags.length : 0) + " bags shown";
  }

}

function applyBagFilter() {
  const el = document.getElementById("bagQuickFilter");
  currentBagFilter = el ? el.value : "";
  renderBagOptions(currentBagFilter);
}

function setPaperBagFilter() {
  const el = document.getElementById("bagQuickFilter");
  currentBagFilter = "paper";
  if (el) el.value = currentBagFilter;
  renderBagOptions(currentBagFilter);
}

function clearBagFilter() {
  const el = document.getElementById("bagQuickFilter");
  currentBagFilter = "";
  if (el) el.value = "";
  renderBagOptions("");
}

function wireBagFinder() {
  const el = document.getElementById("bagQuickFilter");
  if (!el || el.dataset.wired === "1") return;

  el.dataset.wired = "1";
  el.addEventListener("input", () => {
    currentBagFilter = el.value || "";
    renderBagOptions(currentBagFilter);
  });
  el.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      applyBagFilter();
    }
  });
}

async function loadList() {
  const res = await fetch("/api/list?ts=" + Date.now());
  const data = await res.json();

  allBags = data.bags || [];
  allAnnotations = data.annotations || [];

  wireBagFinder();
  renderBagOptions(currentBagFilter || "");
  const bagEl = document.getElementById("bag");
  if (bagEl && bagEl.options.length > 0 && !bagEl.value) {
    bagEl.selectedIndex = 0;
  }

  const annEl = document.getElementById("annotation");
  if (annEl) {
    renderAnnotationsForBag(bagEl ? bagEl.value : "");
  }

  const status = document.getElementById("status");
  if (status) {
    status.innerText = "ready, " + allBags.length + " bags, " + allAnnotations.length + " annotations";
  }
}

function renderBags() {
  renderBagOptions(currentBagFilter || "");
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
    document.getElementById("tracks").checked = true;
    return;
  }

  document.getElementById("rawTitle").innerText = "RAW selector output /target";
  document.getElementById("timTitle").innerText = "TIM-MARS output /target_memory_mars";
}

function frameUrl(idx, side) {
  const q = new URLSearchParams();
  q.set("idx", String(idx));
  q.set("clean", "1");
  q.set("cache_token", String(loadedCacheToken || preloadToken || Date.now()));

  if (side === "raw") {
    q.set("draw_raw", "1");
    q.set("draw_tim", "0");
  } else if (side === "tim") {
    q.set("draw_raw", "0");
    q.set("draw_tim", "1");
  } else {
    q.set("draw_raw", "1");
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
  loadedCacheToken = Date.now();

  document.getElementById("status").innerText = "reloading view cache...";
  await preloadAllFrames(preloadToken);

  if (preloadReady) {
    document.getElementById("status").innerText = "ready";
    document.getElementById("playBtn").disabled = false;
    document.getElementById("progress").disabled = false;
    updateFrame();
  }
}


function currentFrameIndex() {
  const p = document.getElementById("progress");
  if (!p) return 0;
  return parseInt(p.value || "0");
}

function currentPaperFrameList() {
  const input = document.getElementById("paperFigureFrames");
  if (!input) return [];
  return String(input.value || "")
    .split(",")
    .map(x => x.trim())
    .filter(Boolean);
}

function refreshPaperFrameDraft() {
  const badge = document.getElementById("paperFrameDraft");
  const input = document.getElementById("paperFigureFrames");
  if (!badge || !input) return;
  const value = String(input.value || "").trim();
  badge.innerText = value ? "frames: " + value : "frames: none";
}

function addCurrentFrameToPaperList() {
  const idx = currentFrameIndex();
  const input = document.getElementById("paperFigureFrames");
  if (!input) {
    alert("Paper contact-sheet export controls were not found. Scroll down and check that the export panel exists.");
    return;
  }

  const frames = currentPaperFrameList();
  const value = String(idx);

  if (!frames.includes(value)) {
    frames.push(value);
  }

  input.value = frames.join(",");
  refreshPaperFrameDraft();
}

function clearPaperFrameList() {
  const input = document.getElementById("paperFigureFrames");
  if (input) input.value = "";
  refreshPaperFrameDraft();
}


function updateFrame() {
  const idx = parseInt(document.getElementById("progress").value || "0");
  const t = loadedFrames > 1 ? idx / (loadedFrames - 1) * loadedDuration : 0;

  document.getElementById("time").innerText = "frame " + idx + " / " + Math.max(0, loadedFrames - 1) + " | t=" + fmt(t) + " / " + fmt(loadedDuration);
  refreshPaperFrameDraft();

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
    tim_preset: document.getElementById("timPreset").value || "legacy",
    rate: parseFloat(document.getElementById("rate").value || "1.0"),
    absence_min_total: 0.45,
    absence_min_distance: 0.25,
    absence_min_scale: 0.35,
    absence_min_similarity: 0.65,
    absence_appearance_margin: 0.20,
    absence_confirm_frames: 3,
    rank_aware_lost_min_total: 0.40,
    rank_aware_lost_min_geom: 0.10,
    rank_aware_lost_min_app: 0.05,
    rank_aware_lost_app_margin: 0.03,
    rank_aware_confirm_frames: 1
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



function defaultVideoNameForBag() {
  const b = loadedBag || document.getElementById("bag").value || "tim_mars_video_export";
  const base = b.split("/").pop()
    .replace(/^VIDEO__/, "")
    .replace(/[^A-Za-z0-9_.-]+/g, "_")
    .replace(/_+$/g, "");
  return (base || "tim_mars_video_export") + ".mp4";
}

async function exportMp4() {
  const log = document.getElementById("videoExportLog");
  const link = document.getElementById("videoDownload");

  if (link) {
    link.style.display = "none";
    link.href = "#";
  }

  if (!loadedBag && !document.getElementById("bag").value) {
    alert("Load a bag first.");
    return;
  }

  let name = document.getElementById("videoName").value.trim();
  if (!name || name === "tim_mars_video_export.mp4") {
    name = defaultVideoNameForBag();
    document.getElementById("videoName").value = name;
  }
  if (!name.toLowerCase().endsWith(".mp4")) {
    name += ".mp4";
  }

  const payload = {
    out: "reports/ui_video_exports/" + name,
    draw_detections: document.getElementById("videoDetections").checked,
    draw_tracks: document.getElementById("videoTracks").checked,
    draw_raw: document.getElementById("videoRaw").checked,
    draw_tim: document.getElementById("videoTim").checked,
    only_ids: document.getElementById("videoOnlyIds").value || "",
    fps: parseFloat(document.getElementById("videoFps").value || "20"),
    clean: document.getElementById("videoClean").checked,
    draw_reference: document.getElementById("videoReference").checked,
    comparison: document.getElementById("videoComparison").checked,
    paper_overlay: document.getElementById("videoPaperOverlay").checked
  };

  if (log) {
    log.innerText = "Exporting MP4... this can take a while.\n" + JSON.stringify(payload, null, 2);
  }

  try {
    const res = await fetch("/api/export_mp4", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!data.ok) {
      if (log) {
        log.innerText = "ERROR:\n" + JSON.stringify(data, null, 2);
      }
      return;
    }

    const url = data.download_url;

    if (link) {
      link.href = url;
      link.style.display = "inline-block";
      link.innerText = "Download " + data.path.split("/").pop();
    }

    if (log) {
      log.innerText =
        "Export done.\n" +
        "path: " + data.path + "\n" +
        "download: " + window.location.origin + url;
    }
  } catch (err) {
    if (log) {
      log.innerText = String(err);
    }
  }
}



function defaultFigureNameForBag() {
  const b = loadedBag || document.getElementById("bag").value || "seq_contact_sheet";
  const base = b.split("/").pop()
    .replace(/^VIDEO__/, "")
    .replace(/^VIEW__/, "")
    .replace(/^ANNOTATE__/, "")
    .replace(/[^A-Za-z0-9_.-]+/g, "_")
    .replace(/_+$/g, "");
  return (base || "seq_contact_sheet") + "_contact_sheet.jpg";
}

async function exportContactSheet() {
  const log = document.getElementById("paperFigureLog");
  const link = document.getElementById("paperFigureDownload");

  if (link) {
    link.style.display = "none";
    link.href = "#";
  }

  if (!loadedBag && !document.getElementById("bag").value) {
    alert("Load a bag first.");
    return;
  }

  let name = document.getElementById("paperFigureName").value.trim();
  if (!name || name === "seq_contact_sheet.jpg") {
    name = defaultFigureNameForBag();
    document.getElementById("paperFigureName").value = name;
  }
  if (!name.toLowerCase().endsWith(".jpg") && !name.toLowerCase().endsWith(".jpeg") && !name.toLowerCase().endsWith(".png")) {
    name += ".jpg";
  }

  const payload = {
    out: "figures/" + name,
    frames: document.getElementById("paperFigureFrames").value || "",
    cols: parseInt(document.getElementById("paperFigureCols").value || "3"),
    crop: document.getElementById("paperFigureCrop").checked,
    crop_pad: parseInt(document.getElementById("paperFigureCropPad").value || "80"),
    panel_width: parseInt(document.getElementById("paperFigurePanelWidth").value || "520"),
    draw_reference: document.getElementById("paperFigureReference").checked,
    label_mode: "time"
  };

  if (!payload.frames.trim()) {
    alert("Enter frame indices, for example: 120,160,200,240,280,320");
    return;
  }

  if (log) {
    log.innerText = "Exporting contact sheet...\n" + JSON.stringify(payload, null, 2);
  }

  try {
    const res = await fetch("/api/export_contact_sheet", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!data.ok) {
      if (log) log.innerText = "ERROR:\n" + JSON.stringify(data, null, 2);
      return;
    }

    if (link) {
      link.href = data.download_url;
      link.style.display = "inline-block";
      link.innerText = "Download " + data.path.split("/").pop();
    }

    if (log) {
      log.innerText =
        "Export done.\n" +
        "path: " + data.path + "\n" +
        "download: " + window.location.origin + data.download_url;
    }
  } catch (err) {
    if (log) log.innerText = String(err);
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
  showFrontendError("JavaScript error: " + e.message + "\\n" + e.filename + ":" + e.lineno);
});

window.addEventListener("unhandledrejection", function(e) {
  showFrontendError("Unhandled promise rejection:\n" + String(e.reason));
});


let annotationRows = [];
let activeAnnotationIdx = -1;
let activeAnnotationIndex = -1;

function currentTimeS() {
  const idx = parseInt(document.getElementById("progress").value || "0");
  return loadedFrames > 1 ? idx / (loadedFrames - 1) * loadedDuration : 0;
}

function annSetStartNow() {
  setValueIfPresent("annStart", currentTimeS().toFixed(3));
}

function annSetEndNow() {
  setValueIfPresent("annEnd", currentTimeS().toFixed(3));
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




function selectAnnotation(idx) {
  idx = Number(idx);
  if (!Number.isFinite(idx)) return;
  activeAnnotationIdx = idx;

  if (Array.isArray(annotationRows) && annotationRows[idx]) {
    const r = annotationRows[idx];
    setValueIfPresent("annStart", r.start_s || "");
    setValueIfPresent("annEnd", r.end_s || "");
    setValueIfPresent("annTargetId", r.correct_target_track_id || "");
    setValueIfPresent("annEvent", normaliseRowEventType(r.event_type || "", String(r.target_visible || "").toLowerCase() === "true"));
    setValueIfPresent("annNotes", r.notes || "");
  }

  renderAnnotationTable();
}

function normaliseRowEventType(value, visible=true) {
  const legacy = {
    manual_interval: "clean_visible",
    visible_id_interval: "clean_visible",
    target_not_visible: "target_absent",
    not_visible: "target_absent",
    occlusion: "occlusion_ambiguity",
    crossing_ambiguity: "occlusion_ambiguity",
    distractor_confusion: "occlusion_ambiguity",
  };
  const allowed = [
    "clean_visible",
    "target_absent",
    "reentry",
    "occlusion_ambiguity",
    "id_switch_fragmentation",
    "other",
  ];
  let v = String(value || "").trim();
  v = legacy[v] || v;
  if (!allowed.includes(v)) v = visible ? "clean_visible" : "target_absent";
  if (!visible && ["clean_visible", "reentry", "id_switch_fragmentation"].includes(v)) {
    v = "target_absent";
  }
  return v;
}


function newAnnotationInterval() {
  activeAnnotationIdx = -1;
  activeAnnotationIndex = -1;

  const startEl = document.getElementById("annStart") || document.getElementById("startS") || document.getElementById("start_s");
  const endEl = document.getElementById("annEnd") || document.getElementById("endS") || document.getElementById("end_s");
  const idEl = document.getElementById("annTargetId") || document.getElementById("targetId") || document.getElementById("target_id");
  const eventEl = document.getElementById("annEventType") || document.getElementById("eventType") || document.getElementById("event_type");
  const visibleEl = document.getElementById("annVisible") || document.getElementById("targetVisible") || document.getElementById("visible");

  // Try to use current viewer time if available; otherwise keep current values.
  let t = null;
  try {
    if (typeof currentTimeS !== "undefined") t = Number(currentTimeS);
    else if (typeof currentTime !== "undefined") t = Number(currentTime);
    else if (typeof state !== "undefined" && state && state.tRel !== undefined) t = Number(state.tRel);
  } catch (_) {}

  if (Number.isFinite(t)) {
    if (startEl) startEl.value = t.toFixed(3);
    if (endEl) endEl.value = (t + 1.000).toFixed(3);
  } else {
    if (startEl && !startEl.value) startEl.value = "0.000";
    if (endEl && !endEl.value) endEl.value = "1.000";
  }

  if (idEl) idEl.value = "";
  if (visibleEl) visibleEl.checked = true;
  if (eventEl) eventEl.value = "clean_visible";

  if (typeof annRenderRows === "function") annRenderRows();
  if (typeof renderAnnotationTable === "function") renderAnnotationTable();
  if (typeof renderAnnotations === "function") renderAnnotations();
}

function deleteAnnotationRow(idx) {
  idx = Number(idx);
  if (!Number.isFinite(idx)) return;
  if (!Array.isArray(annotationRows)) return;
  if (idx < 0 || idx >= annotationRows.length) return;

  annotationRows.splice(idx, 1);

  if (annotationRows.length === 0) {
    activeAnnotationIdx = -1;
  } else {
    activeAnnotationIdx = Math.min(Math.max(0, activeAnnotationIdx), annotationRows.length - 1);
  }

  renderAnnotationTable();
}


function editAnnotationCell(idx, key, value) {
  if (idx < 0 || idx >= annotationRows.length) return;

  annotationRows[idx][key] = value;

  if (key === "start_s" || key === "end_s") {
    annotationRows[idx][key] = Number(value).toFixed(3);
  }

  if (key === "correct_target_track_id") {
    annotationRows[idx][key] = String(value || "").trim();
  }

  activeAnnotationIndex = idx;
  renderAnnotations();

  const start = document.getElementById("annStart");
  const end = document.getElementById("annEnd");
  const tid = document.getElementById("annTargetId");
  if (start) start.value = annotationRows[idx].start_s || "";
  if (end) end.value = annotationRows[idx].end_s || "";
  if (tid) tid.value = annotationRows[idx].correct_target_track_id || "";
}


function renderAnnotationTable() {
  return annRenderRows();
}

function renderAnnotations() {
  return annRenderRows();
}

function annRenderRows() {
  const host = document.getElementById("annRows");
  const status = document.getElementById("annStatus");
  if (!host) return;

  annotationRows.sort((a, b) => parseFloat(a.start_s || 0) - parseFloat(b.start_s || 0));

  if (status) {
    status.innerText = annotationRows.length + " annotation intervals loaded.";
  }

  if (!annotationRows.length) {
    host.innerHTML = "<div class='annEmpty'>No annotation intervals loaded.</div>";
    return;
  }

  let html = "";
  html += "<div class='annTableWrap'>";
  html += "<table class='annTable editableAnnTable'>";
  html += "<thead><tr>";
  html += "<th class='annColSmall'>#</th>";
  html += "<th>start s</th>";
  html += "<th>end s</th>";
  html += "<th>duration</th>";
  html += "<th>target ID</th>";
  html += "<th>visible</th>";
  html += "<th>event</th><th>action</th>";
  html += "</tr></thead><tbody>";

  annotationRows.forEach((r, idx) => {
    const start = Number(r.start_s || 0);
    const end = Number(r.end_s || 0);
    const duration = Math.max(0, end - start);
    const visible = String(r.target_visible || "").toLowerCase() === "true";
    const active = idx === activeAnnotationIndex ? " active" : "";

    html += "<tr class='" + active + "' onclick='selectAnnotation(" + idx + ")'>";
    html += "<td class='annIndex'>" + idx + "</td>";
    html += "<td><input class='annCellInput annNumInput' type='number' step='0.001' value='" + start.toFixed(3) + "' onchange='editAnnotationCell(" + idx + ", &quot;start_s&quot;, this.value)' onclick='event.stopPropagation()'></td>";
    html += "<td><input class='annCellInput annNumInput' type='number' step='0.001' value='" + end.toFixed(3) + "' onchange='editAnnotationCell(" + idx + ", &quot;end_s&quot;, this.value)' onclick='event.stopPropagation()'></td>";
    html += "<td class='annNum annDuration'>" + duration.toFixed(3) + "</td>";
    html += "<td><input class='annCellInput annIdInput' type='number' step='1' value='" + escapeHtml(String(r.correct_target_track_id || "")) + "' onchange='editAnnotationCell(" + idx + ", &quot;correct_target_track_id&quot;, this.value)' onclick='event.stopPropagation()'></td>";
    html += "<td class='annVisibleCell'><label class='annCheckLabel'><input type='checkbox' " + (visible ? "checked" : "") + " onchange='editAnnotationCell(" + idx + ", &quot;target_visible&quot;, this.checked ? &quot;true&quot; : &quot;false&quot;)' onclick='event.stopPropagation()'> visible</label></td>";
    html += "<td><select class='annCellInput annEventSelect' onchange='editAnnotationCell(" + idx + ", &quot;event_type&quot;, this.value)' onclick='event.stopPropagation()'>";
    const eventOptions = [
      ["clean_visible", "Clean visible"],
      ["target_absent", "Target absent"],
      ["reentry", "Re-entry"],
      ["occlusion_ambiguity", "Occlusion / ambiguity"],
      ["id_switch_fragmentation", "ID switch / fragmentation"],
      ["other", "Other"],
    ];
    const legacyEventMap = {
      manual_interval: "clean_visible",
      visible_id_interval: "clean_visible",
      target_not_visible: "target_absent",
      not_visible: "target_absent",
    };
    let currentEvent = String(r.event_type || "").trim();
    currentEvent = legacyEventMap[currentEvent] || currentEvent;
    if (!eventOptions.map(ev => ev[0]).includes(currentEvent)) {
      currentEvent = visible ? "clean_visible" : "target_absent";
    }
    for (const ev of eventOptions) {
      html += "<option value='" + escapeHtml(ev[0]) + "'" + (currentEvent === ev[0] ? " selected" : "") + ">" + escapeHtml(ev[1]) + "</option>";
    }
    html += "</select></td>";
    html += "<td><button class='smallBtn dangerBtn' onclick='deleteAnnotationRow(" + idx + "); event.stopPropagation();'>delete</button></td>";
    html += "</tr>";
  });

  html += "</tbody></table></div>";
  host.innerHTML = html;
}

function annSelectRow(i) {
  activeAnnotationIndex = i;
  const r = annotationRows[i];
  if (!r) return;

  setValueIfPresent("annStart", Number(r.start_s).toFixed(3));
  setValueIfPresent("annEnd", Number(r.end_s).toFixed(3));
  setValueIfPresent("annTargetId", r.correct_target_track_id || "");
  setValueIfPresent("annLabel", r.target_label || "CORRECT_TARGET");
  setValueIfPresent("annEvent", r.event_type || "manual_interval");
  setValueIfPresent("annNotes", r.notes || "");

  annRenderRows();
}


function annNewInterval() {
  activeAnnotationIdx = -1;
  activeAnnotationIndex = -1;

  let t = null;
  try {
    const slider = document.getElementById("frameSlider");
    if (slider && window.frameTimes && window.frameTimes.length) {
      const idx = Number(slider.value || 0);
      t = Number(window.frameTimes[idx] || 0);
    }
  } catch (_) {}

  try {
    if (!Number.isFinite(t) && typeof currentTimeS !== "undefined") t = Number(currentTimeS);
    if (!Number.isFinite(t) && typeof currentTime !== "undefined") t = Number(currentTime);
    if (!Number.isFinite(t) && typeof state !== "undefined" && state && state.tRel !== undefined) t = Number(state.tRel);
  } catch (_) {}

  if (!Number.isFinite(t)) {
    const startEl = document.getElementById("annEnd") || document.getElementById("annStart");
    t = Number(startEl && startEl.value ? startEl.value : 0);
  }

  const start = Number.isFinite(t) ? t : 0;
  const end = start + 1.000;

  setValueIfPresent("annStart", start.toFixed(3));
  setValueIfPresent("annEnd", end.toFixed(3));
  setValueIfPresent("annTargetId", "");
  setValueIfPresent("annLabel", "CORRECT_TARGET");
  setValueIfPresent("annEvent", "clean_visible");

  const eventEl = document.getElementById("annEventType") || document.getElementById("eventType") || document.getElementById("event_type");
  if (eventEl) eventEl.value = "clean_visible";

  const visibleEl = document.getElementById("annVisible") || document.getElementById("targetVisible") || document.getElementById("visible");
  if (visibleEl) visibleEl.checked = true;

  annRenderRows();
}

function annAddInterval() {
  const label = getValueOrDefault("annLabel", "CORRECT_TARGET");
  const start = parseFloat(getValueOrDefault("annStart", "0") || "0");
  const end = parseFloat(getValueOrDefault("annEnd", "0") || "0");
  const targetId = getValueOrDefault("annTargetId", "").trim();

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
    event_type: getValueOrDefault("annEvent", "manual_interval") || "manual_interval",
    notes: getValueOrDefault("annNotes", "created in TIM clean UI") || "created in TIM clean UI"
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
  setValueIfPresent("annCsv", ann.replace(".csv", "_edited.csv"));
  document.getElementById("annStatus").innerText = "Loaded " + annotationRows.length + " intervals from " + ann;
  annRenderRows();
}

async function annSave() {
  const outPath = getValueOrDefault("annCsv", "").trim();
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
