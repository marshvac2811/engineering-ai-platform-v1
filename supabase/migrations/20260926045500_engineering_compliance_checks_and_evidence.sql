-- Durable, normalized compliance checks and evidence for engineering jobs.

create table if not exists public.engineering_compliance_checks (
    check_id uuid primary key default gen_random_uuid(),
    job_id uuid not null references public.automation_jobs(job_id) on delete cascade,
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    requirement_id text not null,
    status text not null,
    input_value numeric,
    required_value numeric,
    unit text not null default '',
    calculation text not null default '',
    clause_reference text not null default '',
    authority text not null default '',
    code_name text not null default '',
    edition text not null default '',
    requirement_type text not null default '',
    evidence jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (job_id, requirement_id)
);

create index if not exists engineering_compliance_checks_tenant_idx
    on public.engineering_compliance_checks (tenant_id, created_at desc);
create index if not exists engineering_compliance_checks_job_idx
    on public.engineering_compliance_checks (job_id, created_at);

create table if not exists public.engineering_compliance_evidence (
    evidence_id uuid primary key default gen_random_uuid(),
    check_id uuid not null references public.engineering_compliance_checks(check_id) on delete cascade,
    job_id uuid not null references public.automation_jobs(job_id) on delete cascade,
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    source_type text not null,
    source_reference text not null default '',
    document_reference text not null default '',
    calculation_reference text not null default '',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists engineering_compliance_evidence_check_idx
    on public.engineering_compliance_evidence (check_id, created_at);
create index if not exists engineering_compliance_evidence_tenant_idx
    on public.engineering_compliance_evidence (tenant_id, created_at desc);

alter table public.engineering_compliance_checks enable row level security;
alter table public.engineering_compliance_evidence enable row level security;

drop policy if exists engineering_compliance_checks_authenticated_select on public.engineering_compliance_checks;
create policy engineering_compliance_checks_authenticated_select
on public.engineering_compliance_checks for select to authenticated
using (public.is_tenant_member(tenant_id));

drop policy if exists engineering_compliance_checks_service_role_all on public.engineering_compliance_checks;
create policy engineering_compliance_checks_service_role_all
on public.engineering_compliance_checks for all to service_role
using (true) with check (true);

drop policy if exists engineering_compliance_evidence_authenticated_select on public.engineering_compliance_evidence;
create policy engineering_compliance_evidence_authenticated_select
on public.engineering_compliance_evidence for select to authenticated
using (public.is_tenant_member(tenant_id));

drop policy if exists engineering_compliance_evidence_service_role_all on public.engineering_compliance_evidence;
create policy engineering_compliance_evidence_service_role_all
on public.engineering_compliance_evidence for all to service_role
using (true) with check (true);
