-- Reconstructed local baseline for the already-applied remote workflow-plan migration.
-- The production project already records this migration. Keeping the same version
-- locally prevents migration-history drift and allows a clean local reset.

alter table public.automation_jobs
    add column if not exists report_id uuid,
    add column if not exists orchestration jsonb not null default '{}'::jsonb;

create table if not exists public.engineering_report_artifacts (
    report_id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    job_id uuid not null references public.automation_jobs(job_id) on delete cascade,
    version integer not null,
    status text not null default 'draft',
    title text not null,
    skill_id text,
    report jsonb not null default '{}'::jsonb,
    content_sha256 text not null,
    html_path text not null,
    pdf_path text not null,
    reviewer text,
    review_comment text not null default '',
    created_at timestamptz not null default now(),
    approved_at timestamptz,
    constraint engineering_report_version_check check (version > 0),
    constraint engineering_report_status_check check (status in ('draft','approved')),
    unique (job_id, version)
);

alter table public.automation_jobs
    drop constraint if exists automation_jobs_report_fk;
alter table public.automation_jobs
    add constraint automation_jobs_report_fk
    foreign key (report_id) references public.engineering_report_artifacts(report_id) on delete set null;

create index if not exists automation_jobs_report_idx
    on public.automation_jobs (tenant_id, report_id) where report_id is not null;
create index if not exists engineering_report_tenant_created_idx
    on public.engineering_report_artifacts (tenant_id, created_at desc);
create index if not exists engineering_report_tenant_job_idx
    on public.engineering_report_artifacts (tenant_id, job_id, version desc);

alter table public.engineering_report_artifacts enable row level security;

drop policy if exists engineering_report_authenticated_select on public.engineering_report_artifacts;
create policy engineering_report_authenticated_select
on public.engineering_report_artifacts for select to authenticated
using (public.is_tenant_member(tenant_id));

drop policy if exists engineering_report_service_role_all on public.engineering_report_artifacts;
create policy engineering_report_service_role_all
on public.engineering_report_artifacts for all to service_role
using (true) with check (true);
