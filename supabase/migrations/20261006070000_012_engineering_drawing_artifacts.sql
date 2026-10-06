create table if not exists public.engineering_drawing_artifacts (
  drawing_artifact_id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  job_id uuid not null references public.automation_jobs(job_id) on delete cascade,
  report_id uuid,
  report_revision integer not null default 1,
  project_name text,
  status text not null default 'not_approved',
  dispatch_allowed boolean not null default false,
  manifest jsonb not null,
  drawings jsonb not null default '[]'::jsonb,
  manifest_sha256 text not null,
  pdf_sha256 text,
  pdf_storage_path text,
  pdf_filename text,
  dxf_zip_sha256 text,
  dxf_zip_storage_path text,
  dxf_zip_filename text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  dispatched_at timestamptz
);

create index if not exists engineering_drawing_artifacts_tenant_created_idx
  on public.engineering_drawing_artifacts (tenant_id, created_at desc);
create index if not exists engineering_drawing_artifacts_job_revision_idx
  on public.engineering_drawing_artifacts (job_id, report_revision desc);

alter table public.engineering_drawing_artifacts enable row level security;

create policy engineering_drawing_artifacts_tenant_read
  on public.engineering_drawing_artifacts
  for select using (public.is_tenant_member(tenant_id));

insert into storage.buckets (id, name, public)
values ('engineering-drawing-artifacts', 'engineering-drawing-artifacts', false)
on conflict (id) do nothing;
