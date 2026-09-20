# HTTP API

The API is provider-neutral and tenant-scoped.

## Local development authentication

Use:

- `X-Tenant-ID`
- `X-User-ID`
- `X-User-Role` (`owner`, `admin`, `engineer`, `reviewer`, `member`)

Production should replace the development authenticator with a verifier that validates a Supabase Auth JWT before creating the `AuthContext`.

## API keys

Owners/admins can create an API key through `POST /v1/api-keys`. The plaintext secret is returned exactly once. Only its hash is stored.

## Usage

Every API request may be metered as `api_request`; engineering execution may be metered as `skill_execution`. The SQL migration exposes `tenant_usage_monthly` for billing/plan enforcement.
