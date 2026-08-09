// Issue #25 physical-reference bbox annotation mode.
//
// Deliberately a separate file from tim_clean_ui.js: it adds a new UI mode
// without touching the legacy tracker-ID annotation workflow's code. It
// reuses tim_clean_ui.js's existing bag-loading, frame-stepping, and
// frame-time globals (loadedFrames, loadedBag, frameTimesS,
// currentFrameIndex(), currentTimeS()) rather than duplicating them.
//
// Core invariant, enforced by construction, not just convention: this file
// never reads or sends a tracker ID as part of the saved physical-reference
// artifact. Tracker/detection overlays may be drawn on the canvas for
// visual context only (via /frame.jpg's existing draw_tracks param); they
// are pixels in a JPEG, never serialized into physicalRefSamples.
//
// Coordinate contract: the canvas's internal pixel buffer
// (canvas.width/height) is set to the loaded frame's *natural* pixel
// dimensions the moment it loads (see updatePhysicalRefFrame). A mouse
// event is first converted from CSS/display pixels to that buffer's pixel
// space using the ratio between the buffer size and the canvas element's
// on-screen rendered size (getBoundingClientRect); because the buffer size
// already equals the source image size, that conversion *is* the
// display-to-source mapping in one step. Saved boxes are therefore always
// source-image pixels, never raw display/CSS coordinates, regardless of
// how the browser has scaled the canvas element visually.

let physicalRefSamples = [];
let physicalRefActiveIndex = -1; // index into physicalRefSamples, or -1 = new/unsaved
let physicalRefDrawnTarget = null; // [x1,y1,x2,y2] source pixels, or null
let physicalRefDrawnDistractors = []; // array of [x1,y1,x2,y2] source pixels
let physicalRefSourceWidth = 0;
let physicalRefSourceHeight = 0;
let physicalRefFrameImage = null;
let physicalRefDrag = null; // {start:[x,y], current:[x,y]} in source pixels, while dragging
let physicalRefImageTopicHint = null;
let physicalRefImageTopicHintForBag = null;
let physicalRefResolvedConvention = null; // {coordinate_convention, coordinate_convention_evidence} or null
let physicalRefResolvedConventionForBag = null;

function shouldOpenPhysicalRefWorkspace() {
  const checkedRadio = document.querySelector('input[name="workspaceMode"]:checked');
  return !!checkedRadio && checkedRadio.value === "physical";
}
window.shouldOpenPhysicalRefWorkspace = shouldOpenPhysicalRefWorkspace;

function physicalRefSetStatus(text) {
  const el = document.getElementById("physicalRefFrameStatus");
  if (el) el.innerText = text || "";
}

function physicalRefSetFormStatus(text) {
  const el = document.getElementById("physicalRefStatus");
  if (el) el.innerText = text || "";
}

function physicalRefFrameUrl(idx) {
  const showOverlays = document.getElementById("physicalRefShowOverlays");
  const drawOverlays = !showOverlays || showOverlays.checked;
  return "/frame.jpg" +
    "?idx=" + encodeURIComponent(String(idx)) +
    "&clean=0" +
    "&draw_detections=0" +
    "&draw_tracks=" + (drawOverlays ? "1" : "0") +
    "&draw_raw=0" +
    "&draw_tim=0" +
    "&only_ids=" +
    "&ts=" + encodeURIComponent(String(Date.now()));
}

async function physicalRefEnsureImageTopicHint() {
  if (physicalRefImageTopicHintForBag === loadedBag) return;
  physicalRefImageTopicHintForBag = loadedBag;
  try {
    const res = await fetch("/api/physical_reference/image_topic_hint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bag: loadedBag }),
    });
    const data = await res.json();
    physicalRefImageTopicHint = data.ok ? data.topic : null;
  } catch (e) {
    physicalRefImageTopicHint = null;
  }
}

// Deterministic coordinate_convention resolution (docs/issues/p1-10-improve-bbox-evaluation.md
// section F). A historical May/June-style source must never silently default
// to the modern contract, and an unresolvable source must never silently
// default to either -- physicalRefApplyResolvedConvention() below always
// leaves the "-- unresolved, choose deliberately --" option selected unless
// the backend returned an actual resolution.
async function physicalRefEnsureCoordinateConvention() {
  if (physicalRefResolvedConventionForBag === loadedBag) return;
  physicalRefResolvedConventionForBag = loadedBag;
  try {
    const res = await fetch("/api/physical_reference/resolve_coordinate_convention", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bag: loadedBag }),
    });
    const data = await res.json();
    physicalRefResolvedConvention = data.ok ? data.resolved : null;
  } catch (e) {
    physicalRefResolvedConvention = null;
  }
  physicalRefApplyResolvedConvention();
}

function physicalRefApplyResolvedConvention() {
  const sel = document.getElementById("physicalRefCoordConvention");
  const note = document.getElementById("physicalRefCoordResolvedNote");
  const evidenceField = document.getElementById("physicalRefCoordEvidence");
  if (!sel) return;

  if (physicalRefResolvedConvention) {
    sel.value = physicalRefResolvedConvention.coordinate_convention;
    if (evidenceField && physicalRefResolvedConvention.coordinate_convention_evidence) {
      evidenceField.value = physicalRefResolvedConvention.coordinate_convention_evidence;
    }
    if (note) {
      note.innerText =
        "Resolved automatically from the loaded source: " +
        physicalRefResolvedConvention.coordinate_convention +
        ". Verify before relying on it; override below if this source is not " +
        "what the automatic rule assumed.";
    }
  } else {
    sel.value = "";
    if (note) {
      note.innerText =
        "Could not resolve automatically from this source -- choose the " +
        "correct coordinate convention deliberately before saving. The " +
        "backend rejects an unresolved (empty) value.";
    }
  }
  physicalRefOnCoordConventionChange();
}

async function updatePhysicalRefFrame() {
  if (!shouldOpenPhysicalRefWorkspace()) return;

  const canvas = document.getElementById("physicalRefCanvas");
  if (!canvas) return;

  if (!loadedFrames) {
    physicalRefSetStatus("No frames loaded.");
    return;
  }

  physicalRefEnsureImageTopicHint();
  physicalRefEnsureCoordinateConvention();

  const idx = currentFrameIndex();
  const meta = document.getElementById("physicalRefFrameMeta");
  if (meta) {
    meta.innerText =
      "frame " + idx + " / " + Math.max(0, loadedFrames - 1) +
      " | t_s=" + currentTimeS().toFixed(3) +
      " s (bag-relative, derived from the loaded source frame)";
  }

  const img = new Image();
  img.onerror = function () {
    physicalRefSetStatus("Failed to load source frame.");
  };
  img.onload = function () {
    physicalRefFrameImage = img;
    physicalRefSourceWidth = img.naturalWidth;
    physicalRefSourceHeight = img.naturalHeight;
    // Internal buffer resolution = source image resolution. CSS/layout may
    // still scale the element visually; that scaling is exactly what
    // physicalRefCanvasToSourceCoords() below divides back out.
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    physicalRefSetStatus("");
    // Draft geometry is frame-local: every frame change resolves the
    // current frame's own state (a saved sample's geometry, or nothing)
    // before repainting -- an unsaved box drawn on a previous frame must
    // never silently reappear here.
    physicalRefSyncDraftToCurrentFrame();
    physicalRefRepaint();
  };
  img.src = physicalRefFrameUrl(idx);
}
window.updatePhysicalRefFrame = updatePhysicalRefFrame;

function physicalRefDrawBox(ctx, box, colour, label) {
  if (!box) return;
  const [x1, y1, x2, y2] = box;
  ctx.lineWidth = Math.max(2, Math.round(physicalRefSourceWidth / 250));
  ctx.strokeStyle = colour;
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  if (label) {
    ctx.fillStyle = colour;
    ctx.font = "16px sans-serif";
    ctx.fillText(label, x1 + 4, Math.max(14, y1 - 6));
  }
}

function physicalRefRepaint() {
  const canvas = document.getElementById("physicalRefCanvas");
  if (!canvas || !physicalRefFrameImage) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(physicalRefFrameImage, 0, 0);

  physicalRefDrawBox(ctx, physicalRefDrawnTarget, "#33ff66", "target");
  physicalRefDrawnDistractors.forEach((box, i) => {
    physicalRefDrawBox(ctx, box, "#ff9933", "distractor " + (i + 1));
  });

  if (physicalRefDrag && physicalRefDrag.current) {
    const preview = physicalRefNormalizeDrag(physicalRefDrag.start, physicalRefDrag.current);
    if (preview) {
      const modeEl = document.getElementById("physicalRefDrawMode");
      const colour = modeEl && modeEl.value === "distractor" ? "#ff9933" : "#33ff66";
      physicalRefDrawBox(ctx, preview, colour, "drawing...");
    }
  }
}

// --- Coordinate mapping and rectangle normalisation -------------------------

function physicalRefCanvasToSourceCoords(evt, canvas) {
  const rect = canvas.getBoundingClientRect();
  const displayX = evt.clientX - rect.left;
  const displayY = evt.clientY - rect.top;
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return [displayX * scaleX, displayY * scaleY];
}

// Reverse-drag-safe normalisation: returns null for a zero/near-zero-area
// box so the caller can reject it outright, matching
// tools/bag_annotation_ui/tim_ui_physical_reference.py's normalize_rect
// (the backend re-applies the same reverse-drag/zero-area rule as a safety
// net; this is the frontend's first line of defence, not the authority).
function physicalRefNormalizeDrag(start, current) {
  const [x1, y1] = start;
  const [x2, y2] = current;
  const loX = Math.min(x1, x2);
  const hiX = Math.max(x1, x2);
  const loY = Math.min(y1, y2);
  const hiY = Math.max(y1, y2);
  if (hiX - loX < 1.0 || hiY - loY < 1.0) return null;
  return [loX, loY, hiX, hiY];
}

function physicalRefClipToBounds(box) {
  const [x1, y1, x2, y2] = box;
  return [
    Math.max(0, Math.min(x1, physicalRefSourceWidth)),
    Math.max(0, Math.min(y1, physicalRefSourceHeight)),
    Math.max(0, Math.min(x2, physicalRefSourceWidth)),
    Math.max(0, Math.min(y2, physicalRefSourceHeight)),
  ];
}

// --- Pointer interaction -----------------------------------------------------

function physicalRefOnPointerDown(evt) {
  const canvas = document.getElementById("physicalRefCanvas");
  if (!canvas || !physicalRefFrameImage) return;
  const state = document.getElementById("physicalRefState");
  if (state && state.value !== "present_scored") {
    physicalRefSetFormStatus("Set reference state to present_scored before drawing a box.");
    return;
  }
  const [x, y] = physicalRefCanvasToSourceCoords(evt, canvas);
  physicalRefDrag = { start: [x, y], current: [x, y] };
  canvas.setPointerCapture(evt.pointerId);
}

function physicalRefOnPointerMove(evt) {
  if (!physicalRefDrag) return;
  const canvas = document.getElementById("physicalRefCanvas");
  if (!canvas) return;
  const [x, y] = physicalRefCanvasToSourceCoords(evt, canvas);
  physicalRefDrag.current = [x, y];
  physicalRefRepaint();
}

function physicalRefOnPointerUp(evt) {
  if (!physicalRefDrag) return;
  const canvas = document.getElementById("physicalRefCanvas");
  const [x, y] = canvas ? physicalRefCanvasToSourceCoords(evt, canvas) : physicalRefDrag.current;
  const rect = physicalRefNormalizeDrag(physicalRefDrag.start, [x, y]);
  physicalRefDrag = null;

  if (!rect) {
    physicalRefSetStatus("Ignored zero-area box -- drag out a rectangle.");
    physicalRefRepaint();
    return;
  }

  const clipped = physicalRefClipToBounds(rect);
  const modeEl = document.getElementById("physicalRefDrawMode");
  if (modeEl && modeEl.value === "distractor") {
    const context = document.getElementById("physicalRefContext");
    if (context && context.value !== "distractors_complete") {
      physicalRefSetFormStatus(
        "Set identity context to distractors_complete before drawing distractor boxes."
      );
      physicalRefRepaint();
      return;
    }
    physicalRefDrawnDistractors.push(clipped);
    physicalRefRenderDistractorList();
  } else {
    physicalRefDrawnTarget = clipped;
  }
  physicalRefRepaint();
}

function physicalRefSetupCanvasEvents() {
  const canvas = document.getElementById("physicalRefCanvas");
  if (!canvas) return;
  canvas.addEventListener("pointerdown", physicalRefOnPointerDown);
  canvas.addEventListener("pointermove", physicalRefOnPointerMove);
  canvas.addEventListener("pointerup", physicalRefOnPointerUp);
}
window.addEventListener("DOMContentLoaded", physicalRefSetupCanvasEvents);

function physicalRefClearCurrentBox() {
  physicalRefDrawnTarget = null;
  physicalRefDrawnDistractors = [];
  physicalRefRepaint();
  physicalRefRenderDistractorList();
}

// --- State / context controls -----------------------------------------------

function physicalRefOnStateChange() {
  const state = document.getElementById("physicalRefState").value;
  const contextLabel = document.getElementById("physicalRefContextLabel");
  if (contextLabel) contextLabel.hidden = state !== "present_scored";

  if (state !== "present_scored") {
    physicalRefDrawnTarget = null;
    physicalRefDrawnDistractors = [];
    physicalRefRepaint();
  }
  physicalRefOnContextChange();
}

function physicalRefOnContextChange() {
  const state = document.getElementById("physicalRefState").value;
  const context = document.getElementById("physicalRefContext").value;
  if (state === "present_scored" && context === "target_only" && physicalRefDrawnDistractors.length) {
    physicalRefDrawnDistractors = [];
    physicalRefRepaint();
  }
  physicalRefRenderDistractorList();
}

function physicalRefOnCoordConventionChange() {
  const sel = document.getElementById("physicalRefCoordConvention");
  const evidenceLabel = document.getElementById("physicalRefEvidenceLabel");
  if (evidenceLabel && sel) {
    evidenceLabel.hidden = sel.value !== "source_pixels_historical_pre_p53";
  }
}

function physicalRefRenderDistractorList() {
  const host = document.getElementById("physicalRefDistractorList");
  if (!host) return;

  const state = document.getElementById("physicalRefState");
  const context = document.getElementById("physicalRefContext");
  if (!state || state.value !== "present_scored" || !context || context.value !== "distractors_complete") {
    host.innerHTML = "<em>distractors only apply when state=present_scored and context=distractors_complete</em>";
    return;
  }
  if (!physicalRefDrawnDistractors.length) {
    host.innerHTML = "<em>no distractor boxes drawn yet -- switch draw mode to Distractor and drag one out</em>";
    return;
  }

  let html = "";
  physicalRefDrawnDistractors.forEach((box, i) => {
    html +=
      '<div class="physicalRefDistractorRow">' +
      "<span>distractor " + (i + 1) + ": [" + box.map((v) => v.toFixed(1)).join(", ") + "]</span>" +
      '<button type="button" onclick="physicalRefRemoveDistractor(' + i + ')">remove</button>' +
      "</div>";
  });
  host.innerHTML = html;
}

function physicalRefRemoveDistractor(i) {
  physicalRefDrawnDistractors.splice(i, 1);
  physicalRefRepaint();
  physicalRefRenderDistractorList();
}

// --- Sample list (in-memory artifact under construction) --------------------

function physicalRefRenderSampleList() {
  const host = document.getElementById("physicalRefRows");
  if (!host) return;

  if (!physicalRefSamples.length) {
    host.innerHTML = '<div class="hint">No samples yet.</div>';
    physicalRefSetFormStatus("No physical-reference samples loaded.");
    return;
  }

  let html = '<table class="annTable"><thead><tr><th>t_s</th><th>state</th><th>context</th><th></th></tr></thead><tbody>';
  physicalRefSamples.forEach((s, i) => {
    const activeStyle = i === physicalRefActiveIndex ? ' style="background:#222"' : "";
    html +=
      "<tr" + activeStyle + ">" +
      "<td>" + s.t_s.toFixed(3) + "</td>" +
      "<td>" + s.identity_state + "</td>" +
      "<td>" + (s.identity_context || "") + "</td>" +
      '<td><button type="button" onclick="physicalRefLoadSampleIntoForm(' + i + ')">edit</button></td>' +
      "</tr>";
  });
  html += "</tbody></table>";
  host.innerHTML = html;

  physicalRefSetFormStatus(
    physicalRefSamples.length + " sample(s) in memory. Click Save JSON to persist them."
  );
}

function physicalRefNewSampleAtCurrentFrame() {
  if (!loadedFrames) {
    physicalRefSetFormStatus("Load a bag first.");
    return;
  }
  physicalRefActiveIndex = -1;
  physicalRefDrawnTarget = null;
  physicalRefDrawnDistractors = [];
  document.getElementById("physicalRefState").value = "present_scored";
  document.getElementById("physicalRefContext").value = "target_only";
  document.getElementById("physicalRefInterpolate").checked = false;
  document.getElementById("physicalRefNotes").value = "";
  physicalRefOnStateChange();
  physicalRefRepaint();
  physicalRefSetFormStatus(
    "New sample at t_s=" + currentTimeS().toFixed(3) +
      " -- draw a box (if applicable), set state/context, then Add / update."
  );
}

function physicalRefBuildSampleFromForm() {
  const state = document.getElementById("physicalRefState").value;
  const context = state === "present_scored" ? document.getElementById("physicalRefContext").value : null;
  const interpolate = document.getElementById("physicalRefInterpolate").checked;
  const notes = document.getElementById("physicalRefNotes").value || "";
  const t_s = currentTimeS();

  let targetBbox = null;
  let distractors = [];

  if (state === "present_scored") {
    if (!physicalRefDrawnTarget) {
      physicalRefSetFormStatus("Draw a target bbox before adding this sample.");
      return null;
    }
    targetBbox = physicalRefDrawnTarget;
    if (context === "distractors_complete") {
      if (!physicalRefDrawnDistractors.length) {
        physicalRefSetFormStatus("distractors_complete requires at least one distractor bbox.");
        return null;
      }
      distractors = physicalRefDrawnDistractors.slice();
    }
  }

  return {
    t_s: t_s,
    identity_state: state,
    identity_context: context,
    target_bbox_xyxy: targetBbox,
    distractor_bboxes_xyxy: distractors,
    interpolate_from_previous: interpolate,
    notes: notes,
  };
}

function physicalRefUpdateActiveSample() {
  const sample = physicalRefBuildSampleFromForm();
  if (!sample) return;

  // Edit-in-place at the same t_s, or insert in sorted order -- the schema
  // requires samples strictly increasing by t_s.
  const existingIndex = physicalRefSamples.findIndex(
    (s) => Math.abs(s.t_s - sample.t_s) < 1e-9
  );
  if (existingIndex >= 0) {
    physicalRefSamples[existingIndex] = sample;
  } else {
    physicalRefSamples.push(sample);
    physicalRefSamples.sort((a, b) => a.t_s - b.t_s);
  }
  physicalRefActiveIndex = -1;
  physicalRefRenderSampleList();
}

// --- Frame-local draft geometry ----------------------------------------------
//
// Unsaved target/distractor boxes belong to exactly one source frame. On
// every frame change (updatePhysicalRefFrame's img.onload, above) this is
// resolved before repainting: if the newly displayed frame already has a
// saved physical-reference sample, that sample's own geometry is loaded for
// editing (physicalRefLoadSampleIntoForm); otherwise any leftover draft
// geometry from whichever frame was previously displayed is discarded. A
// box drawn on frame A must never silently reappear as draft geometry on
// frame B -- there is no automatic carry-forward path anywhere in this file.

function physicalRefFindSampleAtCurrentFrame() {
  const t = currentTimeS();
  return physicalRefSamples.findIndex((s) => Math.abs(s.t_s - t) < 1e-6);
}

function physicalRefSyncDraftToCurrentFrame() {
  const idx = physicalRefFindSampleAtCurrentFrame();

  if (idx >= 0) {
    physicalRefLoadSampleIntoForm(idx, /* viaNavigation */ true);
    return;
  }

  const interpolateCheckbox = document.getElementById("physicalRefInterpolate");
  const hadUnsavedDraft =
    !!physicalRefDrawnTarget ||
    physicalRefDrawnDistractors.length > 0 ||
    (interpolateCheckbox && interpolateCheckbox.checked);

  physicalRefActiveIndex = -1;
  physicalRefDrawnTarget = null;
  physicalRefDrawnDistractors = [];
  // interpolate_from_previous is a deliberate per-sample decision; it must
  // never remain checked merely because the previously displayed frame (or
  // sample) used interpolation -- that would risk silently creating an
  // interpolated sample on ordinary frame navigation.
  if (interpolateCheckbox) interpolateCheckbox.checked = false;
  physicalRefRenderDistractorList();

  if (hadUnsavedDraft) {
    physicalRefSetStatus(
      "Unsaved draft geometry from the previous frame was discarded " +
        "(draft boxes are frame-local and are never carried forward)."
    );
  }
}

function physicalRefLoadSampleIntoForm(i, viaNavigation) {
  const s = physicalRefSamples[i];
  if (!s) return;
  physicalRefActiveIndex = i;
  document.getElementById("physicalRefState").value = s.identity_state;
  document.getElementById("physicalRefContext").value = s.identity_context || "target_only";
  document.getElementById("physicalRefInterpolate").checked = !!s.interpolate_from_previous;
  document.getElementById("physicalRefNotes").value = s.notes || "";
  physicalRefDrawnTarget = s.target_bbox_xyxy ? s.target_bbox_xyxy.slice() : null;
  physicalRefDrawnDistractors = (s.distractor_bboxes_xyxy || []).map((b) => b.slice());
  physicalRefOnStateChange();
  physicalRefRepaint();
  physicalRefSetFormStatus(
    viaNavigation
      ? "Loaded this frame's saved sample (t_s=" + s.t_s.toFixed(3) + ")."
      : "Editing sample at t_s=" + s.t_s.toFixed(3) +
          ". Step the frame stepper to that time if you want to redraw its box."
  );
}

function physicalRefDeleteActive() {
  if (physicalRefActiveIndex < 0 || physicalRefActiveIndex >= physicalRefSamples.length) {
    physicalRefSetFormStatus("No active sample selected -- click 'edit' on a row first.");
    return;
  }
  physicalRefSamples.splice(physicalRefActiveIndex, 1);
  physicalRefActiveIndex = -1;
  physicalRefRenderSampleList();
}

// --- Save / load --------------------------------------------------------------

function physicalRefGatherProvenance() {
  const bagPath = typeof loadedBag === "string" ? loadedBag : "";
  const bagName = bagPath.split("/").filter(Boolean).slice(-1)[0] || "";
  const evidence = document.getElementById("physicalRefCoordEvidence").value.trim();

  return {
    schema_version: 1,
    contract_version: "tim_physical_target_bbox_v1",
    sequence_id: document.getElementById("physicalRefSequenceId").value || "",
    source_bag_name: bagName,
    source_bag_path: bagPath,
    source_image_topic: physicalRefImageTopicHint || "/camera/image_raw",
    source_width: physicalRefSourceWidth,
    source_height: physicalRefSourceHeight,
    coordinate_convention: document.getElementById("physicalRefCoordConvention").value,
    coordinate_convention_evidence: evidence || null,
    selected_physical_target_label: document.getElementById("physicalRefTargetLabel").value || "",
    annotator: document.getElementById("physicalRefAnnotator").value || "",
    created_date: new Date().toISOString().slice(0, 10),
    notes: "",
  };
}

async function physicalRefSave() {
  const path = document.getElementById("physicalRefOutputPath").value.trim();
  if (!path) {
    physicalRefSetFormStatus("Set an output JSON path first.");
    return;
  }
  if (!physicalRefSamples.length) {
    physicalRefSetFormStatus("No samples to save.");
    return;
  }

  const artifact = { provenance: physicalRefGatherProvenance(), samples: physicalRefSamples };

  let data;
  try {
    const res = await fetch("/api/physical_reference/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path, artifact: artifact }),
    });
    data = await res.json();
  } catch (e) {
    physicalRefSetFormStatus("Save request failed: " + e);
    return;
  }

  if (!data.ok) {
    // The backend validator (physical_target_reference.py) is authoritative;
    // an invalid artifact is never written, regardless of what the frontend
    // thought was fine.
    physicalRefSetFormStatus("Save rejected by backend validator: " + data.error);
    return;
  }

  physicalRefSetFormStatus(data.message);
  physicalRefRefreshExistingList();
}

async function physicalRefLoadSelected() {
  const sel = document.getElementById("physicalRefExisting");
  const path = (sel && sel.value) || document.getElementById("physicalRefOutputPath").value.trim();
  if (!path) {
    physicalRefSetFormStatus("No physical-reference file selected.");
    return;
  }

  let data;
  try {
    const res = await fetch("/api/physical_reference/load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path }),
    });
    data = await res.json();
  } catch (e) {
    physicalRefSetFormStatus("Load request failed: " + e);
    return;
  }

  if (!data.ok) {
    physicalRefSetFormStatus("Load failed: " + data.error);
    return;
  }

  physicalRefSamples = data.samples || [];
  const provenance = data.provenance || null;
  document.getElementById("physicalRefOutputPath").value = data.path;

  if (provenance) {
    document.getElementById("physicalRefSequenceId").value = provenance.sequence_id || "";
    document.getElementById("physicalRefTargetLabel").value = provenance.selected_physical_target_label || "";
    document.getElementById("physicalRefAnnotator").value = provenance.annotator || "";
    // A loaded artifact always carries a validated, non-empty
    // coordinate_convention (the backend validator guarantees this); the ""
    // fallback here only guards a malformed response and deliberately does
    // NOT default to either real convention -- same rule as
    // physicalRefApplyResolvedConvention().
    document.getElementById("physicalRefCoordConvention").value =
      provenance.coordinate_convention || "";
    document.getElementById("physicalRefCoordEvidence").value =
      provenance.coordinate_convention_evidence || "";
    const note = document.getElementById("physicalRefCoordResolvedNote");
    if (note) {
      note.innerText = "Loaded from " + data.path + ".";
    }
    physicalRefOnCoordConventionChange();
  }

  physicalRefActiveIndex = -1;
  physicalRefRenderSampleList();
  physicalRefSetFormStatus("Loaded " + physicalRefSamples.length + " sample(s) from " + data.path);
}

async function physicalRefRefreshExistingList() {
  const sel = document.getElementById("physicalRefExisting");
  if (!sel) return;

  let data;
  try {
    const res = await fetch("/api/physical_reference/list");
    data = await res.json();
  } catch (e) {
    return;
  }

  sel.innerHTML = "";
  (data.paths || []).forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.innerText = p;
    sel.appendChild(opt);
  });
}
window.addEventListener("DOMContentLoaded", physicalRefRefreshExistingList);
