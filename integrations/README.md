# External Integrations

The platform uses one provider-neutral integration boundary so Gmail, Upwork,
Fiverr and Gumroad events enter the same engineering/CRM workflow without
embedding provider-specific logic inside deterministic engineering skills.

## Trial model

- **Gmail:** OAuth connection; read inbound engineering-request mail and later send approved results.
- **Upwork:** OAuth/API adapter; intake proposals/messages/attachments where the approved API scopes permit it.
- **Fiverr:** notification/import adapter for the trial. The current Fiverr platform API page states API integration is "COMING SOON", so direct freelancer inbox automation is not assumed until Fiverr exposes a supported API.
- **Gumroad:** API/webhook adapter for sales/subscription/customer events; useful for trial-plan/product/customer lifecycle signals.
- **HubSpot:** remains the external CRM sync adapter for the canonical internal CRM.

## Normalized flow

`provider event -> integration event -> intake/orchestrator -> automation job -> deterministic skill -> human review -> dispatch`

All inbound external events are de-duplicated by `(tenant_id, provider, external_event_id)`.

## Security

OAuth refresh tokens, API keys, and provider secrets must be stored outside source
control, in the production secret store. The local implementation contains no
real credentials.

## Gmail live trial endpoints

- `GET /v1/integrations/gmail/oauth/start` — authenticated admin starts Google OAuth. Optional query parameter: `login_hint`.
- `GET /v1/integrations/gmail/oauth/callback` — Google redirects here with `code` and `state`; state binds the callback to the tenant.
- `POST /v1/integrations/gmail/sync` — polls Gmail for matching messages, normalizes each message, deduplicates it, creates an engineering job, and optionally downloads attachments into the existing ingestion layer.

The trial uses `gmail.readonly`, so the first phase does not mark messages read and does not send mail. This keeps the test reversible and limits the scope. Google documents offline web-server OAuth with a refresh token and Gmail message listing/filtering through `messages.list`. See the Google Gmail OAuth and messages-list documentation for the current provider requirements.

The local trial token store is deliberately replaceable. Before commercial production, move refresh-token storage to encrypted tenant-scoped persistence/secret management and use a verified authenticated tenant context rather than development headers.
