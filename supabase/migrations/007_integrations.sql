-- External integration registry and durable normalized events.
create table if not exists public.integration_connections (
    connection_id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    provider text not null,
    status text not null default 'configured',
    external_account_id text,
    scopes jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint integration_provider_check check (provider in ('gmail','upwork','fiverr','gumroad','hubspot')),
    constraint integration_status_check check (status in ('configured','connected','error','disabled')),
    unique (tenant_id, provider)
);

create table if not exists public.integration_events (
    integration_event_id bigint generated always as identity primary key,
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    provider text not null,
    event_type text not null,
    external_event_id text not null,
    source_message text,
    payload jsonb not null default '{}'::jsonb,
    received_at timestamptz not null default now(),
    unique (tenant_id, provider, external_event_id)
);

create index if not exists integration_events_tenant_date_idx
    on public.integration_events (tenant_id, received_at desc);
create index if not exists integration_events_provider_idx
    on public.integration_events (tenant_id, provider, received_at desc);

alter table public.integration_connections enable row level security;
alter table public.integration_events enable row level security;

drop policy if exists integration_connections_authenticated_select on public.integration_connections;
create policy integration_connections_authenticated_select on public.integration_connections
for select to authenticated using (public.is_tenant_member(tenant_id));

drop policy if exists integration_connections_service_role_all on public.integration_connections;
create policy integration_connections_service_role_all on public.integration_connections
for all to service_role using (true) with check (true);

drop policy if exists integration_events_authenticated_select on public.integration_events;
create policy integration_events_authenticated_select on public.integration_events
for select to authenticated using (public.is_tenant_member(tenant_id));

drop policy if exists integration_events_service_role_all on public.integration_events;
create policy integration_events_service_role_all on public.integration_events
for all to service_role using (true) with check (true);
