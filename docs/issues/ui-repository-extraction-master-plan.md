# UI Repository Extraction — Master Migration Plan

## Document status

**Status:** active Issue #55 execution specification; migration branch started 1 September 2026; source extraction not yet started.

**Execution branch:** `issue-55-ui-repository-extraction-20260901`

**Execution baseline:** `8e88a471c87b4224d1e5b830b59eacfe86fb159b`

**Created:** 29 August 2026.

**Source repository:** `FRCTavares/IST-Thesis-Code`

**Intended frontend repository:** `FRCTavares/IST-Thesis-UI`

**Intended Pi checkout:** `~/Desktop/IST-Thesis-UI`

**Current frontend location:** `IST-Thesis-Code/live-ui/`

This document is the execution authority for separating the browser-facing
thesis dashboard from the ROS/scientific code repository.

A future session should be able to read this document, inspect the current Git
state, identify the highest completed migration stage, and continue without
repeating the architectural investigation.

The migration must preserve the scientifically validated runtime and must
remain easy to roll back at every material checkpoint.

---

# 1. Executive decision

The repository split is approved in principle, but it is intentionally narrow.

Phase A extracts only the existing React/Vite live dashboard.

The final dependency direction is:

    IST-Thesis-UI
        |
        | HTTP + WebSocket + MJPEG
        v
    IST-Thesis-Code
        |
        | ROS 2
        v
    camera / perception / tracker / TIM-MARS / control

The UI repository is a browser client.

`IST-Thesis-Code` remains the authority for:

- ROS;
- hardware/runtime integration;
- target authority;
- control-sensitive API behavior;
- bags;
- models;
- scientific evaluation;
- experiment scripts;
- physical-reference data;
- annotation backends;
- runtime provenance.

The migration must not create a circular repository dependency.

---

# 2. Primary objective

Move presentation ownership out of the scientific/runtime repository while
preserving all runtime behavior and operator safety.

The desired result is:

1. `IST-Thesis-UI` can be installed, built, tested, and developed independently;
2. it communicates with the Pi runtime only through explicit external
   interfaces;
3. `IST-Thesis-Code` does not depend on UI source files;
4. ROS and scientific code never need the UI repository in order to build,
   evaluate bags, or run non-dashboard experiments;
5. the familiar thesis operator workflow can retain a compatibility launcher
   if useful;
6. rollback never requires Git-history rewriting.

---

# 3. Hard architectural invariants

The following are non-negotiable.

## 3.1 Dependency direction

Allowed:

    IST-Thesis-UI -> network/runtime contract -> IST-Thesis-Code

Forbidden:

    IST-Thesis-Code -> imports/files from IST-Thesis-UI

Forbidden:

    IST-Thesis-UI -> Python or ROS source imports from IST-Thesis-Code

Forbidden:

    IST-Thesis-UI -> direct access to bags, models, reports, thesis_env,
                     ROS installation paths, or evaluator modules

The optional Thesis-Code compatibility launcher described later is an operator
convenience exception, not a build/runtime/scientific dependency. It may
execute the external UI repository launcher when explicitly requested, but
Thesis-Code must remain fully functional when the UI repository is absent.

## 3.2 Control authority

The browser is never selected-person authority.

TIM-MARS remains the selected-person identity authority.

Moving the frontend must not weaken:

- target-selection semantics;
- target clear/reset semantics;
- authority-generation tracking;
- model/tracker reconfiguration protections;
- validated-target ownership.

## 3.3 Scientific independence

The following must remain usable when `IST-Thesis-UI` is absent:

- ROS build;
- live stack without dashboard frontend;
- deterministic replay;
- physical-reference evaluation;
- annotation backend;
- scientific analysis;
- report generation;
- test suites unrelated to browser presentation.

---

# 4. Investigation record

A deep repository dependency audit and a targeted final forensic audit were
performed before this plan was written.

The audits established that `live-ui/` is a clean browser frontend boundary,
whereas `tools/bag_annotation_ui/` is a mixed browser/backend/scientific
application and must not be moved wholesale.

---

# 5. Current execution Git state

The migration execution branch was created on 1 September 2026 after the
previously stacked thesis work had been integrated into `main`.

Execution state:

    branch:
    issue-55-ui-repository-extraction-20260901

    branch base / current main at execution start:
    8e88a471c87b4224d1e5b830b59eacfe86fb159b

The worktree was clean when the execution branch was created.

The earlier 29 August cross-branch investigation remains useful historical
planning evidence, but it is not the execution baseline anymore.

The Issue #32/#58 evidence slice, Issue #74 controller slice, Issue #51
host/network slice, and Issue #27 prospective held-out freeze were all merged
before this branch was created.

---

# 6. Current frontend-boundary verification

The 1 September execution audit reconfirmed that `live-ui/` remains a clean
browser-facing extraction boundary.

Current tracked frontend files:

    45

Current `live-ui` tree SHA:

    634754dd789c32ba1d75216855a9dd77e187774b

The much larger local directory size is dominated by ignored/generated
artifacts such as:

- `live-ui/node_modules/`;
- `live-ui/dist/`;
- `*.tsbuildinfo`.

Those artifacts are not authoritative source and must not be transferred.

The runtime boundary remains unchanged:

    IST-Thesis-UI
        |
        | HTTP + WebSocket + MJPEG
        v
    IST-Thesis-Code
        |
        | ROS 2
        v
    camera / perception / tracker / TIM-MARS / control

The current frontend already supports numeric tracker-ID target selection
through `POST /api/target`.

This is the required bootstrap interaction for the field UI. No tap-to-select
mechanism is required by the thesis workflow.

Selecting tracker ID `N` means:

    bootstrap TIM-MARS from the physical person currently represented by N

It does not mean:

    permanently follow tracker ID N

TIM-MARS remains free to reacquire the same physical selected person under a
different tracker ID, and the UI must display the resulting current TIM target
rather than treating the bootstrap tracker ID as permanent identity.

---

# 7. Pre-migration functional baseline

The green 29 August frontend/runtime baseline remains the last recorded
full pre-migration validation:

- Node.js `v20.20.1`;
- npm `10.8.2`;
- Python `3.12.3`;
- clean npm install: PASS;
- production TypeScript/Vite build: PASS;
- installed dependency consistency: PASS;
- local Vite HTTP smoke: PASS;
- annotation/scientific focused regression suite: 337 passed;
- dashboard/backend focused regression suite: 17 passed.

These results are historical baseline evidence, not permission to skip current
validation.

Before deleting `live-ui/` from Thesis-Code, the migration must establish a
fresh standalone frontend baseline in `IST-Thesis-UI` and rerun the relevant
Thesis-Code contract tests.

---

# 8. Current migration-sensitive hashes

The execution audit recorded the following current sentinels.

## UI launcher

    tools/start_ui_stack.sh
    d842f0742ba09e3bb889e794edfb4c4d1761e7a1ca2ece69b39f44cdce0d49a1

## Dashboard bridge

    ros2_ws/src/thesis_bringup/thesis_bringup/dashboard/dashboard_bridge_node.py
    e0c89adcef7a5b578c149f50ee4b70a5115a6e16b9def568ea21758d486c7086

## Frontend package file

    live-ui/package.json
    fccba2ebe3ea484258a9def29a97c1744b5edac823ea69c35eb1af0557f9beab

## Frontend lockfile

    live-ui/package-lock.json
    3c58cdc7abdb2621430552a3503185a4a80252c14cad753d91efd4cb09ac7fa4

## Frontend runtime configuration

    live-ui/src/services/config.ts
    8d6ea7d673f1b1132ca0ca1e7a5001a8c9f8bf38bbcef7b2dcc68c452232661c

## Frontend telemetry types

    live-ui/src/types/dashboard.ts
    1e5f6623f791ba5fcf3ffa1f23034b342447ba02f09fea52c944f690cc7adbad

## Frontend HTTP client

    live-ui/src/features/dashboard/services/dashboardApi.ts
    85fdd407c4c73b0a7c44571875cb899aa0fc65ce1535cb7efc57735bbc661003

## Frontend WebSocket client

    live-ui/src/features/dashboard/services/dashboardSocket.ts
    f0442745c943421dd3aaf44ac777779e19a1ab88ff50b218842fdbb973c54419

These are execution sentinels, not permanent version pins.

If one changes before source extraction, inspect that contract delta before
continuing.

---

# 9. Known pre-existing frontend conditions

These conditions existed before extraction and must not be mistaken for
migration regressions.

## 9.1 Build-generated source-tree artifacts

The current TypeScript build can emit untracked generated files beside the
TypeScript configuration sources:

- `tailwind.config.js`;
- `tailwind.config.d.ts`;
- `vite.config.js`;
- `vite.config.d.ts`.

The baseline run also generated ignored `*.tsbuildinfo` files.

These files are not authoritative source and must never be transferred or
committed.

Stopping this emission belongs to later frontend hardening under Issue #55.

## 9.2 npm security findings

The baseline clean install reported:

- 6 vulnerabilities;
- 1 low;
- 1 moderate;
- 4 high.

Do not run:

    npm audit fix --force

during source extraction.

Dependency remediation is separate because it can change application behavior.

## 9.3 Bundle warning

The existing production build emits a JavaScript chunk above Vite's 500 kB
warning threshold.

That warning is not an extraction blocker.

Code splitting is later frontend work.

## 9.4 Duplicate/indirect WebSocket provider structure

The source contains:

    src/features/dashboard/providers/dashboardWebSocketProvider.ts

    src/features/dashboard/services/dashboardWebSocketProvider.ts

    src/features/dashboard/services/dashboardWebSocketProvider.tsx

    src/features/dashboard/services/dashboardWebSocketProviderImpl.tsx

The structure contains forwarding layers and duplicate implementation.

It is known technical debt.

Do not clean it during the pure source-transfer commit.

---

# 10. Phase A scope — move now

Phase A extracts the complete tracked `live-ui/` application into the root of a
new dedicated repository.

Source:

    IST-Thesis-Code/live-ui/

Destination:

    IST-Thesis-UI/

The destination must initially preserve frontend behavior.

The first version of the new repository should remain a single straightforward
React application.

Do not introduce a monorepo merely in anticipation of future work.

---

# 11. Intended UI repository structure

Initial target:

    IST-Thesis-UI/
        .env.example
        .gitignore
        README.md
        MIGRATION_PROVENANCE.md
        components.json
        index.html
        package.json
        package-lock.json
        postcss.config.js
        tailwind.config.ts
        tsconfig.json
        tsconfig.app.json
        tsconfig.node.json
        vite.config.ts
        src/
        tools/

Possible future structure such as:

    apps/dashboard/
    apps/annotation/

is explicitly deferred.

It may be introduced only if more than one real frontend application needs to
coexist.

---

# 12. Explicit Phase A non-goals

Do not use this migration to change:

- detector model;
- inference resolution;
- tracker;
- tracker parameters;
- TIM-MARS;
- appearance model;
- target-memory semantics;
- ROS topics;
- coordinate conventions;
- camera configuration;
- control behavior;
- physical-reference schemas;
- annotations;
- bag structure;
- scientific evaluator behavior;
- replay methodology;
- frontend visual design;
- npm dependency versions;
- authentication design;
- CORS policy;
- runtime bind policy;
- annotation UI;
- repository-history size;
- model-file storage;
- unrelated TODO items.

The extraction should be behavior-preserving first.

---

## 12.1 Approved post-extraction field UI target

The pure repository-transfer checkpoint remains behavior-preserving.

Immediately after standalone extraction is proven, Issue #55 frontend
hardening is explicitly approved to simplify the dashboard into an
iPhone-first field interface.

The phone UI must prioritize:

- live MJPEG video;
- numbered person/track overlays;
- numeric tracker-ID selection;
- one explicit `SELECT` action;
- one explicit `CLEAR TARGET` action;
- TIM-MARS state;
- current TIM-MARS target track ID;
- connection/backend status;
- concise command success/failure feedback.

The phone UI does not need to reproduce the current desktop information
density.

The following current dashboard elements are not required in the final
field-oriented UI unless a concrete thesis/operator requirement is discovered:

- performance charts;
- large metrics grids;
- recording-history UI;
- logging workspaces;
- desktop dashboard tabs;
- model switching;
- tracker switching;
- duplicate target-selection surfaces;
- nonessential configuration controls.

In the frozen flight profile, model/tracker switching must not be presented as
ordinary available operator actions.

Backend protection remains authoritative even if frontend controls are removed.

The final design must preserve the identity distinction between:

1. the tracker ID selected only to bootstrap the physical person; and
2. the current tracker ID associated with that physical person by TIM-MARS.

The frontend is presentation and operator-command transport only.
TIM-MARS remains the selected-person identity authority.

---

# 13. Authoritative file-disposition matrix

| Current component | Phase A action | Final owner | Reason |
|---|---|---|---|
| `live-ui/**` | MOVE | IST-Thesis-UI | Browser presentation |
| `tools/start_ui_stack.sh` | REPLACE/SHIM | split | Compatibility entry point |
| dashboard frontend launcher | CREATE | IST-Thesis-UI | Frontend runtime ownership |
| `dashboard_bridge_node.py` | STAY | IST-Thesis-Code | ROS/runtime authority |
| dashboard ROS helpers | STAY | IST-Thesis-Code | Runtime implementation |
| `web_video_server` integration | STAY | IST-Thesis-Code | ROS video transport |
| `tools/start_live_stack.sh` | STAY | IST-Thesis-Code | Runtime orchestration |
| `tools/lib/live_*` | STAY | IST-Thesis-Code | Runtime orchestration |
| `thesis_msgs` | STAY | IST-Thesis-Code | ROS contract |
| perception nodes | STAY | IST-Thesis-Code | Runtime/scientific |
| tracker nodes | STAY | IST-Thesis-Code | Runtime/scientific |
| TIM-MARS | STAY | IST-Thesis-Code | Identity authority |
| control node | STAY | IST-Thesis-Code | Vehicle/control authority |
| `models/` | STAY | IST-Thesis-Code | Runtime artifacts |
| `bags/` | STAY | IST-Thesis-Code | Experimental evidence |
| `reports/` | STAY | IST-Thesis-Code | Scientific outputs |
| `tools/analysis/` | STAY | IST-Thesis-Code | Scientific evaluation |
| `tools/experiments/` | STAY | IST-Thesis-Code | Experimental runtime |
| `tools/bag_annotation_ui/**` | STAY | IST-Thesis-Code | Mixed scientific application |
| `thesis_env/` | STAY local/ignored | IST-Thesis-Code | Scientific Python env |

---

# 14. Why dashboard_bridge_node must stay

The dashboard bridge is not presentation code.

It owns or participates in:

- ROS topic subscriptions;
- ROS publishers;
- target selection;
- target clearing;
- TIM-MARS command readiness;
- model parameter services;
- tracker parameter services;
- target-authority generation;
- target-authority provenance;
- coordinate normalisation;
- model availability discovery;
- runtime telemetry;
- CPU/memory/temperature metrics;
- HTTP server;
- WebSocket server.

Those responsibilities belong to the runtime repository.

The frontend should only know its documented external interface.

---

# 15. Current live dashboard external interfaces

The browser depends on exactly three classes of runtime interface.

## HTTP

Default:

    http://<runtime-host>:8090

## WebSocket

Default:

    ws://<runtime-host>:8765

## MJPEG

Default:

    http://<runtime-host>:8080/stream?topic=/camera/dashboard&type=mjpeg&qos_profile=sensor_data&quality=45

No source-code import across repositories is required.

---

# 16. Current HTTP API contract

The browser currently consumes four live dashboard routes.

## 16.1 GET /api/models

Purpose:

Return supported detector models and availability.

Representative shape:

    {
      "ok": true,
      "models": [
        {
          "key": "model-key",
          "hef_file": "model.hef",
          "hef_path": "/local/path/model.hef",
          "available": true
        }
      ]
    }

The local HEF path being returned is existing behavior.

Do not alter it during extraction.

## 16.2 POST /api/model

Request:

    {
      "model": "model-key"
    }

Relevant result classes:

- 400 unsupported model;
- 409 runtime switching protected/disabled;
- 500 runtime failure;
- 503 runtime switching service unavailable;
- 504 runtime timeout;
- 200 successful switch only when explicitly enabled.

Model-switch requests also reset target authority before a permitted
reconfiguration path.

## 16.3 POST /api/tracker

Request:

    {
      "tracker": "sort"
    }

Supported tracker keys currently include:

- `sort`;
- `ocsort`;
- `bytetrack`;
- `deepsort`.

Relevant result classes:

- 400 unsupported tracker;
- 409 protected frozen runtime;
- 500 runtime failure;
- 503 parameter service unavailable;
- 504 timeout;
- 200 success only when explicitly allowed.

Tracker-switch requests also reset target authority.

## 16.4 POST /api/target

Request:

    {
      "target": 12
    }

or clear:

    {
      "target": null
    }

The backend also accepts defined semantic clear forms internally.

Major result classes:

- 400 invalid target;
- 503 TIM-MARS command subscriber unavailable;
- 200 selection or clear accepted.

This route is safety-relevant.

It stays in Thesis-Code.

---

# 17. Stale /api/replay documentation

The existing frontend README mentions:

    POST /api/replay

The audited current React HTTP client does not use `/api/replay`.

The audited current live dashboard bridge does not implement `/api/replay`.

This is pre-existing documentation drift.

After extraction, correct the documentation.

Do not implement a new replay route merely to match stale documentation.

The historical Issue #55 wording also asks for API contract tests for
"status". The audited dashboard bridge does not currently expose an HTTP
`/api/status` route; live status/telemetry is carried primarily through the
WebSocket contract. Phase A must not invent `/api/status` merely to satisfy
ambiguous historical wording. Resolve the intended status contract explicitly
during later Issue #55 backend hardening.

---

# 18. Target-authority contract

The target command path is:

    browser
        |
        | POST /api/target
        v
    dashboard_bridge_node
        |
        +--> /target_memory_mars/select
        |
        +--> /target_memory_mars/clear
        |
        v
    TIM-MARS

The dashboard bridge verifies that the expected TIM-MARS subscriber exists
before claiming successful command acceptance.

The bridge maintains a target-authority generation.

Operator select and clear operations advance authority state.

Target-authority events may be persisted to the configured JSONL event log.

A frontend extraction must not move any of this logic.

---

# 19. Frozen-flight reconfiguration contract

Normal validated live-stack operation currently configures:

    runtime_reconfiguration_enabled = false

and:

    enable_container_model_switch_api = false

Therefore the UI may visually expose model/tracker controls while the validated
runtime correctly rejects the actual switch.

Expected frozen-profile rejection:

    HTTP 409

This is deliberate protection.

An important current side effect must also be preserved during pure
extraction: both model-switch and tracker-switch handlers reset target
authority before checking `runtime_reconfiguration_enabled`. Therefore a
protected request that ultimately returns HTTP 409 still advances the
target-authority generation and issues the corresponding target clear/reset
semantics.

A migrated frontend receiving HTTP 409 for model/tracker switching is not a
migration failure, and the accompanying authority reset is part of the audited
pre-migration behavior.

Later Issue #55 work may improve the browser UX or deliberately reconsider
these semantics, but any semantic change requires explicit target-authority
review and tests. It must not occur accidentally during repository extraction.

The backend protection must remain authoritative.

---

# 20. WebSocket telemetry producer contract

The dashboard bridge exposes WebSocket telemetry on port 8765.

On connection it sends the current snapshot immediately.

Changed state is subsequently broadcast to connected clients.

The bridge currently uses approximately:

- publish target: 30 Hz;
- ping interval: 20 seconds;
- ping timeout: 20 seconds.

Current metrics schema version:

    3

Current detector-output rolling window:

    3 seconds

Current warning thresholds include:

    e2e_det_ms = 120
    pub_dt_ms = 120

---

# 21. WebSocket top-level telemetry fields

The audited backend state includes:

- `tracks`;
- `detections`;
- `target`;
- `target_requested`;
- `target_active`;
- `target_authority_source`;
- `target_authority_generation`;
- `target_authority_reason`;
- `target_authority_session_id`;
- `target_authority_event_log_path`;
- `target_memory`;
- `camera_input_fps`;
- `det_out_fps`;
- `e2e_det_ms`;
- `pub_dt_ms`;
- `metrics_schema_version`;
- `metric_windows`;
- `metric_thresholds_ms`;
- `replay_progress`;
- `inference_resolution`;
- `system`.

`target_memory` is a JSON status payload produced by TIM-MARS and should remain
forward-compatible with additional status fields.

---

# 22. Existing frontend telemetry typing weakness

The backend currently publishes some target-authority fields that the
TypeScript `DashboardTelemetry` interface does not explicitly declare.

The browser currently does:

    JSON.parse(...)

followed by a TypeScript cast rather than runtime schema validation.

This weakness predates extraction.

Do not silently introduce a schema framework during the pure move.

Issue #55 should later add deterministic API/WebSocket contract testing and may
add runtime validation if justified.

---

# 23. Detection and track overlay contract

Tracks are represented approximately as:

    {
      "id": integer,
      "x": number,
      "y": number,
      "w": number,
      "h": number
    }

Detections are represented approximately as:

    {
      "x": number,
      "y": number,
      "w": number,
      "h": number,
      "label": string,
      "score": number
    }

Box coordinates sent to the browser are normalised.

The dashboard bridge's audited implementation normalises detections/tracks
using the current source-camera reference dimensions:

    camera_ref_w
    camera_ref_h

The live launcher sets these from the active source capture dimensions.

Timing telemetry may update the source-camera reference dimensions when valid
image dimensions are available.

---

# 24. Existing coordinate documentation drift

The old frontend README says overlay normalisation depends on bridge
`img_w/img_h` matching the detector coordinate basis.

The audited current implementation uses:

    camera_ref_w
    camera_ref_h

for the final normalisation sent to the dashboard.

`img_w/img_h` remain relevant to inference-resolution telemetry but are not the
same thing as the source-camera reference dimensions.

The documentation should be corrected after extraction.

The runtime must not be changed merely to match stale prose.

---

# 25. Video contract

Video remains produced from Thesis-Code runtime infrastructure.

ROS topic:

    /camera/dashboard

Browser stream:

    http://<runtime-host>:8080/stream?topic=/camera/dashboard&type=mjpeg&qos_profile=sensor_data&quality=45

The `sensor_data` QoS selection is intentional for the image publisher
semantics.

The browser uses an image element for MJPEG and draws overlays separately.

IST-Thesis-UI does not own:

- camera capture;
- ROS image publication;
- dashboard image generation;
- image QoS;
- `web_video_server`.

---

# 26. Frontend environment contract

Current `.env.example` defines:

    VITE_DASHBOARD_DATA_MODE=backend

    VITE_DASHBOARD_API_BASE_URL=http://127.0.0.1:8090

    VITE_DASHBOARD_WS_URL=ws://127.0.0.1:8765

Current supported modes:

- `backend`;
- `mock`;
- `offline`.

The frontend currently normalises localhost-style API/WS hosts to the active
browser hostname in remote-browser use.

The video URL is built using the browser hostname and does not currently have a
separate Vite environment variable.

Preserve this behavior during source extraction.

---

# 27. Network and security boundary

The audited dashboard bridge currently defaults to:

    api_host = 0.0.0.0

    ws_host = 0.0.0.0

The API currently emits:

    Access-Control-Allow-Origin: *

There is no current authentication layer on the dashboard control API.

This is especially relevant because `/api/target` is an operator command
surface.

Repository extraction does not itself fix this.

The source move should preserve behavior first.

Issue #55 must subsequently establish an intentional security policy.

---

# 28. Required post-extraction security goals

Issue #55 must eventually decide and enforce:

- conservative default API binding;
- conservative default WebSocket binding;
- explicit remote-access configuration;
- intentional CORS allowlist;
- whether trusted local/Tailscale operation alone is sufficient;
- whether explicit authentication/authorization is required;
- behavior for control routes;
- no committed secrets;
- no assumption that Vite environment variables are secret storage.

The security design must not reduce operator usability by silently breaking the
validated local workflow.

It also must not expose control routes to arbitrary networks for convenience.

---

# 29. Annotation UI — Phase A decision

Do not move:

    tools/bag_annotation_ui/

during dashboard extraction.

It is not simply frontend code.

The audit showed that it mixes:

- FastAPI;
- static browser UI;
- rosbag parsing;
- ROS message deserialization;
- OpenCV image handling;
- annotations;
- physical-reference semantics;
- evaluator invocation;
- replay launch;
- report generation;
- repository filesystem ownership.

---

# 30. Annotation-specific hard couplings

Examples identified during audit include:

## tim_clean_ui.py

Repository root derived relative to source location.

Moving the file naively would change its interpretation of the thesis root.

## tim_ui_backend.py

Uses repository/current-working-directory assumptions for:

- bags;
- reports;
- replay logs;
- experiment scripts.

## tim_ui_bag_cache.py

Depends directly on ROS data infrastructure including concepts such as:

- `rosbag2_py`;
- `cv_bridge`;
- ROS deserialization;
- runtime message types.

## tim_ui_evaluation.py

Invokes thesis scientific evaluator code and writes thesis reports.

## physical-reference adapters

Depend directly on physical-reference and evaluator modules under scientific
analysis tooling.

These responsibilities stay in Thesis-Code.

---

# 31. Annotation UI status in thesis execution

Current thesis planning intentionally pauses additional annotation-UI feature
work unless a concrete defect prevents scientifically valid Issue #25
evidence.

CVAT is currently the preferred human annotation frontend for the active
physical-reference workflow.

Therefore there is no justification for increasing migration risk by including
annotation tooling in Phase A.

---

# 32. Possible future annotation Phase B

If later justified, the desired boundary is:

    IST-Thesis-UI browser annotation frontend
        |
        | explicit HTTP contract
        v
    IST-Thesis-Code annotation service
        |
        +--> rosbag2
        +--> cv_bridge
        +--> evaluators
        +--> bags
        +--> physical references
        +--> reports
        +--> replay scripts

Possible future presentation candidates include browser HTML/CSS/JavaScript.

They must not move until the frontend stops assuming same-origin relative
backend routes and an explicit service URL/API contract exists.

Phase B is not required for Phase A completion.

---

# 33. Git-history strategy

The authoritative Thesis-Code repository has a historically large Git object
database because experimental binary data has existed in its history.

The safest Phase A strategy is therefore:

**clean source import with explicit provenance**, not history rewriting.

The new UI repository should record:

- source repository;
- source commit;
- source `live-ui` tree SHA;
- migration date;
- link/path to this master plan;
- statement that older frontend file history remains available in
  IST-Thesis-Code.

This avoids manipulating the large historical repository to extract a small
frontend tree.

---

# 34. History-preservation prohibition

Never:

- rewrite authoritative Thesis-Code history;
- run destructive `filter-repo` against the authoritative checkout;
- force-push rewritten Thesis-Code history.

If filtered historical extraction is ever desired, use only a disposable clone
and review the result as an independent new repository.

Perfect history preservation is lower priority than scientific repository
safety.

---

# 35. MIGRATION_PROVENANCE.md requirement

The initial UI repository must contain:

    MIGRATION_PROVENANCE.md

It should record at minimum:

- source repository: `FRCTavares/IST-Thesis-Code`;
- actual execution source commit;
- actual source `live-ui` tree SHA;
- planning tree SHA:
  `634754dd789c32ba1d75216855a9dd77e187774b`;
- migration date;
- source repository path of this plan;
- the Thesis-Code commit SHA containing the reviewed version of this plan;
- note that original history remains in Thesis-Code.

Do not blindly reuse the planning source commit if `main` has advanced.

The actual migration commit must be measured at execution time.

---

# 36. New GitHub repository policy

Intended repository name:

    FRCTavares/IST-Thesis-UI

Safe initial visibility default:

    private

At M0 the operator may explicitly choose public visibility instead. In the
absence of an explicit visibility decision, create the repository as private;
visibility is reversible later, while unintended public creation is broader
exposure.

Do not create the repository until Phase M0 confirms no naming collision.

Do not put tokens, credentials, Tailscale keys, ROS secrets, or local machine
configuration into the repository.

---

# 37. Local checkout policy

Intended Pi path:

    ~/Desktop/IST-Thesis-UI

Before creation verify that:

- the path does not already exist;
- no other Git worktree uses it;
- no repository already exists on GitHub with conflicting purpose.

The forensic audit found no current local collision at planning time.

Recheck at execution time.

---

# 38. Migration branch policy

Do not perform UI extraction on a scientific issue branch.

Especially do not use:

    issue-58-lightweight-vs-integrated

The migration should run from the then-current intended `origin/main` using a
dedicated branch or worktree.

Recommended branch:

    chore/extract-thesis-ui-repository

A worktree is preferred so active scientific work remains untouched.

---

# 39. Planning branch versus execution branch

This document itself is being prepared on:

    chore/ui-repository-extraction-plan-20260829

based on the 29 August `origin/main`.

That does not mean the later migration must execute from that historical
commit.

At execution time:

1. fetch current `origin/main`;
2. ensure active scientific branches are safely checkpointed;
3. create a fresh migration branch/worktree from the intended current main;
4. re-run only the M0 sentinel checks.

## 39.1 Planning publication and merge gate

This planning branch was created from the audited `origin/main` while the
active Issue #58 branch contained newer scientific and TODO reconciliation
work that had not yet been integrated into main.

It is safe to commit and push this planning branch independently, but before
merging it into `main`:

1. fetch the then-current `origin/main`;
2. inspect divergence from the planning branch;
3. inspect `docs/TODO_LIST.md` specifically;
4. if Issue #58 or other scientific work has landed, update/rebase the planning
   branch onto that current state;
5. resolve any TODO conflict by preserving both the newer scientific state and
   the Issue #55 pointer to this plan;
6. rerun `git diff --check` and the focused planning verification.

Never resolve a planning-branch conflict by discarding newer scientific
evidence, TODO status, or the repository-extraction pointer.

If this planning branch lands first, later Issue #58 integration must likewise
preserve the plan pointer.

---

# 40. Commit policy

Only commit coherent, noticeable changes.

Commit format:

    DD-MM-YY: small explanation of what was done

Recommended Thesis-Code checkpoints:

- master migration plan;
- compatibility/docs/test boundary;
- old frontend removal after successful integration;
- later Issue #55 hardening as separate coherent work.

Avoid tiny mechanical commits for every file.

---

# 41. Phase M0 — execution preflight

No file transfer may occur before all M0 conditions pass.

Required:

- active scientific branch safely checkpointed;
- execution worktree based on intended current main;
- tracked working tree clean;
- `git status --short --ignored` reviewed;
- no root `log/`;
- no root `hailort.log`;
- `thesis_env/` ignored;
- no frontend generated `.js/.d.ts` config artifacts;
- current `live-ui` tree SHA recorded;
- migration-sensitive hashes compared with this plan;
- external repo/path collision check completed;
- current TODO and Issue #55 reviewed.

If a sentinel differs, perform a targeted delta audit.

Do not repeat the full forensic investigation unless architecture changed.

---

# 42. M0 abort conditions

Stop before migration if:

- current main no longer contains `live-ui/`;
- dashboard bridge moved or changed ownership;
- HTTP API materially changed;
- WebSocket producer materially changed;
- target-authority semantics changed;
- old UI no longer builds;
- source tree has unexplained tracked changes;
- active experiment work would be mixed into extraction;
- intended UI repository already exists with unrelated content.

Resolve the discrepancy first.

---

# 43. Phase M1 — create IST-Thesis-UI

Create the external repository only after M0 passes.

Transfer only authoritative tracked frontend files.

Do not copy:

- `.git`;
- `node_modules/`;
- `dist/`;
- `*.tsbuildinfo`;
- generated config `.js`;
- generated config `.d.ts`;
- unrelated logs.

The destination root should correspond directly to the former `live-ui/` root.

Create:

- UI `.gitignore`;
- `MIGRATION_PROVENANCE.md`;
- optional small `docs/` only if immediately useful.

Do not introduce workspaces or monorepo infrastructure.

---

# 44. Phase M1 source-copy rule

Use committed Git content rather than a recursive working-tree copy.

At M1 record:

    SOURCE_REF="$(git rev-parse HEAD)"
    SOURCE_TREE="$(git rev-parse "$SOURCE_REF:live-ui")"

The recommended transfer mechanism is equivalent to:

    UI_ROOT="$HOME/Desktop/IST-Thesis-UI"
    git archive "$SOURCE_REF" live-ui | tar -x -C "$UI_ROOT" --strip-components=1

Only use that command after verifying the destination is the intended new
repository/work area and contains no unrelated files that could be overwritten.

The authoritative source manifest is reproducible from:

    git ls-tree -r --name-only "$SOURCE_REF" live-ui

with the leading `live-ui/` stripped for destination comparison.

Using `git archive` guarantees that ignored local artifacts such as
`node_modules`, `dist`, `*.tsbuildinfo`, and generated untracked config outputs
cannot leak into the transfer.

Compare the transferred frontend manifest against the Git source manifest
before adding new-repository-only files such as `.gitignore`,
`MIGRATION_PROVENANCE.md`, or launcher tooling.

---

# 45. Phase M1 validation before commit

Before the first UI-repository commit:

- compare source/destination tracked file counts;
- compare hashes of transferred files;
- confirm no `node_modules`;
- confirm no `dist`;
- confirm no `*.tsbuildinfo`;
- confirm no generated config `.js/.d.ts`;
- inspect `.env.example`;
- inspect `git status`.

Only then create the coherent initial import commit.

Immediately after the M1 import commit, a temporary source freeze applies to:

    IST-Thesis-Code/live-ui/

Until M7 removes that tree:

- do not make new frontend fixes in the old Thesis-Code copy;
- make frontend changes only in IST-Thesis-UI;
- record the M1 `SOURCE_REF` and `SOURCE_TREE` in
  `MIGRATION_PROVENANCE.md`;
- if an unavoidable emergency edit touches the old `live-ui/`, stop the
  migration, reconcile that delta explicitly into IST-Thesis-UI, and revalidate
  before continuing.

This prevents the temporary two-copy period from becoming two independent
sources of truth.

---

# 46. Phase M2 — standalone frontend baseline

In `IST-Thesis-UI` run at minimum:

    npm ci

    npm run build

    npm ls --depth=0

Then smoke the frontend locally.

Required:

- dev server starts;
- HTML responds;
- React application renders;
- mock mode updates;
- offline mode works;
- no ROS sourcing required;
- no Python environment required;
- no Thesis-Code filesystem read required.

Old `Thesis-Code/live-ui` still exists during M2.

Rollback remains trivial.

---

# 47. Phase M3 — UI-owned launcher

M2 established an additional lifecycle requirement:

- do not assume the PID returned by backgrounding `npm run dev` owns Vite;
- the launcher must own the actual long-lived frontend process or its complete
  session/process group;
- stop/interrupt handling must leave no Vite or esbuild listener/process behind.

Create the authoritative frontend launcher in:

    IST-Thesis-UI/tools/start_dashboard.sh

The launcher should derive the UI repository root from its own location.

It should support at least:

- backend mode;
- mock mode;
- offline mode;
- host;
- port;
- dependency-install option only if intentionally retained.

The UI launcher must not require `THESIS_ROOT`.

---

# 48. UI runtime logging

Frontend launcher/runtime logs must not pollute either repository root.

Preferred state/log root:

    ${XDG_STATE_HOME:-$HOME/.local/state}/ist-thesis-ui/

A configurable equivalent is acceptable.

Do not create:

    IST-Thesis-UI/log/

as uncontrolled runtime noise.

Do not create:

    IST-Thesis-Code/log/

for UI logs.

---

# 49. Phase M4 — compatibility launcher

After the UI-owned launcher works, convert:

    IST-Thesis-Code/tools/start_ui_stack.sh

into a small compatibility shim.

Suggested external root variable:

    THESIS_UI_ROOT

Suggested default:

    $HOME/Desktop/IST-Thesis-UI

The shim should:

1. resolve external UI root;
2. fail clearly if absent;
3. delegate arguments;
4. avoid implementing npm/frontend logic itself;
5. not assume `Thesis-Code/live-ui` exists.

This preserves operator muscle memory while fixing repository ownership.

---

# 50. Compatibility wrapper decision

The wrapper may remain permanently if useful.

Its existence does not violate the repository boundary because Thesis-Code is
not importing frontend code; it is merely delegating to an external operator
tool.

If later removed, documentation must clearly point operators to the direct UI
repository command first.

---

# 51. Phase M5 — documentation migration

Review every reference returned by:

    rg -l 'live-ui|start_ui_stack\.sh' README.md docs tools ros2_ws

Known important locations include:

- root `README.md`;
- `tools/README.md`;
- `docs/design/tim_tooling_index.md`;
- flight-readiness/operator docs;
- Issue #55 documentation;
- test documentation.

Documentation must clearly separate:

- ROS/backend startup;
- browser frontend startup;
- compatibility-wrapper startup.

---

# 52. Phase M5 — old frontend README migration

The useful frontend documentation currently under:

    live-ui/README.md

moves with the frontend.

Before finalising it in the new repository:

- correct stale `/api/replay`;
- correct coordinate-normalisation description;
- document the external runtime dependency;
- document backend/mock/offline modes;
- document expected ports;
- document that protected model/tracker HTTP 409 is expected in the frozen
  flight profile.

Behavior changes must not be hidden inside documentation cleanup.

---

# 53. Test-ownership split

After extraction, tests should follow ownership.

## IST-Thesis-UI owns

- TypeScript typecheck;
- React unit tests;
- frontend HTTP-client behavior;
- frontend WebSocket behavior;
- telemetry parsing;
- reconnect handling;
- mock mode;
- offline mode;
- build;
- frontend lint/format;
- UI launcher tests;
- frontend documentation contract.

## IST-Thesis-Code owns

- ROS dashboard bridge behavior;
- HTTP API producer semantics;
- WebSocket producer semantics;
- target-authority generation;
- target select/clear;
- TIM-MARS subscriber readiness;
- model/tracker frozen protection;
- coordinate normalisation;
- runtime metrics production;
- ROS service failure behavior;
- provenance behavior.

---

# 54. Existing Thesis-Code test migration

`tools/tests/test_documented_operator_contract.py` currently encodes the old
internal frontend location.

Existing assumptions include concepts such as:

- `live-ui/` exists in Thesis-Code;
- `live-ui/README.md` exists;
- `live-ui/package.json` exists;
- operators `cd live-ui`;
- launcher resolves `$THESIS_ROOT/live-ui`.

Do not simply delete these assertions.

Replace them with Thesis-Code-side ownership assertions such as:

- compatibility launcher exists if retained;
- documentation points to external UI repository;
- runtime backend contract remains documented;
- internal `live-ui/` is intentionally absent after M7.

Frontend assertions move to the new repository.

---

# 55. tools layout test migration

Review:

    tools/tests/test_tools_layout.py

Only update assertions made obsolete by dashboard extraction.

Do not remove annotation/backend/scientific assertions.

The migration must not obtain a passing test suite by reducing unrelated
scientific coverage.

---

# 56. Cross-repository integration policy

Normal unit tests in either repository must not require the sibling repository
to exist at a hard-coded path.

Instead maintain a small explicit integration procedure.

The integration contract is:

    frontend
        <- HTTP / WS / MJPEG ->
    runtime backend
        <- ROS ->
    thesis pipeline

This integration can be executed on the Pi when required without making every
CI run depend on ROS hardware/runtime.

---

# 57. Phase M6 — live integration gate

Do not delete the old frontend before a migrated frontend passes runtime
integration.

Validate all relevant interfaces.

## API models

    GET /api/models

Expected:

- connection succeeds;
- JSON parses;
- model list is returned.

## WebSocket

Expected:

- connection opens;
- initial snapshot arrives;
- updates continue;
- no persistent malformed-payload state;
- reconnect works after a controlled disconnect.

## MJPEG

Expected:

- stream loads;
- dashboard image remains live;
- no persistent retry loop.

## Overlay

Manually verify:

- boxes align with detections;
- boxes align with tracks;
- target highlight is coherent;
- source resolutions other than historical 640 inference assumptions do not
  introduce coordinate drift.

---

# 58. Protected-control M6 tests

In the frozen validated runtime:

- model switching must remain protected;
- tracker switching must remain protected.

Expected protected result:

    HTTP 409

For the currently audited backend semantics, also verify that each denied
model/tracker request:

- advances the target-authority generation;
- applies the expected target clear/reset behavior;
- does not apply the requested runtime reconfiguration.

That combination is PASS behavior for the current frozen profile.

Do not enable runtime reconfiguration merely to demonstrate that buttons can
change settings.

---

# 59. Target-command M6 test

Only on a safe bench/replay setup with TIM-MARS active:

- select a valid track;
- confirm HTTP success;
- confirm authority-generation update;
- confirm TIM-MARS owns the selection path;
- clear the target;
- confirm authority transition;
- confirm no raw browser-only state bypasses TIM-MARS.

Do not perform new unsafe control experiments during uncontrolled flight solely
for UI migration validation.

---

# 60. Phase M7 — remove old frontend

Only after M1-M6 pass.

Before deletion, verify that the old frontend tree has remained frozen:

    git rev-parse HEAD:live-ui

must equal the M1 source-tree SHA recorded in
`IST-Thesis-UI/MIGRATION_PROVENANCE.md`.

If it differs, stop. Audit the frontend delta, reconcile any missing change
into IST-Thesis-UI, update evidence, and revalidate before deletion.

Then:

- remove tracked `live-ui/` from Thesis-Code;
- remove path-specific `.gitignore` entries that are obsolete;
- retain useful generic ignores;
- update docs;
- update location-contract tests;
- verify compatibility wrapper;
- inspect full Git diff.

This is the first point at which rollback requires restoring the old tree from
Git rather than simply using the still-existing source directory.

---

# 61. Required regression after M7

Re-run applicable scientific and backend regressions.

Planning reference:

- annotation/scientific focused suite: 337 passed;
- dashboard/backend focused suite: 17 passed.

Exact test counts may change legitimately as main advances.

Acceptance requires:

- all applicable tests pass;
- no coverage removed merely to make the extraction green;
- no annotation/physical-reference behavior changes;
- no dashboard backend regressions.

---

# 62. Issue #55 relationship

Issue #55 is broader than repository extraction.

Repository extraction is a prerequisite/structural subtask, not automatic
completion of Issue #55.

The issue spans both future repositories after the split.

---

# 63. Issue #55 — UI repository ownership

IST-Thesis-UI should own:

- deterministic frontend build;
- typecheck;
- frontend lint;
- frontend tests;
- duplicate/dead provider cleanup;
- frontend launcher;
- HTTP client tests;
- WebSocket client tests;
- mock/offline tests;
- browser behavior for protected controls;
- UI CI.

---

# 64. Issue #55 — Thesis-Code ownership

IST-Thesis-Code should own:

- API implementation;
- WebSocket producer;
- API bind policy;
- WebSocket bind policy;
- CORS;
- target-control security;
- authentication/authorization if required;
- target authority;
- frozen-flight runtime-reconfiguration enforcement;
- ROS service failure handling;
- telemetry production;
- backend contract tests.

---

# 65. Issue #55 — shared ownership

Both repositories participate in:

- HTTP compatibility;
- WebSocket compatibility;
- end-to-end operator workflow;
- integration documentation;
- network/trust-boundary documentation.

No hard filesystem import should be introduced merely to test cross-repository
compatibility.

---

# 66. Recommended Issue #55 frontend hardening order

After pure extraction:

1. prevent generated config `.js/.d.ts` source-tree emission;
2. add explicit `typecheck`;
3. add deterministic lint;
4. add frontend unit-test runner;
5. create one aggregate frontend verification command;
6. remove duplicate WebSocket-provider implementation;
7. test HTTP clients;
8. test WebSocket parsing/reconnect;
9. test mock/offline modes;
10. test production build in CI;
11. evaluate current dependency vulnerabilities;
12. address bundle warning only if worthwhile.

Do not combine all of this with the initial transfer commit.

---

# 67. Recommended Issue #55 backend hardening order

After extraction:

1. add explicit API contract tests;
2. add explicit WebSocket payload contract tests;
3. define default bind policy;
4. define remote bind override;
5. replace accidental wildcard CORS with intentional policy;
6. document trusted-network assumptions;
7. decide whether explicit auth is required;
8. preserve frozen model/tracker protection;
9. protect `/api/target` according to the chosen trust model;
10. document operator configuration.

---

# 68. Repository root cleanliness

Thesis-Code root must remain professional.

Generated runtime artifacts such as:

    log/

and:

    hailort.log

must not remain at root.

ROS logs belong under:

    ros2_ws/log/

with project conventions such as:

    COLCON_LOG_PATH=$THESIS_ROOT/ros2_ws/log/colcon

and:

    HAILORT_LOGGER_PATH=$THESIS_ROOT/ros2_ws/log/hailort

The UI split must not weaken these rules.

---

# 69. thesis_env ownership

`thesis_env/` remains a local ignored Python environment in Thesis-Code.

It is not transferred.

The new frontend repository should not depend on `thesis_env`.

Frontend setup should require only the declared Node/npm toolchain.

---

# 70. ROS build ownership

Normal ROS builds remain in Thesis-Code.

Preferred command:

    cd ~/Desktop/Thesis-Code || exit 1
    export GIT_PAGER=cat
    export PAGER=cat
    tools/thesis_build.sh

Single package example:

    tools/thesis_build.sh --packages-select thesis_bringup

Do not replace this with root-level ad-hoc build behavior during UI migration.

---

# 71. Rollback strategy — before deletion

Until M7, `Thesis-Code/live-ui` remains intact.

Rollback is:

    stop using the new repository
    use the old frontend

No Git restoration is required.

This is why deletion is deliberately late.

---

# 72. Rollback strategy — compatibility-wrapper change

If the new wrapper fails:

- revert the wrapper/docs/test checkpoint;
- continue using internal `live-ui/`;
- leave the new UI repository intact for diagnosis.

Do not destroy the external repository simply because the wrapper needs work.

---

# 73. Rollback strategy — after old frontend deletion

If M7 is not yet merged:

- restore `live-ui/` from the parent migration commit;
- revert wrapper/docs changes as needed.

If M7 is merged:

    git revert <relevant extraction commit>

Do not rewrite published Thesis-Code history.

The independent UI repository may remain.

---

# 74. Forbidden operations during Phase A

Do not:

- migrate on Issue #58;
- migrate on another scientific experiment branch;
- rewrite Thesis-Code history;
- force-push Thesis-Code;
- move annotation backend code;
- move analysis code;
- move bags;
- move models;
- move reports;
- move ROS packages;
- move `thesis_env`;
- commit `node_modules`;
- commit `dist`;
- commit `*.tsbuildinfo`;
- commit generated config `.js/.d.ts`;
- run `npm audit fix --force`;
- upgrade dependencies;
- redesign the UI;
- change ROS topic names;
- change coordinate semantics;
- change target authority;
- enable runtime reconfiguration;
- weaken frozen-flight safety;
- expose APIs publicly for convenience;
- create root runtime log noise;
- combine dashboard extraction with annotation refactoring;
- delete the old frontend before M6 passes.

---

# 75. File-editing safety during execution

Before editing an existing file:

- inspect it with `sed`, `rg`, `cat`, or `git diff`;
- prefer targeted patches;
- do not blindly overwrite unknown files;
- do not use nested Markdown fences inside shell heredocs;
- avoid persistent strict-shell changes in the interactive terminal;
- never use `set -e` in pasted interactive commands.

The execution should remain recoverable if an individual command fails.

---

# 76. Operator commands after extraction

Preferred direct UI invocation:

    cd ~/Desktop/IST-Thesis-UI || exit 1
    tools/start_dashboard.sh

Preferred compatibility invocation if retained:

    cd ~/Desktop/Thesis-Code || exit 1
    tools/start_ui_stack.sh

The live ROS/backend stack remains launched from Thesis-Code.

---

# 77. Annotation UI operator command

Until a separately approved Phase B changes annotation architecture, the
existing thesis annotation command remains owned by Thesis-Code.

Current project-standard command:

    cd ~/Desktop/Thesis-Code || exit 1
    export GIT_PAGER=cat
    export PAGER=cat
    set +u
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash
    thesis_env/bin/python tools/bag_annotation_ui/tim_clean_ui.py --host 100.69.42.62 --port 8888

Dashboard extraction must not break this command.

---

# 78. Migration acceptance — source ownership

Phase A source ownership passes only if:

- authoritative React source exists in IST-Thesis-UI;
- `live-ui/` no longer exists in Thesis-Code after M7;
- dashboard bridge remains in Thesis-Code;
- runtime launch remains in Thesis-Code;
- UI source is not duplicated indefinitely;
- no ROS/scientific code moved to the UI repository.

---

# 79. Migration acceptance — frontend

Required:

- `npm ci` passes;
- production build passes;
- dependency tree is consistent;
- mock mode works;
- offline mode works;
- backend mode works;
- dev launcher works;
- production build has no migration-induced errors.

Known pre-existing warnings may remain until Issue #55 hardening.

---

# 80. Migration acceptance — runtime

Required:

- dashboard bridge launches;
- HTTP API responds;
- WebSocket telemetry responds;
- video stream responds;
- boxes align;
- frozen model/tracker protection remains;
- target command still flows through TIM-MARS;
- target authority generation remains coherent.

---

# 81. Migration acceptance — science

Required:

- scientific tests remain green;
- annotation tooling remains functional;
- no physical-reference schema change;
- no evaluator semantic change;
- no bag/provenance path breakage caused by extraction.

---

# 82. Migration acceptance — repository hygiene

Required in both repositories:

- clean tracked state after intended commits;
- ignored artifacts reviewed;
- no node_modules tracked;
- no dist tracked;
- no runtime root logs;
- no credentials;
- no unexpected binary artifacts;
- correct README ownership.

---

# 83. Definition of repository-extraction done

Repository extraction is complete when:

1. new UI repository exists;
2. provenance is recorded;
3. frontend validates standalone;
4. UI-owned launcher exists;
5. Thesis-Code compatibility boundary is correct;
6. docs/tests are updated;
7. live integration passes;
8. old internal frontend is removed;
9. regressions pass;
10. both repositories are clean;
11. evidence log below is updated;
12. rollback path is documented and still valid.

---

# 84. Definition of Issue #55 done

Issue #55 is not complete merely because the repository split is complete.

It additionally requires the agreed frontend validation and security/access
contract, including:

- deterministic frontend checks;
- provider cleanup;
- contract tests;
- intentional network exposure;
- intentional CORS;
- explicit trust/auth decision;
- continued frozen-flight protection.

---

# 85. TODO_LIST rule

Whenever this plan materially tackles Issue #55:

- inspect `docs/TODO_LIST.md`;
- update it in the same coherent checkpoint.

The TODO must reference this file so later sessions do not repeat the
repository-boundary investigation.

---

# 86. Future-session recovery procedure

A future session continuing this work should first inspect:

    docs/issues/ui-repository-extraction-master-plan.md

then:

    docs/TODO_LIST.md

then:

    git status --short

    git status --short --ignored

    git branch --show-current

    git --no-pager log -5 --oneline --decorate

Then determine the highest completed stage in the evidence ledger.

Do not redesign the architecture unless current source changes invalidate an
explicit contract.

---

# 87. Stage sequence

The intended stage sequence is:

| Stage | Meaning |
|---|---|
| P0 | planning/audit authority |
| M0 | current-main execution preflight |
| M1 | create/copy into IST-Thesis-UI |
| M2 | standalone UI validation |
| M3 | create UI-owned launcher |
| M4 | create Thesis-Code compatibility boundary |
| M5 | move docs/tests to correct ownership |
| M6 | live integration validation |
| M7 | remove old internal frontend |
| H1 | Issue #55 frontend hardening |
| H2 | Issue #55 backend/security hardening |
| B1 | optional future annotation frontend split |

Stages must not be skipped merely because later stages appear simple.

---

# 88. Evidence ledger

Update this table during actual execution.

| Stage | Date | Thesis-Code ref | IST-Thesis-UI ref | Result | Evidence |
|---|---|---|---|---|---|
| P0 forensic audit | 2026-08-29 | `bbc19d21` / main `22b9737a` | N/A | PASS | deep dependency + final forensic audit |
| P0 cross-branch check | 2026-08-29 | tree `634754dd` | N/A | PASS | live-ui/bridge/launcher equivalent |
| P0 execution refresh | 2026-09-01 | `8e88a471` | N/A | PASS | clean #55 branch; current live-ui tree `634754dd`; mobile field target frozen |
| M1 local source import | 2026-09-01 | `bd1f2cd5` / tree `634754dd` | `032041aa` | PASS | 45 source files matched path-for-path and blob-for-blob; 47 tracked files after provenance/.gitignore; no generated artifacts; old live-ui retained |
| P0 green baseline | 2026-08-29 | `bbc19d21` | N/A | PASS | npm/build/smoke; 337 + 17 tests |
| M0 current-main preflight | 2026-09-01 | `bd1f2cd5` / tree `634754dd` | N/A | PASS | clean execution branch; 45 tracked files; destination/GitHub collision checks clear; source sentinels verified |
| M1 repository creation | 2026-09-01 | tree `634754dd` | `032041aa` | PASS | exact 45-file import plus provenance/.gitignore; public `FRCTavares/IST-Thesis-UI` created; remote main exactly matches validated import commit |
| M2 standalone validation | 2026-09-01 | N/A | `032041aa` | PASS | `npm ci`, production build and dependency tree pass; mock/offline HTTP pass without ROS/Thesis-Code dependency; true Vite session ownership gives deterministic cleanup |
| M3 UI launcher | 2026-09-01 | N/A | `03e45384` | PASS | UI-owned `tools/start_dashboard.sh`; backend/mock/offline modes; host/port/install options; external state/log path; launcher execs real Vite process; HTTP and deterministic shutdown smoke pass |
| M4 compatibility wrapper | 2026-09-01 | `5104f0df` | `03e45384` | PASS | `start_ui_stack.sh` reduced to external delegation shim; legacy operator flags/env translated; missing checkout fails clearly; no npm/Vite implementation remains in Thesis-Code |
| M5 docs/test ownership | 2026-09-01 | `5104f0df` | `ef8914c9` | PASS | Thesis-Code operator docs/tests migrated to external frontend ownership with 11 targeted contracts passing; UI README now documents the actual runtime/API/port/frozen-profile/target-authority/bbox contracts and production build passes |
| M6 live integration | 2026-09-02 | `3a42c8e433bf547e8360a42bf2d45916de189afa` | `e7329e01` | PASS | automated live integration PASS; direct real-iPhone LAN and numbered overlay / SELECT / LOCKED / CLEAR / resize validation PASS; truthful Tailscale reporting PASS; A/B/C timing characterization PASS; prebuilt static frontend and deterministic launcher cleanup PASS; real Pixhawk-gated `ISR Aero.Next GCS` field entry PASS with `pixhawk-apm`, no Ethernet default route, and Tailscale inactive; real physical Pixhawk unplug PASS with dispatcher fail-closed return to `unattended` in 8318 ms, maintenance ISR/Tailscale recovery, and no emergency rollback; raw evidence `reports/p055_field_network_2026_09_02/`; summary `docs/results/live/p055_field_network_validation.md`; M7 unblocked but not started |
| M7 old frontend removal | pending | pending | pending | pending | pending |
| H1 frontend hardening | pending | N/A | pending | pending | pending |
| H2 backend hardening | pending | pending | optional | pending | pending |
| B1 annotation frontend | deferred | pending | pending | deferred | not part of Phase A |

---

# 89. Final ownership summary

## Move now

    live-ui/

## Replace with ownership split

    tools/start_ui_stack.sh

Frontend launch implementation belongs in IST-Thesis-UI.

Thesis-Code may retain a compatibility wrapper.

## Stay in Thesis-Code

    dashboard bridge
    web video integration
    ROS runtime
    target authority
    TIM-MARS
    perception
    trackers
    control
    bags
    models
    reports
    analysis
    experiments
    annotation tooling
    scientific tests
    thesis_env ownership

## Explicitly deferred

    annotation frontend/backend separation

---

# 90. Governing principle

The goal is not to produce the visually purest repository split in the fewest
commands.

The goal is to create a stable repository boundary while preserving a
scientifically validated and safety-sensitive UAV perception runtime.

Every migration step must satisfy three questions:

1. Does this preserve scientific/runtime behavior?
2. Is ownership clearer after the change?
3. Is rollback still straightforward?

If the answer to any is no, the step should not proceed as part of Phase A.
