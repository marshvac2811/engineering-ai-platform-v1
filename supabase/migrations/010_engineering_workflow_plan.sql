-- Persist the complete orchestration plan so incomplete jobs can be replanned
-- from the original request without relying on dashboard state.
alter table public.automation_jobs
    add column if not exists orchestration jsonb not null default '{}'::jsonb;
