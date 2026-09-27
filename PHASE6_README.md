# Engineering AI Platform V1 — Phase 6

## What changed

Phase 6 reconciles the application with the live Supabase schema and makes engineering compliance auditable and durable.

### Production schema alignment
- Preserves the already-applied `010_engineering_workflow_plan` migration locally.
- Preserves `automation_jobs.orchestration`.
- Preserves `engineering_report_artifacts`.
- Adds `engineering_compliance_checks`.
- Adds `engineering_compliance_evidence`.
- Adds tenant-scoped RLS policies for the new compliance tables.

### Application alignment
- Supabase job persistence now writes the orchestration plan into `automation_jobs.orchestration`.
- Compliance checks produced by engineering skills are normalized into `engineering_compliance_checks`.
- Evidence metadata is persisted into `engineering_compliance_evidence` when the skill supplies a source type.
- Existing job lifecycle remains authoritative.
- Persistence is backward-compatible: older deployments without the new compliance tables do not fail engineering execution.

## Verification
- Deterministic regression: 88 passed, 1 existing dependency warning.
- Live Supabase migration applied and verified.
- Live compliance tables have RLS enabled.
- Existing live security advisor warning: leaked-password protection disabled.

## Standards governance
The standards registry remains metadata/structured-requirement based. It does not redistribute copyrighted standards. Reports should identify authority, edition and clause and distinguish applicability from reference material.

## Install
Extract this ZIP over the existing `C:\engineering_ai\engineering_ai_platform_v1` project and overwrite application files. Keep the existing `.env` file.

Do not manually edit the remote Supabase schema; the migration is already applied to the connected Engineering AI Platform project. Future schema changes should remain migration-controlled.
