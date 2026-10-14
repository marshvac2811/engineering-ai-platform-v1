-- Delivery, revision, final-submission and payment tracking on CRM deals (additive; one JSON record per deal).
alter table public.crm_deals
    add column if not exists delivery jsonb not null default '{}'::jsonb;
