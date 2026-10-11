-- Job / report serial numbers: YYYYMMDDHHMM (IST) + 5-digit running counter, e.g. 20261010201000001.
alter table public.automation_jobs add column if not exists serial_no text;
create unique index if not exists automation_jobs_serial_no_key on public.automation_jobs (serial_no) where serial_no is not null;

create sequence if not exists public.job_serial_seq as bigint minvalue 1 start 1;

create or replace function public.next_job_serial()
returns text
language sql
security definer
set search_path = public
as $$
  select to_char(now() at time zone 'Asia/Kolkata', 'YYYYMMDDHH24MI') || lpad(nextval('public.job_serial_seq')::text, 5, '0');
$$;

revoke all on function public.next_job_serial() from public, anon, authenticated;
grant execute on function public.next_job_serial() to service_role;
