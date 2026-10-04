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

## Status: working end-to-end for 22 skills
Request -> AI interpretation -> deterministic skill calculation -> evidence capture ->
human review -> approve/rework -> dispatch -> PDF + Excel with hashes. All 22 executable
skills (chiller_efficiency is the only one pending source audit) go through this chain.

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
- 220+ automated tests passing (run: python -m pytest -q from repo root).
- Trial prompt bank: 110 realistic prompts (5 per skill x Simple/Mild/Heavy) kept outside
  the repo as an Excel tracker, given to the user directly in chat (not in this repo).

## Not done yet (in priority order discussed with user)
1. skill_version and source_revision surfaced into the PDF/Excel (currently only in raw
   evidence JSON, not the readable report).
2. "Limitations" field carried from skill result -> evidence -> report.
3. Rework-after-approval (currently rework only works before approval).
4. Register "Evidence" and "Revision History" as dedicated tabs (currently just a skill
   filter + superseded flag on rows).
5. 42-skill scope decision still open: Option A (42 real engineering skills) vs Option B
   (42 test scenarios using the existing 22). User has not chosen yet.
6. 22-skill acceptance matrix: one full end-to-end test per skill (request -> PDF -> XLSX
   -> dispatch) is not built; current tests are unit-level per skill.
7. Gmail/Upwork/Gumroad: need the user's real API credentials in Render env vars to go
   live. Code is ready, untested against real accounts.
8. CRM workflow requested by user: Upwork -> Gmail -> CRM -> this platform -> reply back
   through the same chain. Architecture discussed, not yet built - see chat for design.

## How to resume cheaply
- Don't paste old conversation. Just point Claude at this file plus whatever specific
  task you want next (e.g. "build item 3 from the Not done list").
- Claude should `git clone` the repo fresh, read this file, then read only the specific
  source files relevant to the task - not the whole repo.
- Tests: `python -m pytest -q` from repo root before and after any change.
- Push access: user grants a short-lived GitHub classic token (repo scope) when needed;
  delete it from GitHub afterwards.

Last updated: 2026-10-03, after Report Register export button + rework/resubmit flow.
