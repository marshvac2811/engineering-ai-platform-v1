-- Tenant-aware SaaS security boundary.
-- Worker RPCs are server-side only; browser clients use authenticated RLS.

create table if not exists public.app_tenants (
    tenant_id uuid primary key default gen_random_uuid(),
    name text not null,
    slug text not null unique,
    created_at timestamptz not null default now()
);

create table if not exists public.tenant_memberships (
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    user_id uuid not null,
    role text not null default 'member',
    created_at timestamptz not null default now(),
    primary key (tenant_id, user_id),
    constraint tenant_memberships_role_check check (role in ('owner','admin','engineer','reviewer','member'))
);

create index if not exists tenant_memberships_user_idx
    on public.tenant_memberships (user_id, tenant_id);

insert into public.app_tenants (tenant_id, name, slug)
values ('00000000-0000-0000-0000-000000000001', 'Migration Default Tenant', 'migration-default')
on conflict (tenant_id) do nothing;

alter table public.automation_jobs add column if not exists tenant_id uuid;
update public.automation_jobs
   set tenant_id = '00000000-0000-0000-0000-000000000001'
 where tenant_id is null;
alter table public.automation_jobs alter column tenant_id set not null;

alter table public.automation_jobs drop constraint if exists automation_jobs_tenant_fk;
alter table public.automation_jobs
    add constraint automation_jobs_tenant_fk
    foreign key (tenant_id) references public.app_tenants(tenant_id) on delete cascade;

create index if not exists automation_jobs_tenant_queue_idx
    on public.automation_jobs (tenant_id, status, available_at, priority desc, created_at);

create or replace function public.is_tenant_member(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = p_tenant_id
      and tm.user_id = auth.uid()
  );
$$;

revoke all on function public.is_tenant_member(uuid) from public;
grant execute on function public.is_tenant_member(uuid) to authenticated;

drop policy if exists app_tenants_authenticated_select on public.app_tenants;
create policy app_tenants_authenticated_select
on public.app_tenants for select to authenticated
using (public.is_tenant_member(tenant_id));

drop policy if exists automation_jobs_authenticated_select on public.automation_jobs;
create policy automation_jobs_authenticated_select
on public.automation_jobs for select to authenticated
using (public.is_tenant_member(tenant_id));

drop policy if exists automation_jobs_authenticated_insert on public.automation_jobs;
create policy automation_jobs_authenticated_insert
on public.automation_jobs for insert to authenticated
with check (public.is_tenant_member(tenant_id));

-- Lifecycle updates are intentionally server-side only; authenticated clients do not receive direct UPDATE access.

drop policy if exists automation_job_events_authenticated_select on public.automation_job_events;
create policy automation_job_events_authenticated_select
on public.automation_job_events for select to authenticated
using (
    exists (
        select 1 from public.automation_jobs j
        where j.job_id = automation_job_events.job_id
          and public.is_tenant_member(j.tenant_id)
    )
);

drop policy if exists automation_job_events_authenticated_insert on public.automation_job_events;
create policy automation_job_events_authenticated_insert
on public.automation_job_events for insert to authenticated
with check (
    exists (
        select 1 from public.automation_jobs j
        where j.job_id = automation_job_events.job_id
          and public.is_tenant_member(j.tenant_id)
    )
);

-- Only trusted backend workers may claim/heartbeat/release queue locks.
drop function if exists public.claim_next_automation_job(text, integer);
create or replace function public.claim_next_automation_job(
    p_worker_id text,
    p_tenant_id uuid default null,
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
       and (p_tenant_id is null or tenant_id = p_tenant_id)
       and (locked_at is null or locked_at < now() - make_interval(secs => greatest(p_lock_seconds, 1)))
     order by priority desc, created_at asc
     for update skip locked
     limit 1
  )
  update public.automation_jobs j
     set locked_at = now(), locked_by = p_worker_id
    from candidate c
   where j.job_id = c.job_id
  returning j.*;
end;
$$;

revoke all on function public.claim_next_automation_job(text, uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_next_automation_job(text, uuid, integer) to service_role;
revoke all on function public.heartbeat_automation_job_claim(uuid, text) from public, anon, authenticated;
grant execute on function public.heartbeat_automation_job_claim(uuid, text) to service_role;
revoke all on function public.release_automation_job_claim(uuid, text) from public, anon, authenticated;
grant execute on function public.release_automation_job_claim(uuid, text) to service_role;

-- Service-role is for the trusted server process only.
drop policy if exists automation_jobs_service_role_all on public.automation_jobs;
create policy automation_jobs_service_role_all
on public.automation_jobs for all to service_role
using (true) with check (true);

drop policy if exists automation_job_events_service_role_all on public.automation_job_events;
create policy automation_job_events_service_role_all
on public.automation_job_events for all to service_role
using (true) with check (true);
