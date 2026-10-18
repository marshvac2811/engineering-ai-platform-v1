# Engineering AI Platform — Handoff / Status Note

Read this file first in any new chat to resume work with minimal context. Paste this
exact line to Claude at the start of a new chat:

> Read github.com/marshvac2811/engineering-ai-platform-v1/blob/main/HANDOFF.md and
> continue from there.

## What this is
Commercial SaaS: AI interprets engineering requests, deterministic skills perform the
actual calculations, human review and approval, then a watermarked PDF + Excel evidence
workbook are generated and dispatched. Hosted on Render (FastAPI/WSGI), Supabase
(Postgres + Storage) for persistence, Vercel + middleware.js for edge auth, dashboard at
web/app.html served directly by the Render app.

Live site: https://engineering-ai-platform-v1.onrender.com

## Status: V1 workflow functional; Render live service verified; authenticated artifact workflow verification remains the final live gate

The core workflow is operational for **24 executable skills (25 registered; `chiller_efficiency` remains source-audit pending)**. Trial 1 reached human review with deterministic duct sizing, correct missing-input behavior, and traceability metadata. A production defect was then found: the dashboard Report view rendered only report metadata instead of the persisted engineering work items, and legacy evidence records could produce an apparently blank artifact workbook. The consolidated rendering/recovery fix has been merged; the canonical Render service is live on commit `b481bc1c7ed7b52d49fa32805e40cfb567e22985`; authenticated Trial 1 dispatch and artifact verification remain the final live gate.

## Done
- 24 engineering skills executable (HVAC, BMS, Energy, Commercial, Fire, Plumbing) - see
  skill_registry/registry.yaml for the full list and required inputs.
- Evidence bundle preserves standards/compliance/source_revision/inputs per task.
- PDF and Excel reports are table-based with readable labels and units, not raw JSON.
- Dashboard: View Report, View Evidence, Download PDF, Download Excel, pagination.
- Central Report Register: tabs (All/Pending/Approved/Dispatched/Completed/Failed-Rework),
  search, skill filter, View Audit, Export whole register to Excel.
- Reviewer rework loop: reviewer can send a draft back with a comment before approval;
  engineer edits inputs and resubmits; job re-runs and returns to review. Report revisions
  (V1, V2...) tracked, older ones marked superseded.
- Project / Client fields exist end-to-end: request form -> job -> register -> PDF/Excel
  headers.
- Security: dev-header auth (X-Tenant-ID) disabled in production via ENGINEERING_ENV=
  production; forged X-Engineering-Auth header ignored unless actually running on Vercel;
  approvals record the verified login email, not a client-supplied name.
- Integrations scaffolded with real API wiring (not stubs) for Gmail and Upwork; Fiverr
  is notification/import-only by design (no public freelancer API exists); Gumroad
  partially wired. None connected to live credentials yet. CRM module (crm/) built with
  HubSpot payload support, not connected to a real HubSpot account yet.
- 272 automated tests passing in GitHub Actions on main commit `2d778454506d0936a5f0472041191569ddd18247` (run 37346834387).
- Trial prompt bank: 110 realistic prompts (5 per skill x Simple/Mild/Heavy) kept outside
  the repo as an Excel tracker, given to the user directly in chat (not in this repo).

## Not done yet / next priorities
1. **Post-deploy artifact verification:** rerun Trial 1 on the canonical Render application, approve, dispatch, then verify the readable Report view, Evidence view, PDF, XLSX Results sheet, Calculation Steps, hashes, Evidence Register and Revision History.
2. **Full end-to-end acceptance:** one request -> calculation -> review -> approval -> PDF/XLSX -> register -> dispatch trial for each executable skill, beginning with the HVAC/energy niche rather than all 22 at once.
3. **Product vertical A — HVAC Design Engineering:** client natural-language request + floor/layout evidence -> governed load estimate -> preliminary system selection -> equipment schedule -> duct/pipe/airside planning -> installation/execution plan -> human review.
4. **Product vertical B — HVAC Energy Optimization:** plant/BMS/utility data -> baseline -> inefficiency diagnosis -> savings opportunities -> peak-demand/load-profile analysis -> tariff/cost impact -> prioritized measures -> payback.
5. **Product vertical C — HVAC Decarbonization:** baseline energy/carbon -> retrofit scenarios -> energy/cost/carbon/capex comparison -> implementation roadmap -> measurement/evidence plan. This should reuse the optimization data rather than become a separate calculator.
6. **Commercial/CRM layer:** leads, opportunities, quotations/orders and client follow-up should feed engineering requests and receive controlled engineering deliverables; CRM is a supporting workflow, not a fourth engineering vertical.
7. **Drawing/layout intelligence:** the repository already contains a small CAD-neutral Phase 16 drawing model (`engineering/drawing/`) and plumbing construction scope references. The next drawing work is to expand this into governed drawing intake/building understanding, then HVAC drawing MVP, followed by fire-fighting/plumbing drawing modules and coordination. Outputs must remain preliminary unless source evidence and human review support a stronger claim.
8. Gmail/Upwork/Gumroad live credentials and CRM integrations remain pending.
9. `chiller_efficiency` remains blocked until its source audit is completed.

## Product acceptance sequence
- **Stage 1:** Fix/verify the report + evidence delivery chain.
- **Stage 2:** Prove HVAC Design with a bungalow/floor-plan scenario.
- **Stage 3:** Prove Energy Optimization with real plant/BMS/utility data.
- **Stage 4:** Prove Decarbonization using the same baseline and optimization findings.
- **Stage 5:** Connect the three into one client journey: request -> evidence -> engineering analysis -> options -> commercial recommendation -> human approval -> controlled deliverables.

## Current Trial 1 traceability contract
For the rectangular duct velocity trial (5000 m³/h, 7 m/s, galvanized steel), the governed result must preserve:
- `skill_version: 1.2.0`
- `source_revision: 1410b71e16a4fe4b1c6b04f023291d7b0f458d68`
- calculation trace function: `preliminary_rectangular_velocity_sizing`
- no missing inputs after natural-language extraction
- human review required = true
- expected preliminary result: 450 x 450 mm, actual velocity about 6.86 m/s, friction about 0.962 Pa/m

## How to resume cheaply
- Don't paste old conversation. Just point Claude at this file plus whatever specific
  task you want next (e.g. "build item 3 from the Not done list").
- Claude should `git clone` the repo fresh, read this file, then read only the specific
  source files relevant to the task - not the whole repo.
- Tests: `python -m pytest -q` from repo root before and after any change.
- Push access: user grants a short-lived GitHub classic token (repo scope) when needed;
  delete it from GitHub afterwards.

## Current implementation checkpoint — 2026-10-05
- PR #31 merged: governed building and multidisciplinary drawing foundation.
- PR #32 merged: authenticated drawing planning and coordination API contracts.
- Main drawing foundation now includes source-traceable BuildingModel, structured floors/rooms, confidence/review handling, preliminary HVAC/FIRE/PLUMBING drawing objects, deterministic JSON/SVG export, explicit-input discipline planning, and cross-discipline clearance conflict detection.
- Existing attachment ingestion already hashes and registers uploaded source files; the new building layer consumes normalized layout facts without fabricating geometry.
- API contracts added: POST /v1/drawings/plan and POST /v1/drawings/coordinate, protected by the existing jobs-write scope. Drawing outputs are explicitly preliminary and human-review-required.
- Latest drawing API branch CI: 281 tests passed, 1 warning.
- The drawing system is still not a full PDF/CAD/BIM interpreter or construction drawing generator. The next implementation work is source-document geometry extraction, persistent project/drawing records, governed HVAC drawing generation from actual calculation outputs, then fire/plumbing design modules and coordination package integration.
- Canonical live deployment remains Render and still requires post-merge deployment verification.

## Latest implementation checkpoint — 2026-10-05
- PR #33 merged: deterministic ASCII-DXF LINE geometry extraction.
- PR #34 merged: existing DXF ingestion now reports supported LINE geometry count while preserving no-semantic-interpretation.
- PR #35 merged: controlled drawing evidence package with source hashes, drawing JSON/SVG hashes, revisions, source-calculation references and coordination status.
- Current drawing stack therefore covers: source registration/hash → normalized building model → confidence/review boundary → explicit-input HVAC/FIRE/PLUMBING preliminary objects → JSON/SVG drawing export → coordination conflict detection → controlled drawing manifest/hashes.
- CI is green on each merged feature branch; latest drawing evidence branch passed the full suite before merge.
- Remaining major implementation is the higher-level semantic drawing pipeline: PDF/image/CAD semantic interpretation, persistent project/drawing records, actual HVAC calculation-to-layout routing, governed fire/plumbing engineering calculators, richer drawing rendering (PDF/DXF output from semantic objects), and full controlled drawing dispatch integration.

## Current verified checkpoint — 2026-10-05
- `main` commit: `2d778454506d0936a5f0472041191569ddd18247`.
- PR #30 fixed a stale facade report-type assertion exposed by the legacy-report recovery change; PR #30 is merged.
- GitHub Actions run `37346834387`: **272 passed**, 1 warning.
- The previous `d07515e...` main run failed only because `tests/test_api.py` expected the obsolete `engineering_compliance_report`; production behavior was not changed by the fix.
- Canonical deployment remains Render. The Render service is now connected and verified live; authenticated `/v1` Trial 1/report/evidence/PDF/XLSX verification remains open.
- The existing Phase 16 drawing foundation is minimal: a CAD-neutral `DrawingModel` with points/lines/dimensions plus deterministic JSON serialization and a parametric facade-elevation example. It is **not** yet the building-layout/HVAC/fire/plumbing drawing engine described in the expanded roadmap.

Last updated: 2026-10-05, after CI recovery and drawing-foundation audit.

## Latest implementation checkpoint — 2026-10-06
- PR #36 merged: governed drawing package linkage to engineering Jobs.
- Added `engineering/drawing/service.py` to bind drawing manifests to job/tenant/report/revision identity and to enforce an explicit approval gate before controlled issue eligibility.
- Added `POST /v1/drawings/package`: builds multidisciplinary preliminary drawing packages from normalized building input, records source hashes, calculates coordination conflicts, persists the package manifest into the linked Job result, and exposes JSON/SVG outputs.
- Before approval, package status is `not_approved` and `dispatch_allowed=false`. For an approved Job, the package is marked `approved_for_controlled_dispatch` with `dispatch_allowed=true`.
- Added service and API regression tests for package traceability and approval enforcement.
- Acceptance matrix now records AT-43..AT-58 as unit-covered, AT-59 as package-linkage/API-covered with persistent production artifact storage still remaining, and AT-60 as partial because actual drawing-file dispatch integration is not yet complete.
- Important boundary: this does **not** claim final construction/statutory drawing approval or full PDF/CAD/BIM semantic interpretation.
- PR #36 merged commit: `b2fb6bf17104d00ab3e3f228f80c83fc02ecc6b0`.
- GitHub combined status currently shows only a Vercel pending check for the PR head; no GitHub Actions run was exposed by the connector for that head, so CI must not be claimed for PR #36 without a later verified run.
- Next implementation priority: persistent drawing/project artifact records and actual controlled drawing-file dispatch (PDF/DXF package), then semantic source interpretation and calculation-to-layout routing.

## Latest implementation checkpoint — 2026-10-06 (controlled drawing artifacts)
- PR #37 merged: persistent and controlled engineering drawing artifacts.
- Added `engineering/drawing/dispatch.py` for deterministic preliminary drawing PDF generation and ASCII-DXF ZIP packaging, with explicit preliminary/review watermarking.
- Added Supabase migration `20261006070000_012_engineering_drawing_artifacts.sql` for tenant-scoped persistent drawing artifact records and private `engineering-drawing-artifacts` storage.
- Drawing package manifests now persist drawing JSON payloads/SVGs, project/job/report/revision identity and a manifest SHA-256 bound to that identity. Mutable approval/dispatch flags are excluded from the immutable content hash.
- The normal approved Job dispatch lifecycle now also creates controlled drawing PDF/DXF artifacts when a drawing package is attached to the Job.
- Added tenant-scoped GET/download APIs for persisted drawing artifacts.
- Drawing dispatch files are stored privately; the package contains the PDF, per-drawing ASCII DXF files and manifest JSON. SHA-256 values are recorded in the drawing artifact record and returned in Job dispatch results.
- Governance boundary remains explicit: these are AI-assisted preliminary engineering drawings, not final construction/statutory approvals. Semantic PDF/CAD/BIM interpretation and calculation-to-layout routing are still future layers.
- PR #37 merge commit: `80abed341044fb7d8ac4a3e6b4bcab55903944ce`.
- GitHub connector currently exposes no Actions workflow run for this merge commit; combined status shows Vercel pending only. Do not claim CI passed for this checkpoint until a later verified run exists.
- Canonical live deployment remains Render; the service is now verified live on Render. Authenticated drawing dispatch verification remains open.
- Next implementation priority: semantic source interpretation and calculation-to-layout routing, then governed fire/plumbing engineering calculators and richer coordinated drawing generation.

## Latest implementation checkpoint — 2026-10-06 (source interpretation and calculation-to-layout routing)
- Added `engineering/building/interpreter.py` for conservative interpretation of extracted building evidence. Explicit room/area/dimension facts can be surfaced from text-bearing sources; scanned/image-only PDFs remain blocked because automatic OCR/visual semantics are not claimed.
- DXF interpretation exposes deterministic LINE geometry only and explicitly keeps architectural semantics disabled.
- Added `POST /v1/jobs/{job_id}/attachments/{attachment_id}/building-interpretation`, which stores the interpretation in the Job result and audit events.
- Added `engineering/design/routing.py` and `POST /v1/drawings/route`. Calculation outputs are routed to drawing rooms only when they contain an explicit room_id, source_calculation reference, discipline-specific value and source geometry coordinates. No nearest-room, name matching or geometric guessing is performed.
- Routed layouts remain preliminary and human-review-required. This is a routing/traceability layer, not a replacement for the deterministic engineering calculators.
- Main currently includes these changes directly; GitHub Actions workflow runs are not exposed by the connector for these commits, so CI is not claimed as verified for this checkpoint.
- Next priority remains governed fire/plumbing engineering calculators and richer coordinated drawing generation, followed by semantic visual/CAD interpretation when a dedicated parser/vision capability is introduced.

## Latest implementation checkpoint — 2026-10-06 (Fire + Plumbing engineering core)
- Added `fire_water_storage` as a deterministic preliminary skill. It calculates storage only from explicit/governed required flow, duration and optional reserve percentage; it does not invent statutory fire demand, sprinkler density, pump duty or pipe sizing.
- Added `plumbing_water_demand` as a deterministic preliminary skill. It aggregates explicit fixture flow rates and an explicit diversity factor; it does not infer code fixture units, simultaneous-use rules, pipe sizes or statutory demand.
- Added adapters, unit tests and registry entries for both skills.
- Registry is now **25 skill IDs: 24 integrated/executable + 1 source-audit-pending (`chiller_efficiency`)**.
- Acceptance matrix extended with AT-61 Fire Water Storage and AT-62 Plumbing Water Demand. Drawing trials remain AT-43 through AT-60.
- Removed the duplicate `crm_pipeline` registry block.
- These Fire/Plumbing skills are deliberately input-governed preliminary capabilities. Standards-derived design logic will only be added when a source/audit basis is explicitly established.
- GitHub Actions results for these latest direct-main commits are not exposed by the connector, so CI is not claimed as verified for this checkpoint. Render runtime verification has now caught and fixed the Fire/Plumbing import/binding defects.
- Next priority: connect these calculators to the discipline drawing planner and calculation-to-layout routing, then add controlled Fire/Plumbing coordinated package trials.


## Latest implementation checkpoint — 2026-10-06 (Fire/Plumbing calculation-to-layout integration)
- Fire and Plumbing preliminary calculators are now connected to the governed drawing routing/planner layer.
- route_calculation_outputs preserves the existing explicit protection_type / fixture_type paths and additionally accepts only explicit total_storage_m3 for Fire water-tank layout and explicit design_demand_lpm for Plumbing demand layout.
- plan_discipline_layout renders these values as traceable preliminary fire_tank and water_demand objects. No room matching, code-demand inference, pipe sizing, pump selection or automatic placement is performed.
- Both Fire/Plumbing adapters now preserve skill_version in SkillResult, closing a metadata traceability gap.
- Added regression coverage for Fire storage and Plumbing demand routing and drawing generation.
- Next step: controlled coordinated Fire/Plumbing package trials, followed by a full repository test/CI verification.


## Latest implementation checkpoint — 2026-10-06 (coordinated Fire/Plumbing drawing package)
- Fire/Plumbing calculation-to-layout integration is complete at the repository layer.
- Routing now accepts HVAC as a normalized single-field tuple and Fire/Plumbing as explicit alternative routed fields, preventing discipline-specific field handling bugs.
- Fire water storage can route explicit total_storage_m3 into a preliminary fire_tank drawing object.
- Plumbing water demand can route explicit design_demand_lpm into a preliminary water_demand drawing object.
- Existing explicit Fire protection_type and Plumbing fixture_type drawing paths remain supported.
- Both new adapters now preserve skill_version in SkillResult.
- Added AT-63, AT-64 and AT-65 covering calculation-to-layout and combined controlled package lineage.
- AT-65 verifies that Fire and Plumbing preliminary drawings can be combined into one job-linked drawing package while remaining not approved / not dispatchable until the engineering Job approval gate.
- Registry verification: 25 registered skill IDs; 24 integrated/executable; chiller_efficiency remains source-audit-pending.
- Verification limitation: this environment has no local repository checkout and cannot execute pytest locally; the GitHub connector did not expose an Actions run for these direct-main commits. Therefore no new CI pass is claimed for this checkpoint. The previously verified main suite remains 272 passed on run 37346834387 before these later additions.
- Vercel statuses are deployment checks only and are not being used as a substitute for the required Render live verification.
- Canonical live deployment remains Render. Live Fire/Plumbing calculation, drawing package, approval, controlled PDF/DXF artifact, Evidence Register and Revision History verification still requires the Render connection/live environment.


- Added a controlled drawing-dispatch regression confirming an approved Fire drawing package produces a preliminary/watermarked PDF and hashed DXF ZIP before controlled issue.


- Report Register enhancement: controlled drawing artifacts are now merged into report-register rows and Excel export, including drawing status, manifest SHA-256, drawing PDF SHA-256, DXF ZIP SHA-256 and availability. Dashboard Evidence view exposes those hashes and provides controlled Drawing PDF/DXF download actions.
- Added regression coverage for Supabase-backed register merging of drawing artifacts.


- Acceptance reconciliation: AT-59 now records persistent drawing artifact/evidence linkage as implemented; AT-60 records controlled PDF/DXF dispatch, private storage and hashes as implemented at repository/API level, with only the live Render issue trial still pending.


## Live verification checkpoint — 2026-10-06 (final gate status)
- Render service `engineering-ai-platform-v1` is configured for automatic deployment from `main` and the current live deploy is commit `57336595019c18b203681987b52e82a18a3b778e`.
- Render runtime logs verified successful startup and authenticated dashboard/API traffic: `GET /v1/account`, `GET /v1/jobs`, `GET /v1/reports`, and an individual job report all returned HTTP 200.
- Production Supabase currently contains 18 jobs, including 6 at human review, 4 in approved-like/completed states, and 0 failed jobs in the current register query.
- Controlled report artifacts are proven in production for approved HVAC decarbonisation and VFD energy-savings jobs: approved watermark, PDF/XLSX SHA-256 values, approval timestamps and dispatch timestamps are persisted.
- The current live Trial 1 duct-sizing job `0be60e84-759b-4cc0-aef8-79024646f5e6` is correctly at `human_review` with a draft report; it has not been dispatched, so no approval is being fabricated.
- The persistent drawing-artifact register is currently empty. This is expected until an approved Job carrying a drawing package reaches controlled drawing dispatch; direct database insertion is not used because it would bypass the governed approval lifecycle.
- GitHub Actions has no workflow run exposed by the connected GitHub action for commit `57336595019c18b203681987b52e82a18a3b778e`; CI is therefore not claimed here without a verified run.
- Governance boundary remains unchanged: drawing outputs are AI-assisted preliminary engineering drawings and require qualified engineer review; `chiller_efficiency` remains source-audit pending.


## Latest implementation checkpoint — 2026-10-07 (consolidated intake/routing audit)
- Consolidated the recurring natural-language intake defect exposed by the chiller-selection trial.
- Chiller selection/recommendation requests are now prioritized before broad HVAC-energy rescue routing, preventing annual energy/cost wording from diverting a selection job into decarbonisation/payback.
- Semantic extraction now recognizes average operating load as load_factor_pct, ₹/kWh tariff notation, and an explicit “continue operating if one chiller is unavailable” statement as redundancy_level = N+1.
- Chiller advisor contract corrected: duty_modules is optional because a module count cannot be safely invented without an explicit module-capacity basis. When absent, the calculator reports module configuration as PENDING_MODULE_CAPACITY_BASIS.
- Chiller calculator now accepts N/N+1/N+2 redundancy text and reports the redundancy basis explicitly.
- Added tests/test_platform_intake_regression.py covering chiller fact extraction, routing priority and no-invention module handling.
- Consolidated implementation is on final commit 969816cbf80624b36c86c6a883a12ddc16312b17.
- Render deployment for that final commit succeeded at 2026-10-07 01:07:57Z. Runtime logs show application startup complete and the primary Render URL serving HTTP 200.
- Local pytest execution was unavailable in this environment; the regression test was added, and Render build/deploy succeeded. Do not claim the new pytest file was executed unless a later CI run verifies it.

## Latest implementation checkpoint — 2026-10-09 (production defect repair)

- Root cause of the live "Submit Request / Run trial not working" failures: earlier commits had written literal `\n` text into Python source. In `api/app.py` (commit 98f78f9) this turned the `/v1/intake` setup code (`provider`, `project_context`) into a comment, so every intake raised an unbound-variable error. In `orchestrator/intake.py` (commit 24d61b1) it caused an IndentationError that failed the Render build.
- Also fixed: `reports/artifacts.py` `build_evidence_xlsx` used `document_status` without defining it, so **Approve & Dispatch crashed** for every job. `orchestrator/intake.py` was missing the `ProviderUnavailableError` import.
- Plain-language VFD requests now extract motor kW, speed reduction %, static-head fraction %, annual hours and tariff (previously only "label: value" forms worked, which sent typed requests to Information Needed).
- Verified locally: free-text VFD request -> /v1/intake -> human_review -> approve+dispatch -> completed; result 130,233 kWh/yr. New tests in `tests/test_vfd_freetext_trial.py`.
- Lesson: after any automated edit run `python -m compileall .` and `python -m pyflakes` (undefined names) before committing.
- Known: 18 older tests still fail because they hard-code registry counts (22/23 skills) and lack standards-coverage entries for fire_water_storage / plumbing_water_demand. Not caused by these changes (they failed before).
- Live Render verification of the new deploy is still pending.

## Checkpoint — 2026-10-09 (report presentation + live trial verified)
- Live trial verified by the user: VFD Energy Savings trial (Job fe9e32bd) -> approve -> dispatch produced PDF + XLSX; numbers re-checked by hand (38.6% theoretical, 28.9% corrected, 130,233 kWh/yr, 1,106,979 cost at 8.5/kWh).
- Report clarity fixes: VFD calculation steps now carry worked numbers (`detail`), explicit labels/units in `reports/formatting.py::_DISPLAY_OVERRIDES` (currency is NOT assumed: "currency"), Summary "Limitations" falls back to warnings. Calculation values unchanged. Tests: `tests/test_vfd_report_content.py`.
- Dashboard JS syntax error (broke Jobs/Register "Loading...") fixed; `tests/test_dashboard_js_syntax.py` guards it with `node --check`.
- Still open: 18 stale tests (hard-coded 22/23 skill counts, standards-coverage entries for fire_water_storage/plumbing_water_demand); reconcile held-back `building/` text-schedule module with `engineering/building`; decision on "42 skills"; live Gmail/Upwork credentials.

## Checkpoint — 2026-10-10 (HVAC Design vertical, slice 1; test debt cleared)
- Decisions from the user (2026-10-10): "42 skills" = 42 real calculators (registry now 26 ids / 25 executable); HVAC Design vertical first; Gmail reply is an acceptable client reply channel; implement the whole Notion master prompt incrementally.
- Test debt cleared: suite is green (343 passed). Real bugs found and fixed on the way: natural-phrasing routing (duct/BMS/refrigerant/facade) and motor-kW/speed-reduction extraction in `orchestrator/intake.py`; fire/plumbing report profiles + explicit empty standards coverage; stale count/format tests updated to registry truth.
- NEW skill `hvac_design_package` (`skills/hvac/design_package/`): rooms[{room_id,name,area_m2,occupancy?}] + building_type + climate_zone -> per-room load (existing load estimator), supply airflow (CFM/TR basis), branch duct size (existing duct sizing), terminal-equipment class, block load with diversity, plant suggestion. Assumptions (cfm_per_tr=400, velocity=5 m/s, material, diversity) are explicit overridable inputs and always listed. Preliminary; human review required; no new engineering formulas.
- Reports now render lists of flat records as real tables (room schedule / rooms input) in PDF and XLSX (`reports/formatting.py::extract_tables`); assumptions/limitations no longer duplicated as result rows.
- Not done in the vertical yet: room-load model driven by envelope/orientation/ventilation, psychrometric airflow, duct network pressure balance, equipment model selection, pipe sizing, link of room schedule into the drawing routing (`/v1/drawings/route`), free-text room-list extraction (rooms currently via structured input), dashboard form for rooms.
- Still open from the master prompt: 17 more calculators toward 42, Energy Optimization and Decarbonization verticals, Sitetrack-style BOQ takeoff, Gmail/Upwork/CRM live pipeline (needs credentials), CAD generation, semantic PDF/CAD interpretation, live-DB check of multi-revision history, repo visibility/secrets audit.

## Checkpoint — 2026-10-10 (Gmail pipeline hardening; credentials still pending)
- Already existed: Gmail OAuth (`/v1/integrations/gmail/oauth/start|callback`), inbox sync -> one reviewable job per new message (+ attachments), de-dup by message id, and `POST /v1/jobs/{id}/gmail-reply` (draft by default, send only on explicit `mode=send`). Reply channel decision: Gmail reply is acceptable.
- Added: `POST /v1/integrations/gmail/sync-scheduled` for cron use. Authenticated only by header `X-Scheduler-Secret` == env `GMAIL_SCHEDULER_SECRET` (>= 24 chars, constant-time compare; normal user auth cannot use it). Fails closed unless `GMAIL_SYNC_QUERY` is set explicitly (e.g. `label:engineering-requests is:unread`), so the whole inbox is never ingested. Tenant from `GMAIL_SCHEDULER_TENANT_ID`.
- Added: `integrations/token_store.py` - refresh tokens encrypted (Fernet, `GMAIL_TOKEN_ENCRYPTION_KEY`) in Supabase table `integration_tokens` (migration `20261010060000_013_integration_tokens.sql`, must be applied in Supabase). Without the key it falls back to the ephemeral file store (tokens are lost on each Render redeploy). `cryptography` added to requirements.txt.
- Added: dashboard "Gmail Intake" card (connect, sync with filter, create draft reply) in an isolated script block.
- NOT verified live: no Google OAuth client exists yet. Needs `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REDIRECT_URI` (= <render-url>/v1/integrations/gmail/oauth/callback), `GMAIL_TOKEN_ENCRYPTION_KEY`, `GMAIL_SYNC_QUERY`, `GMAIL_SCHEDULER_SECRET`, `GMAIL_SCHEDULER_TENANT_ID` on Render, the migration applied, and a Render Cron Job calling the scheduled endpoint. All covered by unit tests with a fake Gmail client only.

## Checkpoint — 2026-10-10 (repository hygiene)
- Secret scan of all 639 commits for common key patterns (OpenAI/GitHub/AWS/Google/Slack tokens, JWTs, service_role, DB URLs): no hits. Only the Supabase *publishable* key appears (api/auth.py, login.html, index.html) which is public by design; Row Level Security must keep protecting data. Still rotate any key you remember ever pasting anywhere.
- Removed from the repo: 18 `*.py.*`/`*.yaml.*` manual backup copies, scratch files (bedrock/haiku/test JSON, app_page_test.js, auth_refresh_block.js, installed_packages_audit.txt). STEP*.txt audit dumps moved to docs/audit_archive/. `.gitignore` updated so they do not return.
- Repo is still public on GitHub; making it private is the owner's switch (Settings > General > Danger zone).

## Checkpoint 2026-10-10 — Dashboard HVAC Design form
- `web/app.html`: "HVAC Design Package" card (`#designCard`): building type, climate zone, diversity, CFM/TR, duct velocity, editable room rows. Posts `/v1/intake` with `requested_skill_id: hvac_design_package`; job lands in Ready for Review.
- Verified in headless Chromium with mocked API (validation, POST body, no page errors) and full suite (352 passed). NOT yet verified on live Render after deploy.

## Checkpoint 2026-10-10 — 17 governed calculators (42 skills total)
- `skills/calculators/` (catalogue + formulas): psychrometrics, cooling coil load, ventilation (62.1), fan power, water pipe sizing, expansion tank, hydronic flow, heat recovery, IPLV, duct pressure drop, insulation/condensation, cable voltage drop, sprinkler demand, hot-water heater, rainwater drainage, solar PV, carbon emissions. Registered in registry.yaml, bindings, profiles, coverage, scope, intake routing.
- `tests/test_calculator_catalogue.py`: hand-checked values + missing-input rejection. 42 executable skills.
- Defaults (grid factor, yields, NFPA-style densities, etc.) are listed as assumptions in each result; preliminary only, engineer must verify.
- Not yet verified live on Render.

## Checkpoint 2026-10-10 — Design package: ventilation, fans, chilled-water header
- `hvac_design_package` now also returns per-room outdoor air (ASHRAE 62.1 ref rates), fan motor kW, and a `plant_summary` (chilled-water flow, header DN, total fan kW). Optional inputs: `fan_pressure_pa`, `chw_delta_t_c`, `outdoor_db_c`+`outdoor_rh_pct` (adds ventilation load kW, reported but NOT added to room loads, to avoid double counting the benchmark). Dashboard form does not expose these optional fields yet.
- Still open: envelope/orientation/glazing loads, equipment model selection, link room schedule to drawing routing.

## Checkpoint 2026-10-10 — BOQ takeoff skill (43 executable skills)
- New skill `boq_takeoff` (`skills/commercial/boq_takeoff/`): input `boq_items` or `boq_csv`, optional company `recipes`; outputs line takeoff, per-line materials, consolidated procurement totals, unmatched lines. Unit conversion sqm/sqft, m/rft. Registered everywhere; PDF/Excel render tables.
- Fixed `scope_engine` bug: doubled backslashes in regexes meant "1200 sqft" was never extracted.
- Recipes in `scope_engine/catalog.yaml` are marked `validated: false` (gypsum, tile, GI duct, duct insulation): consumption/wastage are DEFAULTS and the report warns. Replace/extend with the SiteTrack recipes (pass in `recipes` or edit the catalog).
- Not done: BOQ file upload (xlsx) in the dashboard; HVAC recipes beyond duct sheet/insulation; live verification.

### SiteTrack recipe import (2026-10-10)
The sitetrack GitHub repo holds only the schema (tables `work_types`, `work_type_materials`); the real recipes live in the user's Supabase DB. `boq_takeoff` accepts them via `recipes_csv`. Export with this SQL (Supabase SQL editor -> download CSV):
```sql
select t.name as work_type, t.unit as work_unit, m.material_name, m.unit,
       m.consumption_per_unit, m.wastage_percent
from work_types t join work_type_materials m on m.work_type_id = t.id
order by t.name, m.material_name;
```
Recipes imported this way are treated as company-validated (no "unvalidated" warning).

## Checkpoint 2026-10-10 — Energy optimisation study (44 executable skills)
- New skill `energy_optimisation_study` (`skills/energy/study/`): baseline kWh/tariff + list of measures (vfd via governed affinity-law calc, solar by kWp x yield, custom kWh) with investment/O&M -> ranked by simple payback, avoided tCO2e, combined saving capped at baseline, residual emissions. Interactions not modelled (stated in assumptions). Routing is deliberately narrow ("energy study", "energy optimisation study", ...) so plain "energy optimisation of existing plant" still goes to `hvac_decarbonisation`.
- Hand-checked in `tests/test_energy_study.py`. Dashboard form not built yet; not verified live.
- Still open: Gmail/Upwork/CRM live (credentials), CAD generation, semantic PDF/CAD reading, SiteTrack recipe CSV from user, dashboard BOQ upload form.

## Checkpoint 2026-10-10 — Dashboard forms for BOQ takeoff and energy study
- `web/app.html`: `#boqCard` (CSV paste/file, optional recipes CSV) and `#energyCard` (baseline + measure rows). Isolated script; posts `/v1/intake` with requested_skill_id. Verified in headless Chromium (mocked API) and via `tests/test_dashboard_forms_api.py` (real intake -> approve -> dispatch).
- Fixed: `boq_takeoff` registry listed `boq_items` as required, which blocked CSV-only requests at intake (awaiting_information); both inputs are now optional, adapter requires one.
- Not verified on live Render.

## Checkpoint 2026-10-10 — Supabase/Render connectors used
- Applied migration `013_integration_tokens` to Supabase project `engineering-ai-platform` (vaxerlbgwwlfamncevdg). Security advisor: integration_tokens "RLS enabled, no policy" is intentional (service role only). Pre-existing WARN: `public.resolve_current_tenant_membership()` SECURITY DEFINER is executable by anon/authenticated; review whether anon execute is needed. Leaked-password protection is off in Supabase Auth.
- Render service `engineering-ai-platform-v1` (srv-daujn4e7bikc73at4om0) live on 0503466. Set env: GMAIL_TOKEN_ENCRYPTION_KEY, GMAIL_SCHEDULER_SECRET, GMAIL_SCHEDULER_TENANT_ID (default tenant 00000000-0000-0000-0000-000000000001), GMAIL_SYNC_QUERY, GMAIL_REDIRECT_URI. Still needed from the user (Google Cloud OAuth client): GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET. Cron job not created yet (paid Render plan; useless until OAuth is connected).
- SiteTrack Supabase project (senhystjytormmekmtwo) was paused; restored. Its public schema is EMPTY (work-library tables were never created), so there are no recipes to import; recipes must come from the user.

## Checkpoint 2026-10-11 — Room schedule extraction (text + DXF) feeding the design package
- `engineering/building/schedule.py`: `extract_room_schedule(text)` (name + area with unit, sqft converted, optional occupancy; skipped rows reported) and `extract_dxf_candidate_rooms(bytes)` (closed LWPOLYLINE with exactly one TEXT label inside; area from $INSUNITS; flagged inferred/review_required; nothing produced without units).
- `interpret_building_source` now returns `design_rooms` (ready for `hvac_design_package`) and `design_rooms_need_confirmation`. API building-interpretation endpoint passes DXF candidates.
- `hvac_design_package` accepts `rooms_text`; registry no longer lists `rooms` as required (same intake-stall bug as BOQ). Dashboard design form has a paste-schedule box.
- Limits: no OCR/vision (image-only PDFs still blocked), no DWG, no wall/door/service recognition, only LWPOLYLINE rooms.

## Checkpoint 2026-10-11 — CAD (DXF) generation for the HVAC design package
- `engineering/drawing/design_schematic.py` (uses `ezdxf`, added to requirements.txt): R2010 DXF, $INSUNITS=mm, layers A-ROOM / A-ROOM-TEXT / M-DUCT-SCHEM / M-EQUIP-TEXT / G-TITLE / G-NOTE. Rooms = area-proportional boxes (3:2) in a grid, duct circles at the sized diameter, load/airflow/terminal labels, plant summary, title block, red notes. It is a SCHEMATIC, NOT a floor plan (positions are not known); stated on the sheet. Deterministic bytes (ezdxf write-time GUID/timestamp normalised).
- `GET /v1/jobs/{id}/design-dxf` (jobs:read): only after dispatch (409 before), only if the job has a room schedule; returns JSON with base64 DXF + sha256. Generated on demand from the stored evidence bundle; nothing stored (no DB change).
- Dashboard: "Download DXF (schematic)" button on dispatched hvac_design_package jobs.
- Validated by reading back with ezdxf and `doc.audit()`; NOT opened in AutoCAD/BricsCAD/DWG TrueView by anyone yet.
- Not done: DWG output; true plan geometry (needs explicit room coordinates from a drawing/building model - `engineering/design/routing.py` already requires explicit coordinates); fire/plumbing drawings; DXF in the dispatched artifact set / Gmail reply attachments.

## Checkpoint 2026-10-11 — Audits and nominal sizing
- Secret scan of repo + full git history (sk-, AIza, ghp_, JWT, private keys, committed .env): nothing found; `.env.example` holds placeholders only. Repo can be switched to private safely from a secrets point of view (rotate nothing).
- Live DB check: all 14 `engineering_report_artifacts` rows are version 1; multi-revision history has NEVER been exercised live. Schema supports it (UNIQUE(job_id, version), version > 0). `tests/test_report_versions.py` proves with an ordering-aware fake that rework -> version 2, same content -> no new version, approved v1 untouched. A real live rework run is still the final proof.
- `hvac_design_package`: nominal capacity bands per room (split <=5 TR, package <=20 TR) and plant options (one unit / two equal units, rounded to the next nominal size; chiller series above 20 TR). Generic series, NOT vendor models; stated in limitations.

## Checkpoint 2026-10-11 — Optional component-summation room loads
- A room in `hvac_design_package` may carry `envelope`: `walls[{area_m2,u_value,delta_t_c}]`, `glazing[{area_m2,u_value,delta_t_c,shgc,solar_w_m2}]`, `lighting_w_m2`, `equipment_w_m2`, optional `person_sensible_w/person_latent_w` (defaults 75/55 W flagged as assumptions), `safety_margin_pct` (default 10). Load = steady-state sum x margin; every coefficient is caller-supplied (no built-in CLTD/solar tables). Rooms without `envelope` still use the benchmark; each row reports `load_method`. Hand-checked in tests (4,930 W x 1.10 = 5,423 W). API/JSON only; no dashboard fields yet.
- User reported being unable to complete a step on the Google Cloud console page (Gmail OAuth client); waiting for details.

## Checkpoint 2026-10-11 (Gmail dashboard fixes)
- Job ids: `_resolve_job_id` accepts a unique tenant-scoped prefix (>=8 chars); malformed ids give a clear error instead of Postgres 22P02.
- Dashboard API timeout raised 15s -> 30s (Render free plan wake-up). Root cause of the /v1/integrations timeout not confirmed from logs.
- Render logs showed live Gmail sync -> approve -> dispatch of job cfdf2677 succeeded; draft reply not yet verified with the correct id.

## Checkpoint 2026-10-11 (layman requests: governed standard assumptions)
- Missing non-critical inputs are filled from registered preliminary assumptions (governance/assumption_policy.py + assumptions/registry.yaml) and disclosed as ASSUMED_DUE_TO_CLIENT_DATA_UNAVAILABLE in result, evidence, PDF and Excel. Covers duct_sizing (method velocity, rectangular, 7 m/s), load climate zone, fan static pressure, refrigerant velocities, cooling tower range/approach/COC/drift.
- Core quantities (e.g. airflow) are never assumed. VFD static_head_fraction deliberately NOT assumed (0 would overstate savings).
- Fix: intake-applied assumptions now carried via assumptions_context.applied_input_assumptions to the executor; format_value no longer shows 1.81e-05 as 0.
- TODO: audit remaining skills for layman-friendly defaults (needs engineering sign-off on each default value).

## Checkpoint 2026-10-11 (layman HVAC design intake)
- More governed defaults: vrf combination ratio 100%, coil leaving 13C/90%, heat recovery 60% eff + exhaust 24C/50%, VFD derating ambient 40C/altitude 0, design-package climate zone.
- Intake: "design HVAC for ..." routes to hvac_design_package; building type inferred from words (office/hospital/retail); rooms parsed from prose ("a 120 m2 open office and a 30 m2 meeting room").
- orchestrator/result.py: engine assumptions AND intake-applied defaults are both disclosed (previously the latter were dropped when the engine had its own list).
- Known gap: no LLM provider key on Render (rule-based intake only); fan selection, cooling coil, heat recovery, pump head prose extraction still limited.

## Checkpoint 2026-10-11 (tabbed dashboard + Mars Engineering Solutions branding)
- web/app.html: five top tabs (New Request, Review & Jobs [badge], Reports, Design & Calculations [HVAC Design/BOQ/Energy/Trials picker], Gmail Intake); last tab remembered; submitting a form jumps to Review & Jobs with a toast. Job cards compact: AI interpretation + rework collapsed; Approve / Approve & Dispatch / View Report / View Evidence on one row. All element ids unchanged. Browser-tested with headless Chromium (scratchpad tabs.js/card.js).
- branding/: name, tagline, address/contact (env-overridable MARS_BRAND_NAME, MARS_TAGLINE, MARS_ADDRESS, MARS_EMAIL, MARS_PHONE, MARS_WEBSITE), vector logo (ReportLab) + SVG (web/mars-logo.svg).
- PDFs: branded header, faint monogram + diagonal "MARS ENGINEERING SOLUTIONS / APPROVED CONTROLLED DOCUMENT" watermark, address footer on every page. XLSX: print header/footer on every sheet, brand row on Summary, tab colours.
- Address is a placeholder "Delhi NCR, India" until the exact registered address is set in Render (MARS_ADDRESS). Phone/email taken from user's profile.
- Not done: Excel image watermark (openpyxl cannot place header images simply).

## Checkpoint 2026-10-11 (serial numbers, master register, layman catalogue intake)
- Migration 014a applied live: archive_20261011 schema (backup copy of 40 jobs, 236 events, 16 report rows, 4 integration events), automation_jobs.serial_no (unique), sequence public.job_serial_seq, function public.next_job_serial() (service_role only). Serial = YYYYMMDDHHMM (IST) + 5-digit counter, e.g. 20261010201000001. jobs/serials.py is the local fallback; Supabase store calls rpc next_job_serial on first save.
- The DELETE of the trial data was blocked/cancelled by the tooling when run from the assistant; the user must run the 4 DELETE statements in the Supabase SQL editor (data is already archived).
- Serial shown on job card, PDF, XLSX Summary, Gmail reply text, register (first column), register Excel (Master Register sheet, autofilter on all sheets). Reports tab = Master Register (dispatched), search by serial/report/job/project/client/skill/reviewer. Job id lookup (Gmail draft) accepts serial no.
- skills/calculators/prose.py: plain-sentence extraction for fan, coil, heat recovery, water pipe, ventilation, psychrometric, cable and duct pressure drop; extra routing phrases.

## Checkpoint 2026-10-12 (serial numbers live in DB; cleanup pending confirmation)
- Applied migration 014 to live Supabase: automation_jobs.serial_no, job_serial_seq (untouched, next = 00001), next_job_serial() (service_role only). Format YYYYMMDDHHMM (IST) + 5 digits.
- Archive copy of all current trial data taken in schema archive_20261012 (jobs 40, events 236, reports 16, usage_events 341). Live tables NOT yet cleared: delete call was cancelled by the user's permission prompt. Storage objects (32 files) also not deleted. Needs explicit user confirmation before retrying.
- Gmail connection (integration_connections/tokens) deliberately kept.

## Checkpoint 2026-10-12 (DXF + serial)
- DXF schematic is attached to the Gmail draft reply for hvac_design_package jobs (test_integration_api); DXF title-block reference now uses the job serial number.
- Open: user to clear old trial data in Supabase SQL editor (connector delete was cancelled twice); LLM key decision for AI interpretation; recipes CSV for BOQ; exact registered address (MARS_ADDRESS env).

## Checkpoint 2026-10-12 (Excel watermark + 4 calculators)
- Excel: faint tiled Mars watermark background picture on every sheet (post-processed zip; reports/xlsx_watermark.py, branding/watermark.py). Structure validated + opens in openpyxl/LibreOffice; on-screen look in desktop Excel NOT visually verified.
- New governed calculators (hand-checked in tests): pump_power_sizing, generator_sizing, transformer_sizing, domestic_water_tank_sizing. Registry now 49 ids / 48 executable. Defaults (e.g. DF 0.8, PF 0.8/0.9, 45 L/person/day) are planning values disclosed as assumptions - need engineer sign-off.
- Plain-sentence routing/extraction for the four.

## Checkpoint 2026-10-12 (fire / domestic-water schematic DXF)
- engineering/drawing/services_schematic.py: block-diagram DXF for sprinkler_demand / fire_water_storage (tank > pump > sprinklers > hose) and domestic_water_tank_sizing / plumbing_water_demand (UG tank > transfer pump > OH tank > fixtures). Numbers only from calculator output; pump head/selection stated as "not determined here". No pipe routes invented.
- Served by GET /v1/jobs/{id}/design-dxf and attached to the Gmail draft reply; dashboard DXF button shown for these skills too. Tests: tests/test_services_schematic.py (incl. API end-to-end).
- Earlier checkpoint correction: Excel faint Mars watermark background (84c1c24) and pump_power/generator/transformer/domestic_water_tank calculators (eb7fe47) were already built.
- Still not built: OCR of scanned drawings, DWG output, live Upwork/CRM pipeline.

## Pending: Docker deploy (added 2026-10-12)
Needed for DWG->DXF (LibreDWG dwg2dxf) and OCR/scanned plans (tesseract, OpenCV). Render free python runtime lacks these. Plan reader already reports DWG/images as unsupported until then.

## Docker candidate (2026-10-12)
docs/docker/Dockerfile written but NOT built/tested and NOT active. To switch: build locally, then on Render change runtime to Docker with dockerfilePath docs/docker/Dockerfile (env vars stay). The plan reader already calls `dwg2dxf` when present. OCR/scanned-plan reading code is NOT written yet (needs scale + wall detection; unreliable without a vision service).

## Checkpoint 2026-10-14 — BOQ takeoff and retrofit study
- BOQ takeoff: Excel (.xlsx) upload (dashboard + skill input `boq_xlsx_b64`), heading context carried into sub-lines, tender unit aliases, starter recipes (ceilings, partitions, wall tile, cables, trays, conduit, MS/GI pipes, louvers, dampers, fire door; all `validated: false`), `{spec}` size text in material names, equipment/lump-sum lines listed as `procure_as_specified`, optional AI-drafted recipes (`ai_draft.py`, needs OPENAI_API_KEY and OpenAI credit; flagged unverified). RITES BOQ: 39 lines taken off, 142 procure-as-specified, 0 unmatched.
- OpenAI key is set on Render; live test returned 429 `insufficient_quota` (account has no credit). Pipeline otherwise worked live.
- New skill `retrofit_study` (skills/energy/retrofit): plant survey -> baseline (reconciled with measured kWh, warning over 15%) -> options incl. `efficiency_upgrade` (E x (1 - new/old)) -> ranked and phased. No dashboard form yet (works via API/Gmail routing with phrases like "retrofit study"). 509+ tests pass. Not verified on live Render.

## Checkpoint 2026-10-14 — Layout sizing + master-prompt status
- `engineering/layout/sizing.py`: routed duct trunk and sprinkler main are split at junctions, loads accumulated to the plant, then sized PRELIMINARILY (round duct by velocity limit with Darcy-Weisbach friction; light-hazard pipe-schedule head counts, hydraulic calc flagged above 100 heads). Sizes labelled on the layout DXF (M-TAG / F-TAG) and returned in `summary["sizing"]` with length per size. New params `supply_air_m3h_per_m2` (20) and `duct_max_velocity_ms` (6). Not covered: branch ducts, fittings, rectangular ducts, other hazard classes, hydraulics, clash check. 516 tests pass.
- Sample plans for trials generated from `engineering/plan/samples.py` (DXF mm and PDF 1:100).
- Master-prompt status: calculators 49 executable (target 42 exceeded); HVAC design, BOQ takeoff, energy study, retrofit study, layout + sizing built. Remaining items depend on the owner or infrastructure: OpenAI credit (AI drafting), Docker/OCR/DWG, live Upwork/CRM, Gmail cron after trial sign-off, engineer sign-off on defaults/recipes, MARS_ADDRESS, old trial data clear.
- Owner plan: salaried job to Dec 2026, platform in test-only mode; monetisation (fixed-fee services) from Jan 2027.

## Checkpoint 2026-10-14 — Dashboard look + CRM & Clients tab
- web/app.html: visible Mars watermark (fixed tiled SVG overlay, low opacity, prints too), gradient header with skyline/duct illustration and strap line, softer cards. New tab "CRM & Clients": KPI tiles (open deals, open pipeline value, follow-ups due, won value), Pipeline board with stage drop-down per card, Add/Edit Deal form, Clients view. Uses existing /v1/crm routes (GET list, POST create, PATCH update); follow-up empty sent as null.
- Clients are DERIVED (no new table): deal.company and job project_context.client grouped case-insensitively. A proper client table, per-client storage folders, Gmail/Upwork enquiry -> deal, won deal -> job are still TODO.
- Browser-tested headlessly with mocked API (board, move stage, add deal, client view); not yet seen on live Render.
- CRM delivery tracking (2026-10-14): migration 015 (applied live) adds crm_deals.delivery jsonb. Per deal: delivered_on, final_submitted_on, invoice no/date/amount, revisions[{no,date,note}], payments[{date,amount,ref}]; server computes paid_total, outstanding, payment_status (not_invoiced/invoiced/part_paid/paid). `normalize_delivery` in crm/models.py validates (dates YYYY-MM-DD, non-negative amounts, <=50 revisions, <=100 payments). Dashboard: CRM > Delivery & Payments (won deals) + "Payments outstanding" tile. No automated reminders or invoice PDFs yet.
- CRM auto-linking (2026-10-14): `crm/linker.py` CRMLinker attached to JobService.observers (default service factory in api/app.py). Job created (any source: form, request, Gmail) -> find/create deal (same client + project name, stage Budgetary, follow-up +3 days, category from skill hint), link job, store `crm_deal_id` in job.project_context. Rework -> numbered revision with the reviewer comment. Dispatch -> delivered_on (first) and final_submitted_on (latest). Client name = explicit client, else sender display name, else company domain (free-mail/Upwork/Fiverr/LinkedIn senders give none). Errors are swallowed so CRM can never break a job. Payments, deal value and stage changes beyond Budgetary stay manual. Tests: tests/test_crm_linker.py. No UI to delete auto-created deals (use Closed - Lost).
- Fix 2026-10-15: dispatch of a boq_takeoff job failed ("Flowable Table ... too large") because the uploaded workbook (`boq_xlsx_b64` input, ~46k chars) was dumped into one PDF table cell. `reports.formatting.shorten_for_report` now replaces long/base64 strings (>500 chars) with a short note in PDF and Excel (full value stays in evidence). Regression: tests/test_report_long_values.py. A job whose dispatch fails is status `failed` and cannot be re-dispatched; resubmit it. TODO: a retry-dispatch path for failed jobs.
- Memory fix 2026-10-15: Render free instance (512 MiB limit) hit 528 MB and restarted while processing a BOQ upload. Cause: the uploaded workbook (base64, 108 KB) was copied 24 times into one job record (3.7 MB; every save/GET moved it). `jobs/compact.py` `compact_large_values` (strings > 20,000 chars -> marker with length + sha256) now applied to orchestration/event plan copies, workflow output, consolidated result and the evidence bundle's request/orchestration; `job.inputs` keeps the only full copy and `manifest.input_hash` is still sha256 of the full inputs (unchanged value). Job record ~1.2 MB. Not yet verified live; Render free plan is also only ~0.1 CPU. Remaining ideas: lighter dashboard polling, paid instance with more CPU/RAM.


## 2026-10-15 checkpoint: BOQ report grouped per item
- PDF: each BOQ item is a block (heading, description, its materials with qty + basis), then Material Totals. Excel: sheet 'BOQ Item Materials' (item rows with materials under them); flat 'Line Takeoff'/'Line Materials' sheets removed (data stays in evidence JSON as line_takeoff/line_materials/boq_breakdown).
- Recipe matching now token-based (any word order, e.g. 'gypsum board false ceiling').

- Work Programme (client bonus): skills/commercial/boq_takeoff/programme.py. Days per item from crew output per gang-day (overridable via inputs productivity/gangs/working_days_per_week/start_date), staged sequence with 40% overlap, critical path, Gantt in PDF + Excel sheet "Work Programme". No prices anywhere.

- Client file view (CRM > Clients): name variants merged (Ltd/Pvt Ltd/Limited), totals (quoted/invoiced/received/outstanding), documents folder per project with PDF/Excel downloads. Browser-tested with mocked API. Real client table in DB still not built (clients derived from names).
- CRM "Needs your attention" panel on Pipeline: follow-ups due, won-not-delivered, delivered-not-invoiced, payments outstanding (in-app only, no email/WhatsApp yet).
- Send Status Report tab: POST /v1/status-report/send (jobs:read scope, 2-min rate limit) emails status summary via connected Gmail (to STATUS_REPORT_EMAIL or the Gmail account) and WhatsApp via Twilio when TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, STATUS_REPORT_WHATSAPP_TO are set.

## 2026-10-16: drawing-based BOQ takeoff
- engineering/services_takeoff/measure.py: reads DXF only; measures runs by service layer + size label, counts elbows/tees/crosses/reducers from geometry, devices from blocks/symbols. boq_link.py: classifies BOQ lines (plumbing/fire/hvac pipe, duct, duct insulation, conduit, wiring, tray, fixtures), builds materials (pipe, fittings, couplings, supports; duct sheet area, joints, hangers; conduit bends, boxes, saddles; wire = conduit x wires), notes drawing vs BOQ variance. Inputs drawing_dxf_b64, drawing_filename, drawing_units, drawing_factors. Not done: DWG (needs Docker), PDF/scans, per-size branch labelling is only as good as the drawing labels.
- Hotel BOQ+schematic DXF trial (2026-10-16): fixed fire/lighting layer names, noun-style fixture lines, linear-unit gate for pipe items, condensate=HVAC, rival unsized items not split, schematic warning, drawing_repeat multiplier (floors).

## Checkpoint 2026-10-16 (night)
- Added "Retry dispatch" for jobs whose dispatch failed (service.retry_dispatch, POST /v1/jobs/{id}/retry-dispatch, button on failed job cards). 539 tests passing.
- Added optional preliminary duct sizing from diffuser airflow for unsized duct runs (engineering/services_takeoff/autosize.py; input drawing_cmh_per_diffuser; BOQ form field). Plant position is ASSUMED (far end of unsized network) and disclosed. 542 tests passing.

## Checkpoint 2026-10-17 (morning)
- Cause of stuck jobs: Render OOM kill (512 MB) at 00:51Z while dispatching the RITES job; job left in dispatching/processing.
- Added: JobService.recover_interrupted (runs on GET /v1/jobs; fails jobs stuck >10 min), JobService.retry + POST /v1/jobs/{id}/retry + dashboard "Retry" button on failed jobs; api/memory.py (glibc arena cap=2, malloc_trim after each request, [memory] log line when rss>=300MB); WSGI workers 10 -> 4.
- Local profile of the RITES BOQ (process+PDF+Excel) peaks ~75 MB, so the Render memory growth is in the Supabase path (per-thread clients / big row JSON). Watch Render logs for "[memory]" lines to confirm.
- Catalog: supporting materials (fasteners, flanges/gaskets, electrodes, paint, adhesive, tapes, glands, lugs, ties, anchors, sealants, hardware) added to the MEP recipes; names containing commas must be quoted in YAML flow mappings (test added).
- 2026-10-17: Dashboard live progress: animated run box + stage steps + elapsed timer on In Progress job cards (auto-refresh every 6 s while a job runs), and a bottom-right activity box for every save/submit/approve/dispatch call (global fetch wrapper); action timeouts raised from 30/60 s to 240 s.

## Checkpoint 2026-10-18
- Download fix: the page opened the signed file URL with window.open after a ~20 s wait, which Chrome blocks as a pop-up (server logs showed 200 OK). downloadArtifact now downloads in the same tab via an anchor and also shows a visible link. Artifact endpoint no longer loads the whole job, and selects only file columns (faster).
- Consolidated material list: material_totals now carries trade + Main/Supporting type; PDF has a stand-alone "Consolidated material list" page (grouped by trade), Excel has a "Consolidated Materials" sheet, dashboard BOQ view shows the table. 548 tests passing.

## 2026-10-18 evening: trade secret + consolidated procure list
- Client PDF/Excel no longer show calculation basis: Basis columns, recipe names, recipe factors, programme basis, calculation steps and unvalidated-defaults note are stripped by `reports/client_safe.py` (applied at the start of build_approved_pdf / build_evidence_xlsx). Stored job record and owner data are unchanged.
- Procure-as-specified lines are merged (same description+unit, qty summed, item numbers listed) and grouped by equipment category (`skills/commercial/boq_takeoff/procure.py`); new PDF page and Excel sheet "Procure As Specified".

## 2026-10-18 night: routing fix
- A full "HVAC design package ... duct sizing ..." request was routed to the single duct_sizing calculator (job fc511cdf asked for airflow). Added an explicit design-package rule ahead of the single-calculator rules in orchestrator/intake.py.
- Known gaps seen in the local run: the design package uses benchmark loads and ignored the typed envelope/design-condition values; room names came out as "Space N"; only the listed rooms are counted (515 sqm, not the 12,000 sqm building).
- Fixed (same night): room rows typed as "Name, 60 sqm, 10 people" keep names and people counts; "12,000 sqm built-up" is no longer read as a room; indoor DB/RH and outdoor DB/WB (converted to RH) typed in the request are passed to the design package (`engineering/building/prose_inputs.py`). Still not used: typed U-values / glass % / SHGC / W-per-sqm (needs wall and glass areas per room), whole-building scaling.
