// Issue #25 physical-reference bbox annotation mode -- v2
// (tim_physical_target_bbox_v2).
//
// Sibling of, and replacement for the *active* workspace behind,
// tim_physical_reference_ui.js (v1): v1's file remains in the repository
// untouched and its own tests remain meaningful, but this is the script
// tim_clean_ui.html now loads for the "Physical reference" workspace mode
// -- new physical-reference artifacts created through the normal UI
// workflow always use v2. A v1 artifact is never silently edited or
// migrated here; loading one is explicitly rejected with a clear message
// (see physicalRefLoadSelected). Deliberately a separate file from
// tim_clean_ui.js: it adds this UI mode without touching the legacy
// tracker-ID annotation workflow's code, reusing tim_clean_ui.js's
// existing bag-loading, frame-stepping, and frame-time globals
// (loadedFrames, loadedBag, frameTimesS, currentFrameIndex(),
// currentTimeS()) rather than duplicating them.
//
// Core invariant, enforced by construction, not just convention: this file
// never reads or sends a tracker ID as part of the saved physical-reference
// artifact. Tracker/detection overlays may be drawn on the canvas for
// visual context only (via /frame.jpg's existing draw_tracks param); they
// are pixels in a JPEG, never serialized into physicalRefSamples. Physical
// distractor identity is instead an annotation-local person_ref
// (phys_dNNN) scoped to this artifact only -- see physicalRefV2NextPersonRef
// and physicalRefV2KnownPersonRefsFromSamples.
//
// Coordinate contract (unchanged from v1): the canvas's internal pixel
// buffer (canvas.width/height) is set to the loaded frame's *natural*
// pixel dimensions the moment it loads (see updatePhysicalRefFrame). A
// mouse event is first converted from CSS/display pixels to that buffer's
// pixel space using the ratio between the buffer size and the canvas
// element's on-screen rendered size (getBoundingClientRect); because the
// buffer size already equals the source image size, that conversion *is*
// the display-to-source mapping in one step. Saved boxes are therefore
// always source-image pixels, never raw display/CSS coordinates,
// regardless of how the browser has scaled the canvas element visually.
//
// evaluation_window (frozen, corrected 2026-08-10 in commit 4ab33ec1):
// derived deterministically from the loaded source frame timeline as
// {start_s: frameTimesS[0], end_s: frameTimesS[frameTimesS.length - 1]},
// always read-only in the normal workflow -- never DEFAULT_STEP_S, an
// estimated/median frame period, an epsilon, or a manually-typed value.
// The final source frame (t_s == end_s) is a legal right-boundary
// interpolation anchor and contributes zero duration by itself; see
// docs/issues/p1-10-physical-reference-v2-contract.md section I.

let physicalRefSamples = [];
let physicalRefActiveIndex = -1; // index into physicalRefSamples, or -1 = new/unsaved
let physicalRefDrawnTarget = null; // [x1,y1,x2,y2] source pixels, or null
let physicalRefDrawnDistractors = []; // array of {person_ref, bbox_xyxy}
let physicalRefV2ActivePersonRef = null; // person_ref the NEXT distractor draw will use
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
// section F; unchanged from v1, same backend route reused -- resolution has
// no schema-version dependency). A historical May/June-style source must
// never silently default to the modern contract, and an unresolvable
// source must never silently default to either --
// physicalRefApplyResolvedConvention() below always leaves the
// "-- unresolved, choose deliberately --" option selected unless the
// backend returned an actual resolution.
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

// --- evaluation_window: source-derived, read-only (contract section I) -----

function physicalRefV2EvaluationWindow() {
  if (!Array.isArray(frameTimesS) || frameTimesS.length === 0) {
    return { start_s: 0.0, end_s: 0.0 };
  }
  // Deliberately just the first/last entries of the already-normalised
  // frame timeline -- no DEFAULT_STEP_S, no estimated/median frame period,
  // no epsilon, no manual override. frameTimesS[0] is expected to be 0.0
  // by the existing bag-relative normalisation.
  return {
    start_s: frameTimesS[0],
    end_s: frameTimesS[frameTimesS.length - 1],
  };
}

function physicalRefV2RenderEvaluationWindow(windowOverride) {
  const el = document.getElementById("physicalRefEvalWindow");
  if (!el) return;
  const w = windowOverride || physicalRefV2EvaluationWindow();
  el.innerText =
    "Evaluation window (source-derived, read-only): [" +
    Number(w.start_s).toFixed(3) + "s, " + Number(w.end_s).toFixed(3) + "s). " +
    "The final source frame (t_s = end_s) is a legal right-boundary " +
    "interpolation anchor and contributes zero duration by itself.";
}

// Loads the frame-image JPEG (which may have server-baked tracker-overlay
// pixels per physicalRefFrameUrl's draw_tracks param) into the canvas's
// backing buffer and invokes onReady() once it is ready to be painted on.
// This is pure image-fetch/buffer-sizing mechanics -- it never touches
// physicalRefDrawnTarget/physicalRefDrawnDistractors/physicalRefV2ActivePersonRef
// or the interpolate checkbox. Callers decide separately whether the new
// image represents an actual frame change (and therefore must resync the
// frame-local draft, see updatePhysicalRefFrame) or the same frame redrawn
// only because overlay visibility changed (see physicalRefRefreshOverlayImage,
// which must never resync the draft).
function physicalRefLoadFrameImage(idx, onReady) {
  const canvas = document.getElementById("physicalRefCanvas");
  if (!canvas) return;
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
    onReady();
  };
  img.src = physicalRefFrameUrl(idx);
}

async function updatePhysicalRefFrame() {
  if (!shouldOpenPhysicalRefWorkspace()) return;

  if (!document.getElementById("physicalRefCanvas")) return;

  if (!loadedFrames) {
    physicalRefSetStatus("No frames loaded.");
    return;
  }

  physicalRefEnsureImageTopicHint();
  physicalRefEnsureCoordinateConvention();
  physicalRefV2RenderEvaluationWindow();

  const idx = currentFrameIndex();
  const meta = document.getElementById("physicalRefFrameMeta");
  const evalWindow = physicalRefV2EvaluationWindow();
  const isRightBoundaryAnchor = Math.abs(currentTimeS() - evalWindow.end_s) < 1e-6;
  if (meta) {
    meta.innerText =
      "frame " + idx + " / " + Math.max(0, loadedFrames - 1) +
      " | t_s=" + currentTimeS().toFixed(3) +
      " s (bag-relative, derived from the loaded source frame)" +
      (isRightBoundaryAnchor
        ? " | final source frame -- valid right-boundary interpolation anchor"
        : "");
  }

  physicalRefLoadFrameImage(idx, function () {
    // Draft geometry (including any active person_ref selection) is
    // frame-local: every frame change resolves the current frame's own
    // state (a saved sample's geometry, or nothing) before repainting --
    // an unsaved box drawn on a previous frame must never silently
    // reappear here. This runs only on an actual frame change, never on
    // an overlay-visibility-only redraw (physicalRefRefreshOverlayImage).
    physicalRefSyncDraftToCurrentFrame();
    physicalRefRepaint();
  });
}
window.updatePhysicalRefFrame = updatePhysicalRefFrame;

// Tracker-overlay visibility is a pure presentation toggle. The overlay
// pixels are baked server-side into the JPEG (physicalRefFrameUrl's
// draw_tracks param), so the image genuinely must be re-fetched -- but the
// displayed frame itself has not changed, so this must never run the
// frame-navigation draft-reset path (physicalRefSyncDraftToCurrentFrame).
// Any unsaved target/distractor/person_ref/interpolation draft state is
// left completely untouched; only the repainted pixels change.
function physicalRefRefreshOverlayImage() {
  if (!shouldOpenPhysicalRefWorkspace()) return;
  if (!document.getElementById("physicalRefCanvas")) return;
  if (!loadedFrames) return;

  const idx = currentFrameIndex();
  physicalRefLoadFrameImage(idx, function () {
    physicalRefRepaint();
  });
}
window.physicalRefRefreshOverlayImage = physicalRefRefreshOverlayImage;

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

  physicalRefDrawBox(ctx, physicalRefDrawnTarget, "#33ff66", "Target");
  physicalRefDrawnDistractors.forEach((d) => {
    physicalRefDrawBox(ctx, d.bbox_xyxy, "#ff9933", d.person_ref);
  });

  if (physicalRefDrag && physicalRefDrag.current) {
    const preview = physicalRefNormalizeDrag(physicalRefDrag.start, physicalRefDrag.current);
    if (preview) {
      const modeEl = document.getElementById("physicalRefDrawMode");
      const isDistractor = modeEl && modeEl.value === "distractor";
      const colour = isDistractor ? "#ff9933" : "#33ff66";
      const label = isDistractor ? (physicalRefV2ActivePersonRef || "?") : "Target";
      physicalRefDrawBox(ctx, preview, colour, label);
    }
  }
}

// --- Coordinate mapping and rectangle normalisation -------------------------
// Unchanged from v1: person_ref logic never touches coordinate handling.

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
// (reused as-is by tim_ui_physical_reference_v2.py -- the backend re-applies
// the same reverse-drag/zero-area rule as a safety net; this is the
// frontend's first line of defence, not the authority).
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
    if (!physicalRefV2ActivePersonRef) {
      physicalRefSetFormStatus(
        "Select an existing physical person or '+ New physical person' " +
          "before drawing a distractor box -- person_ref is never derived " +
          "from a tracker ID, drawing order, or bbox position."
      );
      physicalRefRepaint();
      return;
    }
    const alreadyDrawn = physicalRefDrawnDistractors.some(
      (d) => d.person_ref === physicalRefV2ActivePersonRef
    );
    if (alreadyDrawn) {
      physicalRefSetFormStatus(
        physicalRefV2ActivePersonRef +
          " already has a box in this sample -- remove it first or select a different person."
      );
      physicalRefRepaint();
      return;
    }
    physicalRefDrawnDistractors.push({
      person_ref: physicalRefV2ActivePersonRef,
      bbox_xyxy: clipped,
    });
    physicalRefRenderDistractorList();
    physicalRefV2RenderPersonRefPalette();
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
  physicalRefV2RenderPersonRefPalette();
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
  physicalRefV2RenderPersonRefPalette();
  physicalRefV2UpdateInterpolationEligibilityNote();
}

function physicalRefOnCoordConventionChange() {
  const sel = document.getElementById("physicalRefCoordConvention");
  const evidenceLabel = document.getElementById("physicalRefEvidenceLabel");
  if (evidenceLabel && sel) {
    evidenceLabel.hidden = sel.value !== "source_pixels_historical_pre_p53";
  }
}

// --- person_ref: annotation-local physical-person identity ------------------
//
// Never a tracker ID, detector index, drawing order, or bbox position.
// "Known" people are always re-derived from physicalRefSamples (plus the
// current unsaved draft, so a not-yet-saved new person can't collide with
// itself) -- nothing about identity is stored separately, so removing a
// distractor from the current draft can never remove that person from an
// earlier saved sample or from the palette.

function physicalRefV2KnownPersonRefsFromSamples(samples) {
  const refs = new Set();
  (samples || []).forEach((s) => {
    (s.distractors || []).forEach((d) => {
      if (d && d.person_ref) refs.add(d.person_ref);
    });
  });
  return Array.from(refs).sort();
}

function physicalRefV2AllKnownPersonRefs() {
  const fromSamples = physicalRefV2KnownPersonRefsFromSamples(physicalRefSamples);
  const fromDraft = physicalRefDrawnDistractors.map((d) => d.person_ref);
  return Array.from(new Set(fromSamples.concat(fromDraft))).sort();
}

// Deterministic policy: lowest unused positive ordinal in the phys_dNNN
// namespace (mirrors tools/bag_annotation_ui/tim_ui_physical_reference_v2.next_person_ref
// exactly, so client-side generation never disagrees with the backend).
// Given {phys_d001, phys_d002, phys_d004}, returns phys_d003 -- not
// phys_d005 (monotonic-next would also be defensible, but this repository
// uses lowest-unused).
function physicalRefV2NextPersonRef(knownRefs) {
  const used = new Set();
  (knownRefs || []).forEach((ref) => {
    const m = /^phys_d([0-9]{3,})$/.exec(String(ref));
    if (m) used.add(parseInt(m[1], 10));
  });
  let n = 1;
  while (used.has(n)) n++;
  return "phys_d" + String(n).padStart(3, "0");
}

function physicalRefV2SelectPersonRef(ref) {
  physicalRefV2ActivePersonRef = ref;
  physicalRefV2RenderPersonRefPalette();
}
window.physicalRefV2SelectPersonRef = physicalRefV2SelectPersonRef;

function physicalRefV2NewPersonRef() {
  const known = physicalRefV2AllKnownPersonRefs();
  const next = physicalRefV2NextPersonRef(known);
  physicalRefV2SelectPersonRef(next);
  physicalRefSetStatus(
    "New physical person " + next + " selected -- switch draw mode to " +
      "Distractor and drag out its box. Reuse this identifier on later " +
      "keyframes only if you are genuinely certain it is the same " +
      "physical person; if uncertain after a disappearance/re-entry, " +
      "create a new one instead."
  );
}
window.physicalRefV2NewPersonRef = physicalRefV2NewPersonRef;

// The active person_ref's drawn/not-drawn status is two independent
// questions -- "does this identity already exist in the saved artifact"
// (isHistoricallyKnown) and "does it have a bbox in the CURRENT draft/
// sample right now" (physicalRefDrawnDistractors, frontend-only, updated
// immediately on draw/remove, never requiring a save/reload/navigation/
// overlay-toggle round trip) -- and must never conflate them: a brand-new
// identity becomes "drawn" the instant its box is drawn, and a
// historically-known identity reused on a later frame is never mislabeled
// "new" merely because this particular frame hasn't been drawn yet.
function physicalRefV2ActivePersonRefStatusSuffix(ref, isHistoricallyKnown) {
  const drawnNow = physicalRefDrawnDistractors.some((d) => d.person_ref === ref);
  if (drawnNow) return "";
  return isHistoricallyKnown ? " (not drawn on this frame)" : " (new, not yet drawn)";
}

function physicalRefV2RenderPersonRefPalette() {
  const host = document.getElementById("physicalRefPersonRefPalette");
  if (!host) return;

  const known = physicalRefV2KnownPersonRefsFromSamples(physicalRefSamples);
  let html =
    '<div class="physicalRefHint">Known physical people in this artifact ' +
    "(annotation-local identities -- never tracker IDs):</div>" +
    '<div class="physicalRefPersonRefChips">';

  known.forEach((ref) => {
    const isActive = ref === physicalRefV2ActivePersonRef;
    const activeClass = isActive ? " physicalRefPersonRefChipActive" : "";
    // Drawn/not-drawn status is only shown for the currently active
    // selection -- annotating every known person in the palette with
    // per-frame drawn status would be noise for identities the annotator
    // isn't working with right now.
    const suffix = isActive ? physicalRefV2ActivePersonRefStatusSuffix(ref, true) : "";
    html +=
      '<button type="button" class="physicalRefPersonRefChip' + activeClass + '" ' +
      'onclick="physicalRefV2SelectPersonRef(\'' + ref + '\')">' + ref + suffix + "</button>";
  });

  if (physicalRefV2ActivePersonRef && known.indexOf(physicalRefV2ActivePersonRef) === -1) {
    const suffix = physicalRefV2ActivePersonRefStatusSuffix(physicalRefV2ActivePersonRef, false);
    html +=
      '<button type="button" class="physicalRefPersonRefChip physicalRefPersonRefChipActive ' +
      'physicalRefPersonRefChipPending" disabled>' +
      physicalRefV2ActivePersonRef + suffix + "</button>";
  }

  html +=
    '<button type="button" class="physicalRefPersonRefChip physicalRefPersonRefChipNew" ' +
    'onclick="physicalRefV2NewPersonRef()">+ New physical person</button>' +
    "</div>";

  host.innerHTML = html;
}

// --- distractors_complete interpolation eligibility (convenience only) -----
//
// Backend validation (physical_target_reference_v2.validate_physical_reference)
// remains authoritative; this is a status message only, never a second
// independent schema check.

function physicalRefV2PreviousSample() {
  const t = currentTimeS();
  let prev = null;
  physicalRefSamples.forEach((s) => {
    if (s.t_s < t - 1e-9 && (!prev || s.t_s > prev.t_s)) prev = s;
  });
  return prev;
}

function physicalRefV2UpdateInterpolationEligibilityNote() {
  const note = document.getElementById("physicalRefInterpolateNote");
  if (!note) return;

  const state = document.getElementById("physicalRefState");
  const context = document.getElementById("physicalRefContext");
  if (!state || state.value !== "present_scored" || !context || context.value !== "distractors_complete") {
    note.innerText = "";
    return;
  }

  const prev = physicalRefV2PreviousSample();
  if (!prev || prev.identity_state !== "present_scored" || prev.identity_context !== "distractors_complete") {
    note.innerText = "";
    return;
  }

  const prevRefs = (prev.distractors || []).map((d) => d.person_ref).slice().sort();
  const currentRefs = physicalRefDrawnDistractors.map((d) => d.person_ref).slice().sort();
  const sameSet =
    prevRefs.length === currentRefs.length && prevRefs.every((r, i) => r === currentRefs[i]);

  note.innerText = sameSet
    ? "Previous set: {" + prevRefs.join(", ") + "} = current set -- interpolation eligible."
    : "Previous set: {" + prevRefs.join(", ") + "} vs current set: {" +
        currentRefs.join(", ") + "} -- person set changed, interpolation " +
        "not allowed (the backend will reject a save with the checkbox on).";
}

function physicalRefRenderDistractorList() {
  const host = document.getElementById("physicalRefDistractorList");
  if (!host) return;

  const state = document.getElementById("physicalRefState");
  const context = document.getElementById("physicalRefContext");
  if (!state || state.value !== "present_scored" || !context || context.value !== "distractors_complete") {
    host.innerHTML = "<em>distractors only apply when state=present_scored and context=distractors_complete</em>";
    physicalRefV2UpdateInterpolationEligibilityNote();
    return;
  }
  if (!physicalRefDrawnDistractors.length) {
    host.innerHTML =
      "<em>no distractor boxes drawn yet -- select or create a physical " +
      "person above, switch draw mode to Distractor, and drag one out</em>";
    physicalRefV2UpdateInterpolationEligibilityNote();
    return;
  }

  // Frontend display order only (sorted by person_ref for readability) --
  // never authoritative; the backend always serializes sorted by
  // person_ref regardless of drawing/input order.
  const sorted = physicalRefDrawnDistractors
    .slice()
    .sort((a, b) => (a.person_ref < b.person_ref ? -1 : a.person_ref > b.person_ref ? 1 : 0));

  let html = "";
  sorted.forEach((d) => {
    const originalIndex = physicalRefDrawnDistractors.indexOf(d);
    html +=
      '<div class="physicalRefDistractorRow">' +
      "<span>" + d.person_ref + ": [" +
      d.bbox_xyxy.map((v) => v.toFixed(1)).join(", ") + "]</span>" +
      '<button type="button" onclick="physicalRefRemoveDistractor(' + originalIndex + ')">remove</button>' +
      "</div>";
  });
  host.innerHTML = html;
  physicalRefV2UpdateInterpolationEligibilityNote();
}

function physicalRefRemoveDistractor(i) {
  // Removes only this entry from the current draft/sample -- never
  // affects historical samples or the artifact-wide known-person palette
  // (both are re-derived from physicalRefSamples, which this does not
  // touch).
  physicalRefDrawnDistractors.splice(i, 1);
  physicalRefRepaint();
  physicalRefRenderDistractorList();
  physicalRefV2RenderPersonRefPalette();
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
  physicalRefV2ActivePersonRef = null;
  document.getElementById("physicalRefState").value = "present_scored";
  document.getElementById("physicalRefContext").value = "target_only";
  document.getElementById("physicalRefInterpolate").checked = false;
  document.getElementById("physicalRefNotes").value = "";
  physicalRefOnStateChange();
  physicalRefRepaint();
  physicalRefV2RenderPersonRefPalette();
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
      // Deterministic order independent of drawing order -- the backend
      // re-sorts on its own too, this is belt-and-braces for readability
      // of the in-memory sample list before it is even sent.
      distractors = physicalRefDrawnDistractors
        .map((d) => ({ person_ref: d.person_ref, bbox_xyxy: d.bbox_xyxy.slice() }))
        .sort((a, b) => (a.person_ref < b.person_ref ? -1 : a.person_ref > b.person_ref ? 1 : 0));
    }
  }

  return {
    t_s: t_s,
    identity_state: state,
    identity_context: context,
    target_bbox_xyxy: targetBbox,
    distractors: distractors,
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
  physicalRefV2ActivePersonRef = null;
  physicalRefRenderSampleList();
  physicalRefV2RenderPersonRefPalette();
}

// --- Frame-local draft geometry ----------------------------------------------
//
// Unsaved target/distractor boxes (and any pending person_ref selection)
// belong to exactly one source frame. On every frame change
// (updatePhysicalRefFrame's img.onload, above) this is resolved before
// repainting: if the newly displayed frame already has a saved
// physical-reference sample, that sample's own geometry is loaded for
// editing (physicalRefLoadSampleIntoForm); otherwise any leftover draft
// geometry from whichever frame was previously displayed is discarded,
// including the active person_ref selection -- a conservative reset, since
// an active selection alone could otherwise silently attach a new box to
// the wrong frame's draft. There is no automatic carry-forward path
// anywhere in this file.

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
  physicalRefV2ActivePersonRef = null;
  // interpolate_from_previous is a deliberate per-sample decision; it must
  // never remain checked merely because the previously displayed frame (or
  // sample) used interpolation -- that would risk silently creating an
  // interpolated sample on ordinary frame navigation.
  if (interpolateCheckbox) interpolateCheckbox.checked = false;
  physicalRefRenderDistractorList();
  physicalRefV2RenderPersonRefPalette();

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
  physicalRefDrawnDistractors = (s.distractors || []).map((d) => ({
    person_ref: d.person_ref,
    bbox_xyxy: d.bbox_xyxy.slice(),
  }));
  physicalRefV2ActivePersonRef = null;
  physicalRefOnStateChange();
  physicalRefRepaint();
  physicalRefV2RenderPersonRefPalette();
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
  physicalRefV2RenderPersonRefPalette();
}

// --- Save / load --------------------------------------------------------------

function physicalRefGatherProvenance() {
  const bagPath = typeof loadedBag === "string" ? loadedBag : "";
  const bagName = bagPath.split("/").filter(Boolean).slice(-1)[0] || "";
  const evidence = document.getElementById("physicalRefCoordEvidence").value.trim();

  return {
    schema_version: 2,
    contract_version: "tim_physical_target_bbox_v2",
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
    evaluation_window: physicalRefV2EvaluationWindow(),
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
    const res = await fetch("/api/physical_reference_v2/save", {
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
    // The backend validator (physical_target_reference_v2.py) is
    // authoritative; an invalid artifact is never written, regardless of
    // what the frontend thought was fine.
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
    const res = await fetch("/api/physical_reference_v2/load", {
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
    // Covers both ordinary validation failures and the explicit "this is
    // a legacy tim_physical_target_bbox_v1 artifact" rejection -- v1
    // artifacts are never silently migrated or edited here.
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
    if (provenance.evaluation_window) {
      physicalRefV2RenderEvaluationWindow(provenance.evaluation_window);
    }
  }

  // Loading a new artifact replaces the ENTIRE physical-reference editing
  // state, not just the sample table: the known-person palette is
  // re-derived from physicalRefSamples (already replaced above), and the
  // current-frame draft must be reconstructed strictly from the newly
  // loaded artifact -- never left over from whatever was on the canvas
  // before the load (which may be a backend-rejected, never-persisted
  // draft; a stale draft displaying as if it belonged to the freshly
  // loaded artifact is misleading regardless of how it got there).
  // physicalRefSyncDraftToCurrentFrame() is the exact function real frame
  // navigation already uses for this: it loads the (now-loaded)
  // artifact's own sample at the current frame's timestamp if one exists,
  // or otherwise clears the target/distractor/person_ref/interpolation
  // draft -- so, for the current frame, an explicit load behaves exactly
  // like navigating onto a frame of the freshly loaded artifact. It also
  // sets physicalRefActiveIndex/physicalRefV2ActivePersonRef correctly and
  // re-renders the person-ref palette itself, so no separate reset is
  // needed here.
  physicalRefSyncDraftToCurrentFrame();
  physicalRefRenderSampleList();
  physicalRefSetFormStatus(
    "Loaded " + physicalRefSamples.length + " sample(s) from " + data.path +
      " (tim_physical_target_bbox_v2, schema_version=" +
      (provenance ? provenance.schema_version : "?") + ")."
  );
}

async function physicalRefRefreshExistingList() {
  // Schema-version-independent listing, shared with v1 -- it only lists
  // json paths under docs/data/physical_target_references/. Attempting to
  // load a v1-shaped file through physicalRefLoadSelected() above is
  // still safely rejected by the v2 backend.
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

// --- Keyboard frame stepping (M3-v2 approved productivity feature) ---------
//
// Exactly equivalent to moving the existing frame slider by one step and
// calling seek() -- the same path the slider's own oninput uses -- so all
// existing frame-local safety (draft clearing, interpolation reset, no
// autosave) applies automatically with no separate code path to keep in
// sync. Suppressed whenever focus is inside a form control, so typing in
// sequence_id or any other field can never trigger navigation.

function physicalRefV2IsEditableTarget(el) {
  if (!el) return false;
  const tag = (el.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (el.isContentEditable) return true;
  return false;
}

function physicalRefV2StepFrame(delta) {
  if (!shouldOpenPhysicalRefWorkspace()) return;
  const progress = document.getElementById("progress");
  if (!progress || progress.disabled) return;
  const maxIdx = Math.max(0, loadedFrames - 1);
  const current = currentFrameIndex();
  const next = Math.min(maxIdx, Math.max(0, current + delta));
  if (next === current) return;
  progress.value = String(next);
  // The exact same navigation path the slider's own oninput uses -- no
  // separate/duplicated frame-change logic, no autosave, no bbox or
  // person_ref carry-forward beyond what that path already guarantees.
  seek();
}

function physicalRefV2OnKeyDown(evt) {
  if (physicalRefV2IsEditableTarget(evt.target)) return;
  if (!shouldOpenPhysicalRefWorkspace()) return;
  if (evt.key === "ArrowLeft") {
    evt.preventDefault();
    physicalRefV2StepFrame(-1);
  } else if (evt.key === "ArrowRight") {
    evt.preventDefault();
    physicalRefV2StepFrame(1);
  }
}
window.addEventListener("keydown", physicalRefV2OnKeyDown);
