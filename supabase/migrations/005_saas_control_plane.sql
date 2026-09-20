-- Commercial SaaS control plane: plans, API keys, usage metering, and tenant members.

alter table public.app_tenants
    add column if not exists plan text not null default 'trial';
alter table public.app_tenants
    add column if not exists status text not null default 'active';

alter table public.app_tenants
    drop constraint if exists app_tenants_plan_check;
alter table public.app_tenants
    add constraint app_tenants_plan_check
    check (plan in ('trial','starter','professional','business','enterprise'));

alter table public.app_tenants
    drop constraint if exists app_tenants_status_check;
alter table public.app_tenants
    add constraint app_tenants_status_check
    check (status in ('active','suspended','cancelled'));

create table if not exists public.api_keys (
    api_key_id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    created_by uuid not null,
    name text not null,
    key_prefix text not null,
    key_hash text not null unique,
    role text not null default 'member',
    scopes jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    expires_at timestamptz,
    revoked_at timestamptz,
    constraint api_keys_role_check check (role in ('owner','admin','engineer','reviewer','member'))
);

create index if not exists api_keys_tenant_idx on public.api_keys (tenant_id, created_at desc);

create table if not exists public.usage_events (
    usage_event_id bigint generated always as identity primary key,
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    user_id uuid,
    event_type text not null,
    units numeric not null default 1,
    job_id uuid references public.automation_jobs(job_id) on delete set null,
    skill_id text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists usage_events_tenant_date_idx
    on public.usage_events (tenant_id, created_at desc);
create index if not exists usage_events_skill_idx
    on public.usage_events (tenant_id, skill_id, created_at desc);

create or replace view public.tenant_usage_monthly as
select
    tenant_id,
    date_trunc('month', created_at) as month,
    sum(units) as total_units,
    count(*) as event_count,
    count(*) filter (where event_type = 'skill_execution') as skill_executions,
    count(*) filter (where event_type = 'api_request') as api_requests
from public.usage_events
group by tenant_id, date_trunc('month', created_at);

alter table public.api_keys enable row level security;
alter table public.usage_events enable row level security;

drop policy if exists api_keys_authenticated_select on public.api_keys;
create policy api_keys_authenticated_select
on public.api_keys for select to authenticated
using (public.is_tenant_member(tenant_id));

-- API key issuance/revocation is server-side only.
drop policy if exists api_keys_service_role_all on public.api_keys;
create policy api_keys_service_role_all
on public.api_keys for all to service_role
using (true) with check (true);

drop policy if exists usage_events_authenticated_select on public.usage_events;
create policy usage_events_authenticated_select
on public.usage_events for select to authenticated
using (public.is_tenant_member(tenant_id));

drop policy if exists usage_events_service_role_all on public.usage_events;
create policy usage_events_service_role_all
on public.usage_events for all to service_role
using (true) with check (true);
