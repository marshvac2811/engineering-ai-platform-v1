-- Encrypted OAuth tokens for integrations. Ciphertext only (Fernet); written by the service role.
create table if not exists public.integration_tokens (
    tenant_id uuid not null references public.app_tenants(tenant_id) on delete cascade,
    provider text not null,
    token_encrypted text not null,
    updated_at timestamptz not null default now(),
    primary key (tenant_id, provider)
);

-- Row level security on with no policies: only the service role (which bypasses RLS) can read or write.
alter table public.integration_tokens enable row level security;
