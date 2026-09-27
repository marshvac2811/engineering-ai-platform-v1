# Engineering AI Platform V1 — Phase 7

## First-class engineering reports

Phase 7 closes the reporting loop introduced in Phases 5–6.

### Application changes
- Supabase persistence now creates/version-controls `engineering_report_artifacts` from the engineering result.
- Report content is canonicalized and SHA-256 hashed.
- Re-saving an unchanged report updates its review status instead of creating duplicate versions.
- Human approval changes the persisted report artifact from `draft` to `approved`.
- Existing compliance checks/evidence remain normalized and tenant-scoped.
- Existing job lifecycle remains authoritative.

### API changes
- `GET /v1/jobs/{job_id}/report`
  - returns the latest versioned engineering report artifact when persisted
  - falls back to the in-job report for in-memory/local execution
- `GET /v1/jobs/{job_id}/compliance`
  - returns normalized compliance checks
  - falls back to the engineering result for in-memory/local execution

### Verification
- Full deterministic regression: **100 passed, 1 existing dependency warning**.
- No new Supabase schema migration is required in Phase 7; it uses the Phase 6 report/compliance schema.

### Production safety
- Existing tenant/RLS model is preserved.
- No secrets or `.env` files are included.
- No remote schema changes are required for this phase.

Supabase recommends keeping schema changes migration-controlled and aligned with the remote migration history. This phase deliberately adds application behavior only and does not bypass that workflow.
