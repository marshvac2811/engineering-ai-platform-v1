alter table public.engineering_report_artifacts
  add column if not exists evidence_sha256 text,
  add column if not exists pdf_sha256 text,
  add column if not exists pdf_storage_path text,
  add column if not exists pdf_filename text,
  add column if not exists xlsx_sha256 text,
  add column if not exists xlsx_storage_path text,
  add column if not exists xlsx_filename text,
  add column if not exists watermark_text text,
  add column if not exists dispatched_at timestamptz;

insert into storage.buckets (id, name, public)
values ('engineering-artifacts', 'engineering-artifacts', false)
on conflict (id) do nothing;
