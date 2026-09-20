-- Private Supabase Storage bucket for job attachments.
-- Files are tenant-scoped by the first path segment: <tenant_id>/<job_id>/...

insert into storage.buckets (id, name, public, file_size_limit)
values ('engineering-attachments', 'engineering-attachments', false, 52428800)
on conflict (id) do nothing;

drop policy if exists engineering_attachments_authenticated_select on storage.objects;
create policy engineering_attachments_authenticated_select
on storage.objects for select to authenticated
using (
    bucket_id = 'engineering-attachments'
    and public.is_tenant_member(((storage.foldername(name))[1])::uuid)
);

drop policy if exists engineering_attachments_authenticated_insert on storage.objects;
create policy engineering_attachments_authenticated_insert
on storage.objects for insert to authenticated
with check (
    bucket_id = 'engineering-attachments'
    and public.is_tenant_member(((storage.foldername(name))[1])::uuid)
);

-- Client-side update/delete are intentionally not enabled in V1.
-- Trusted server-side ingestion uses the Supabase service key and remains
-- subject to application-level tenant checks.
