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
