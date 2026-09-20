-- Canonical MEP CRM / pipeline. External CRMs synchronize through adapters.
create table if not exists public.crm_deals (
    deal_id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    name text not null,
    category text not null default 'Project Sales',
    stakeholder text not null default 'Other',
    contact text not null default '',
    company text not null default '',
    value numeric not null default 0,
    stage text not null default 'budgetary',
    next_follow_up date,
    notes text not null default '',
    engineering_job_id uuid references public.automation_jobs(job_id) on delete set null,
    hubspot_object_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint crm_deals_category_check check (category in ('Project Sales','Retrofit Jobs','Energy Optimization')),
    constraint crm_deals_stakeholder_check check (stakeholder in ('Consultant','Builder','Developer','Contractor','End Client','Other')),
    constraint crm_deals_stage_check check (stage in ('budgetary','tendering','quotation','followup','negotiation','won','lost')),
    constraint crm_deals_value_check check (value >= 0)
);

create index if not exists crm_deals_tenant_stage_idx on public.crm_deals (tenant_id, stage, updated_at desc);
create index if not exists crm_deals_followup_idx on public.crm_deals (tenant_id, next_follow_up);
create index if not exists crm_deals_engineering_job_idx on public.crm_deals (tenant_id, engineering_job_id);

alter table public.crm_deals enable row level security;

drop policy if exists crm_deals_authenticated_select on public.crm_deals;
create policy crm_deals_authenticated_select on public.crm_deals
for select to authenticated using (public.is_tenant_member(tenant_id));

drop policy if exists crm_deals_authenticated_write on public.crm_deals;
create policy crm_deals_authenticated_write on public.crm_deals
for all to authenticated using (public.is_tenant_member(tenant_id)) with check (public.is_tenant_member(tenant_id));

drop policy if exists crm_deals_service_role_all on public.crm_deals;
create policy crm_deals_service_role_all on public.crm_deals
for all to service_role using (true) with check (true);
