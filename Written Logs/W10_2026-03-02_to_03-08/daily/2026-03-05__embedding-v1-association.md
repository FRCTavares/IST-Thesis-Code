# Daily Log — 2026-03-05 — Embedding v1 End-to-End (Cheap but Real) (Week 10, Day 3)

## Goal
Implement embedding v1 end-to-end (cheap but real). By end of day, association uses an appearance term and you can measure its effect on ID switches proxy and reacquisition.

**Target outcome:**
- Appearance descriptor v1 implemented (HSV histogram + gradient, 16D)
- Plugged into association cost with IoU-based gating
- Comparison report: tracker with vs without appearance
- Quantified benefit OR clear failure reason

**Philosophy:** Start with cheap baseline, keep interface identical for future learned embeddings.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**, all tests use bag replay. Camera integration planned for Week 11. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Target environment | Outdoor tennis court (multi-person, occlusion) |
| Baseline tracker | *(locked from Day 03)* |
| Embedding goal | Improve ID consistency in ambiguous scenes |

---

## Work Plan

### A) Implement appearance descriptor v1 (CPU)
Create a cheap, fast appearance descriptor suitable for real-time on Pi.

- [ ] Design descriptor with two components:
  - **HSV colour histogram:** 8×8×8 bins (512 dim)
  - **Gradient magnitude:** Sobel edge map, spatial pooling to 4×4 grid (16 dim)
- [ ] Compress to 16D total:
  - Histogram: PCA or random projection (512 → 8 dim)
  - Gradient: Keep as is (16 dim) OR downsample further
  - OR: Just use 16D gradient + 8D colour (24D total)
- [ ] Implement extraction function:
  ```python
  def extract_appearance(bbox, image):
      crop = extract_crop(image, bbox, pad=0.1)
      
      # Colour histogram
      hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
      hist = cv2.calcHist([hsv], [0,1,2], None, [8,8,8])
      hist_norm = hist.flatten() / (hist.sum() + 1e-6)
      
      # Gradient magnitude
      gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
      grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
      grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
      grad_mag = np.sqrt(grad_x**2 + grad_y**2)
      grad_pooled = spatial_pool(grad_mag, grid_size=4)  # 16 values
      
      # Combine (with PCA/projection if needed)
      appearance = np.concatenate([hist_norm[:8], grad_pooled])
      return appearance  # 24D or compress to 16D
  ```
- [ ] Optimize for speed (target: < 2 ms per detection on Pi)
- [ ] Test extraction on sample crops
- **Deliverable:** `thesis_vision_utils/appearance.py`
- Notes: *(fill)*

**Performance budget:**
- Target: < 2 ms per detection (5 detections → 10 ms)
- Acceptable: < 5 ms per detection (still within 200 ms budget)

**Design decisions:**
- Descriptor dimension: *(16D / 24D / other)*
- Compression method: *(PCA / random projection / none)*
- HSV bins: *(8×8×8 / 4×4×4)*
- Gradient grid: *(4×4 / 2×2)*

### B) Plug into association gating
Integrate appearance cost into tracker association with IoU-based gating.

- [ ] Modify tracker association cost:
  ```python
  # Current
  cost_matrix = 1.0 - iou_matrix(detections, tracks)
  
  # New (with appearance)
  iou_cost = 1.0 - iou_matrix(detections, tracks)
  app_cost = appearance_distance_matrix(detections, tracks)
  
  # Gating: only use appearance when IoU ambiguous
  ambiguous_mask = (iou_matrix > iou_threshold_low) & (iou_matrix < iou_threshold_high)
  # e.g., iou_threshold_low = 0.3, iou_threshold_high = 0.7
  
  cost_matrix = iou_cost.copy()
  cost_matrix[ambiguous_mask] = w_iou * iou_cost[ambiguous_mask] + w_app * app_cost[ambiguous_mask]
  ```
- [ ] Implement appearance distance:
  - **Option 1:** L2 distance (Euclidean)
  - **Option 2:** Cosine distance
  - **Option 3:** Chi-squared for histograms
  - **Decision:** *(fill)*
- [ ] Make gating parameters configurable:
  - `iou_threshold_low`: 0.3 (below this, appearance not helpful)
  - `iou_threshold_high`: 0.7 (above this, IoU sufficient)
  - `w_iou`: 0.7
  - `w_app`: 0.3
- [ ] Add appearance extraction to track state:
  - Store `appearance_vec` in Track object
  - Update on each successful association
  - Use exponential moving average: `app_t = alpha * app_new + (1-alpha) * app_old`
- [ ] Log appearance cost for diagnostics
- **Deliverable:** Updated baseline tracker with appearance integration
- Notes: *(fill)*

**Distance metrics comparison:**
| Metric | Formula | Best for | Computational cost |
|--------|---------|----------|-------------------|
| L2 | `sqrt(sum((a-b)^2))` | General | Low |
| Cosine | `1 - dot(a,b)/(norm(a)*norm(b))` | Direction | Low |
| Chi-squared | `sum((a-b)^2/(a+b))` | Histograms | Medium |

### C) Run eval suite
Compare baseline tracker with and without appearance term.

- [ ] Create two tracker configs:
  - `config/tracker_<baseline>_no_app.yaml` (w_app = 0.0)
  - `config/tracker_<baseline>_with_app.yaml` (w_app = 0.3)
- [ ] Run evaluation on all scenarios:
  - clean
  - occlusion_1s
  - ambiguous_crossing
- [ ] Compare metrics:
  - **Tracking quality:** Switches per minute, ID switches proxy, reacquire time
  - **Runtime:** track_ms p95 (appearance extraction overhead)
  - **Association:** Appearance cost statistics (mean, p95, distribution)
- [ ] Generate comparison report
- **Deliverable:** `reports/compare/W10_embedding_v1_compare.md`
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] `thesis_vision_utils/appearance.py` with descriptor extraction
- [ ] Baseline tracker updated with appearance cost (gated)
- [ ] Evaluation suite run with and without appearance
- [ ] `reports/compare/W10_embedding_v1_compare.md` with quantified impact

### Appearance descriptor v1 specifications

| Component | Implementation | Dimensions | Computation time |
|-----------|----------------|------------|------------------|
| Colour histogram | HSV 8×8×8 → PCA to 8D | 8 | — ms |
| Gradient magnitude | Sobel + 4×4 spatial pool | 16 | — ms |
| Total descriptor | Concatenated | 24D | — ms |
| Distance metric | *(L2 / Cosine / Chi-sq)* | N/A | — ms |

**Performance:**
- Extraction time per detection: — ms (p95)
- Total overhead: — ms for 5 detections
- Within budget? *(Yes / No)*

### Embedding v1 impact

**Scenario comparison:**

| Scenario | Metric | Without appearance | With appearance | Improvement |
|----------|--------|-------------------|-----------------|-------------|
| clean | Switches/min | — | — | — |
| clean | track_ms p95 | — | — | Overhead |
| occlusion_1s | Reacquire time p95 | — | — | — |
| occlusion_1s | Correct ID % | — | — | — |
| ambiguous_crossing | Switches/min | — | — | — |
| ambiguous_crossing | ID switches | — | — | — |

**Appearance cost statistics (ambiguous cases only):**
- Mean appearance distance: —
- p95 appearance distance: —
- Correlation with correct match: *(fill)*

**Overall assessment:**
*(Does appearance help? In which scenarios? What is the failure mode if it doesn't help?)*

**Possible outcomes:**
1. **Success:** Appearance reduces ID switches in ambiguous/occlusion scenarios with acceptable overhead
2. **Partial success:** Helps in some scenarios but not others (document which and why)
3. **Failure:** No benefit or degrades performance (document why: not discriminative enough? Too noisy? Overhead too high?)

**Next steps for embedding:**
- *(If successful)* Fine-tune weights and gating thresholds
- *(If partial)* Identify failure modes, improve descriptor
- *(If failure)* Consider learned embedding (ReID model) or abandon appearance term
- *(Always)* Keep interface ready for future learned embeddings

---

## Issues / Risks
- *(Fill as they arise)*

**Known challenges:**
- HSV histogram may not be discriminative for similar clothing
- Indoor test data may not represent outdoor appearance variation (lighting, shadows)
- Gradient features may be sensitive to image quality/resolution
- Limited multi-person crossing data without camera

---

## Next steps (Day 06)
- [ ] Write outdoor test protocol (flight-test style)
- [ ] Define tennis court scenarios (5m, 10-20m, lateral, crossing)
- [ ] Specify success criteria with numbers
- [ ] Create test runner template with pre-flight checklist

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Comparison report: `../../reports/compare/W10_embedding_v1_compare.md`
- Appearance module: `../../thesis_vision_utils/appearance.py`
- Tracker config (with appearance): `../../config/tracker_<baseline>_with_app.yaml`
