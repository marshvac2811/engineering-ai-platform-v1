create index if not exists automation_jobs_tenant_created_idx
on public.automation_jobs (tenant_id, created_at);
