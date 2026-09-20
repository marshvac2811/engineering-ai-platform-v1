-- Persistent job queue + audit trail for the Engineering AI Platform.
-- Designed for Supabase/PostgreSQL. No external provider dependency.

create extension if not exists pgcrypto;

create table if not exists public.automation_jobs (
    job_id uuid primary key,
    source text not null,
    requested_skill_id text,
    inputs jsonb not null default '{}'::jsonb,
    project_context jsonb not null default '{}'::jsonb,
    standards_context jsonb not null default '{}'::jsonb,
    assumptions_context jsonb not null default '{}'::jsonb,
    status text not null,
    skill_id text,
    result jsonb,
    dispatch_result jsonb,
    errors jsonb not null default '[]'::jsonb,
    warnings jsonb not null default '[]'::jsonb,
    attachments jsonb not null default '[]'::jsonb,
    attempt integer not null default 0,
    priority integer not null default 100,
    available_at timestamptz not null default now(),
    locked_at timestamptz,
    locked_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists automation_jobs_queue_idx
    on public.automation_jobs (status, available_at, priority desc, created_at);

create index if not exists automation_jobs_lock_idx
    on public.automation_jobs (locked_at, locked_by);

create table if not exists public.automation_job_events (
    event_id bigint generated always as identity primary key,
    job_id uuid not null references public.automation_jobs(job_id) on delete cascade,
    event_key text not null unique,
    event_type text not null,
    status text not null,
    message text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists automation_job_events_job_idx
    on public.automation_job_events (job_id, created_at);

create or replace function public.set_automation_job_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists automation_jobs_updated_at on public.automation_jobs;
create trigger automation_jobs_updated_at
before update on public.automation_jobs
for each row execute function public.set_automation_job_updated_at();

-- Claim one queued job without two workers receiving the same job.
create or replace function public.claim_next_automation_job(
    p_worker_id text,
    p_lock_seconds integer default 300
)
returns setof public.automation_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  with candidate as (
    select job_id
    from public.automation_jobs
    where status = 'queued'
      and available_at <= now()
      and (
        locked_at is null
        or locked_at < now() - make_interval(secs => greatest(p_lock_seconds, 1))
      )
    order by priority desc, created_at asc
    for update skip locked
    limit 1
  )
  update public.automation_jobs j
     set locked_at = now(),
         locked_by = p_worker_id
    from candidate c
   where j.job_id = c.job_id
  returning j.*;
end;
$$;

create or replace function public.heartbeat_automation_job_claim(
    p_job_id uuid,
    p_worker_id text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.automation_jobs
     set locked_at = now()
   where job_id = p_job_id
     and locked_by = p_worker_id;
end;
$$;

create or replace function public.release_automation_job_claim(
    p_job_id uuid,
    p_worker_id text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.automation_jobs
     set locked_at = null,
         locked_by = null
   where job_id = p_job_id
     and locked_by = p_worker_id;
end;
$$;

-- Minimal RLS policy set. Tighten further when tenant/account identity is introduced.
alter table public.automation_jobs enable row level security;
alter table public.automation_job_events enable row level security;

create policy if not exists automation_jobs_service_role_all
on public.automation_jobs
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');

create policy if not exists automation_job_events_service_role_all
on public.automation_job_events
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');
