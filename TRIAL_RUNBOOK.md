# External-Service Trial Runbook

## What the trial proves

1. A real external request/notification enters the platform.
2. The integration layer normalizes it.
3. The AI intake layer classifies/extracts the request.
4. A deterministic engineering job is created.
5. Attachments can enter the existing ingestion pipeline.
6. Engineering calculations remain deterministic and auditable.
7. A human reviews before dispatch.

## Gmail

Use Gmail as the first live ingress because the Gmail API supports OAuth and message listing/filtering. Start with the narrowest read scope needed for the trial. Add send scope only when approved outbound dispatch is tested. Google identifies Gmail read scopes as sensitive/restricted depending on the exact scope and notes that broader public use can require verification.

Trial message examples:

- Subject: `Load Calculation Request`
- Subject: `Duct Sizing Request`
- Subject: `Project Spec - HVAC`
- Subject: `Optimization Request`

Attach a PDF/XLSX/DOCX or CAD file.

## Upwork

The adapter is ready for OAuth/API intake. Live access depends on obtaining an Upwork API key/application approval. Current Upwork documentation says API access is available for personal/internal use and lists account eligibility requirements; it also states there is no sandbox/test account. Therefore the trial should use the adapter with approved live credentials, or the normalized-event test harness until approval exists.

## Fiverr

For the trial, route Fiverr order/message notification emails into the Gmail intake mailbox, or submit normalized Fiverr events directly to the integration endpoint. Fiverr's current platform-solutions page says its API integration is `COMING SOON`, so the platform does not pretend a freelancer inbox API exists today.

## Gumroad

Connect Gumroad for sales/subscription/customer lifecycle events. These events are recorded as integration events and can later feed plan entitlement, CRM, onboarding, or customer workflows. Do not convert a Gumroad sale into an engineering job unless the event actually carries an engineering request.

## Trial sequence

**Trial A — Gmail -> Engineering**

Send one real engineering-request email with an attachment. Confirm:
`email -> normalized event -> job -> attachment ingestion -> deterministic calculation -> draft -> human review`

**Trial B — Upwork/Fiverr -> Engineering**

Use a real approved Upwork event or a Fiverr notification email. Confirm that the normalized message enters exactly the same intake/job path as Gmail.

**Trial C — Gumroad -> CRM/commerce**

Create a test sale/subscription event and confirm the event is recorded and deduplicated without creating a false engineering job.

## Production security

Do not place provider secrets or refresh tokens in source control. For production, store secrets in the deployment secret manager and store OAuth tokens encrypted at rest with tenant isolation. Replace the simple trial webhook secret with provider-supported webhook verification where available.


## Live Gmail trial setup

1. In Google Cloud, enable Gmail API and create a Web application OAuth client. Add the exact `GMAIL_REDIRECT_URI` to the OAuth client's authorized redirect URIs.
2. Configure `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REDIRECT_URI`, and `GMAIL_TOKEN_DIR` outside source control.
3. Start the API and call `GET /v1/integrations/gmail/oauth/start` as a tenant admin. Open the returned `authorization_url` in a browser and complete Google consent.
4. Google redirects to `/v1/integrations/gmail/oauth/callback`, which stores the trial credential and registers the Gmail connection for the tenant.
5. Send a fresh Gmail message to the connected account with a subject such as `Load Calculation Request` and attach a PDF/XLSX/DOCX or CAD file.
6. Call `POST /v1/integrations/gmail/sync` with `download_attachments=true`.
7. Verify the response contains a normalized Gmail event, a created engineering job, and downloaded attachments. Then use the existing job `enqueue`, `process`, `report`, `approve`, and `dispatch` lifecycle.

Google's current web-server OAuth guidance recommends offline access for refresh tokens and server-side storage of those tokens. Gmail's current API supports message search with Gmail query syntax via `messages.list`; attachments can be retrieved with the Gmail attachment endpoint.

### Important Google trial-mode note
If the Google OAuth consent screen is left in `Testing` publishing status, Google currently limits the project to up to 100 test users and authorizations for test users expire after 7 days; refresh tokens issued for those authorizations also expire. This is acceptable for the first trial, but production rollout needs the appropriate publishing/verification path.
