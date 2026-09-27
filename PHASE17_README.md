# Phase 17 — Upwork Production Workflow

Phase 17 connects the existing provider-neutral integration boundary to a first-class business workflow task without replacing the authoritative engineering JobService/orchestrator.

## Added
- Upwork OAuth 2.0 start/callback boundary.
- Tenant-scoped, single-use OAuth state for local/trial use.
- Local trial Upwork token store; production must move secrets/tokens to encrypted tenant storage.
- First-class `WorkflowTask` with business lifecycle states.
- External-event idempotency at the task layer.
- Task → Engineering Job linkage.
- Supabase migration for `workflow_tasks` with tenant RLS and external-event uniqueness.
- API routes for task creation/list/get/status transition.
- Upwork event intake can create a business task before engineering execution.

## Important boundary
Upwork API access is not claimed to be live merely because the adapter exists. Upwork requires OAuth 2.0 credentials and application approval/appropriate scopes; webhook subscriptions may require Upwork review. Configure credentials only when ready.

## Existing architecture preserved
`Integration → Workflow Task → Requirement/Intake → JobService/Orchestrator → Engineering Skill → Compliance → Report/Drawing → Human Review → Delivery`

Do not bypass JobService or create a second engineering execution engine.
