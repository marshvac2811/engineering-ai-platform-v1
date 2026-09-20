-- Document/file ingestion storage metadata and chunk index for downstream AI retrieval.
create table if not exists public.automation_attachments (
    attachment_id uuid primary key,
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    job_id uuid not null references public.automation_jobs(job_id) on delete cascade,
    filename text not null,
    mime_type text not null,
    source_type text not null,
    size_bytes bigint not null,
    sha256 text not null,
    storage_provider text not null default 'supabase_storage',
    storage_key text,
    metadata jsonb not null default '{}'::jsonb,
    extraction_status text not null default 'pending',
    extraction_metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists automation_attachments_tenant_idx
    on public.automation_attachments (tenant_id, created_at);
create index if not exists automation_attachments_job_idx
    on public.automation_attachments (job_id, created_at);

create table if not exists public.automation_document_chunks (
    chunk_id uuid primary key,
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    attachment_id uuid not null references public.automation_attachments(attachment_id) on delete cascade,
    chunk_index integer not null,
    text_content text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (attachment_id, chunk_index)
);

create index if not exists automation_document_chunks_attachment_idx
    on public.automation_document_chunks (attachment_id, chunk_index);

alter table public.automation_attachments enable row level security;
alter table public.automation_document_chunks enable row level security;

create policy if not exists automation_attachments_service_role_all
on public.automation_attachments for all to service_role
using (true) with check (true);
create policy if not exists automation_document_chunks_service_role_all
on public.automation_document_chunks for all to service_role
using (true) with check (true);

create policy if not exists automation_attachments_authenticated_select
on public.automation_attachments for select to authenticated
using (public.is_tenant_member(tenant_id));
create policy if not exists automation_attachments_authenticated_insert
on public.automation_attachments for insert to authenticated
with check (public.is_tenant_member(tenant_id));
create policy if not exists automation_document_chunks_authenticated_select
on public.automation_document_chunks for select to authenticated
using (public.is_tenant_member(tenant_id));
