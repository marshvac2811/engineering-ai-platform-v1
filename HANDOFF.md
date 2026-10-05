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

## Status: V1 workflow functional; CI green; live Render artifact verification remains open

The core workflow is operational for 22 executable skills (23 registered; `chiller_efficiency` remains source-audit pending). Trial 1 reached human review with deterministic duct sizing, correct missing-input behavior, and traceability metadata. A production defect was then found: the dashboard Report view rendered only report metadata instead of the persisted engineering work items, and legacy evidence records could produce an apparently blank artifact workbook. The consolidated rendering/recovery fix has been merged; a fresh production deployment and one post-deploy Trial 1 dispatch verification remain required before declaring the artifact path closed.

## Done
- 22 engineering skills executable (HVAC, BMS, Energy, Commercial) - see
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
- Canonical deployment remains Render. Live `/health`/Trial 1/report/evidence/PDF/XLSX verification is still not confirmed from this chat because Render is not connected here.
- The existing Phase 16 drawing foundation is minimal: a CAD-neutral `DrawingModel` with points/lines/dimensions plus deterministic JSON serialization and a parametric facade-elevation example. It is **not** yet the building-layout/HVAC/fire/plumbing drawing engine described in the expanded roadmap.

Last updated: 2026-10-05, after CI recovery and drawing-foundation audit.
