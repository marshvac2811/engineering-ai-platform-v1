# Supabase persistence layer

This folder contains the first persistent queue/audit contract for the Engineering AI Platform.

Apply `migrations/001_automation_jobs.sql` to the Supabase Postgres database before using `SupabaseJobStore`.

## Tables

- `automation_jobs` — durable job payload, lifecycle state, result, errors/warnings, retry attempt, priority and worker lock.
- `automation_job_events` — append-style audit trail for lifecycle and review events.

## Queue RPCs

- `claim_next_automation_job(worker_id, lock_seconds)` — claims one queued job using `FOR UPDATE SKIP LOCKED`.
- `heartbeat_automation_job_claim(job_id, worker_id)` — extends an active worker claim.
- `release_automation_job_claim(job_id, worker_id)` — releases a claim.

## Security

The starter migration enables RLS and grants full table access only to the Supabase `service_role`.
Tenant/user policies should be added before exposing these tables directly to browser clients.

## Tenant security checkpoint

Apply `migrations/001_automation_jobs.sql` followed by `migrations/002_tenant_security.sql`. The second migration adds `app_tenants`, `tenant_memberships`, tenant ownership on jobs, authenticated RLS, and service-role-only queue claim/heartbeat/release RPC access. Lifecycle UPDATE access is intentionally server-side only.

For production, replace the migration-default tenant mapping with real tenant provisioning before accepting client traffic.
