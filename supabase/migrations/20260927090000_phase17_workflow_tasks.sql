create table if not exists public.workflow_tasks (
    task_id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    source text not null,
    external_id text,
    client_name text not null default '',
    client_contact text not null default '',
    company text not null default '',
    title text not null,
    requirement text not null default '',
    skill_id text,
    priority text not null default 'NORMAL',
    deadline timestamptz,
    status text not null default 'NEW',
    engineering_job_id uuid,
    deliverable text,
    follow_up_at timestamptz,
    notes text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint workflow_tasks_priority_chk check (priority in ('LOW','NORMAL','HIGH','URGENT')),
    constraint workflow_tasks_status_chk check (status in ('NEW','TRIAGE','AWAITING_CLIENT_INFO','READY_FOR_ENGINEERING','ENGINEERING','AWAITING_REVIEW','READY_FOR_DELIVERY','DELIVERED','FOLLOW_UP','COMPLETED','CANCELLED') )
);
create unique index if not exists workflow_tasks_external_uq on public.workflow_tasks(tenant_id, source, external_id) where external_id is not null;
create index if not exists workflow_tasks_tenant_status_idx on public.workflow_tasks(tenant_id, status);
create index if not exists workflow_tasks_tenant_followup_idx on public.workflow_tasks(tenant_id, follow_up_at);
alter table public.workflow_tasks enable row level security;
create policy workflow_tasks_tenant_select on public.workflow_tasks for select using (tenant_id = auth.uid());
create policy workflow_tasks_tenant_insert on public.workflow_tasks for insert with check (tenant_id = auth.uid());
create policy workflow_tasks_tenant_update on public.workflow_tasks for update using (tenant_id = auth.uid()) with check (tenant_id = auth.uid());
