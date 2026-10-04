# Engineering AI Platform V1

Commercial SaaS foundation for deterministic HVAC/BMS/energy/commercial engineering skills with AI orchestration, governed assumptions/standards, human review, persistent jobs, tenant security, and provider-neutral dispatch.

## Current integration checkpoint

- 23 skill definitions in the registry.
- 22 executable deterministic skills integrated.
- 1 skill intentionally pending source audit: `chiller_efficiency`.
- Phase 4 checkpoint had 63 automated tests; Phase 5 adds universal compliance/facade coverage and preserves the existing test suite.
- GitHub source repositories are read-only inputs for this build; no source repository is modified by the platform package.

## Integrated skill groups

### HVAC
- `preliminary_load_estimation`
- `duct_sizing`
- `pump_head`
- `hvac_fault_diagnosis`
- `cooling_tower`
- `refrigerant_pipe_sizing`
- `vrf_sizing`
- `cleanroom_ach`
- `duct_leakage`
- `chiller_selection_advisor`

### BMS
- `bms_points_generation`
- `bms_controller_sizing`
- `bms_cost_estimation`
- `bms_alarm_evaluation`

### Energy
- `vfd_energy_savings`
- `vfd_derating`
- `harmonic_screening`
- `hvac_decarbonisation`
- `energy_payback`

### Commercial
- `hvac_boq`
- `deviation_statement`

## Governance principles

1. Deterministic engineering code performs calculations.
2. AI orchestrates requests, gathers missing information, selects skills, explains results, and drafts outputs.
3. Standards and assumptions are governed metadata, not hidden prompt text.
4. Manufacturer-dependent calculations are explicitly classified as preliminary/advisory and require final manufacturer verification.
5. Human review is required before commercial dispatch.
6. Every skill records a source revision for traceability.

## API boundary

A minimal WSGI API now exposes tenant-scoped job intake and lifecycle actions without duplicating engineering logic. See `api/README.md`. In production, tenant identity should come from the authenticated Supabase JWT/claims rather than a client-supplied header.

## Job architecture

`received -> queued -> processing -> input_validation -> engineering_validation -> draft_ready -> human_review -> approved -> dispatching -> dispatched -> completed`

The package includes in-memory and Supabase-compatible job stores, worker locking/heartbeat/release, tenant-aware RLS, audit events, and a provider-neutral dispatch interface.

## Remaining source-audit item

`chiller_efficiency` is intentionally not executable because the audited repository currently does not expose a verified calculation engine. It remains in the registry with `source_audit_pending` status.


## AI provider layer

The orchestrator now includes an optional OpenAI intent/extraction provider behind the same provider-neutral boundary as the deterministic router. Set `ENGINEERING_AI_INTENT_PROVIDER=openai` and `OPENAI_API_KEY` to enable it; otherwise the default remains the auditable rule-based router. The LLM is restricted to intent classification and input extraction. It does not perform engineering calculations.

## Document/file ingestion

The V1 ingestion layer accepts job attachments without mixing extracted document content into deterministic engineering results. Supported source types include PDF, DOCX, XLSX, CSV, text/JSON/XML, DXF metadata, and binary CAD metadata-only registration. Extracted text is chunked for downstream retrieval; scanned PDFs are flagged for OCR instead of being silently processed. Supabase migration `003_attachments_ingestion.sql` adds durable attachment and document-chunk tables.

## Ingestion dependencies

PDF and DOCX extraction use the optional dependencies listed in `requirements-ingestion.txt`. XLSX extraction uses Python standard-library ZIP/XML parsing and does not depend on `openpyxl`.

## Supabase attachment storage

When `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are configured, the API uses the `engineering-attachments` private Supabase Storage bucket for attachment bytes and the `automation_attachments` / `automation_document_chunks` tables for durable metadata and extracted chunks. The bucket is tenant-scoped by the first path segment and authenticated access is constrained by `public.is_tenant_member(...)`.

Optional production dependency: `requirements-supabase.txt`.

## SaaS control plane checkpoint

The API now has an authentication abstraction, local development identity headers, API-key issuance/revocation, tenant usage metering, and role-gated review/dispatch actions. Production should inject a real Supabase JWT verifier instead of trusting development headers.

## Current commercial SaaS checkpoint

- Phase 4 checkpoint had 63 automated tests; Phase 5 adds universal compliance/facade coverage and preserves the existing test suite.
- Authentication abstraction with development headers and API-key authentication.
- API keys are stored as SHA-256 hashes; plaintext secrets are returned only at issuance.
- API-key scopes are enforced for job read/write, approval, dispatch, usage, and key administration.
- Tenant usage events support future billing/plan enforcement.
- Supabase migration `005_saas_control_plane.sql` adds plan/status fields, API keys, usage events, and monthly usage aggregation.

## Production boundary

The production API requires the Supabase-backed job store when ENGINEERING_ENV=production, rejects development tenant headers unless explicitly enabled, and verifies Supabase bearer JWTs on Render. Local/test mode may use in-memory stores for portability. Report artifacts, evidence, revisions, approval metadata and dispatch hashes are persisted through the Supabase report-artifact layer.

The remaining external-service boundary is provider authorization/configuration: Upwork and Gmail must use approved credentials before live operation; Fiverr currently uses notification/normalized-event intake rather than an assumed freelancer API. The platform does not mark an external integration live merely because its adapter exists.

## Governed automatic assumptions

Minor, explicitly registered inputs may be filled by controlled preliminary assumptions when they are not safety/regulatory-critical. Each applied assumption is recorded as ASSUMED_DUE_TO_CLIENT_DATA_UNAVAILABLE, disclosed for human review, and retained in the evidence chain. Inputs not registered for automatic assumption remain blocking requirements.


## CRM / Sales Pipeline

The platform now includes a canonical internal MEP CRM model based on the existing `pipeline` repository. The preserved pipeline stages are Budgetary, Tendering, Quotation, Follow-Up, Negotiation, Closed — Won, and Closed — Lost, with Project Sales, Retrofit Jobs, and Energy Optimization categories. The CRM can link a deal to an engineering job and prepare a HubSpot outbound payload.

## External integration layer

The current checkpoint also contains a provider-neutral external integration
layer for Gmail, Upwork, Fiverr and Gumroad plus HubSpot. Integration events are
normalized before entering the orchestrator, and duplicate external events are
suppressed. Migration `007_integrations.sql` adds durable connection/event tables.
The trial can therefore be run end-to-end with live or notification/import based
inputs; direct Fiverr freelancer API access is intentionally not assumed until
Fiverr publishes the required API surface.

## Gmail live trial boundary

The V1 package now includes a stdlib-only Gmail OAuth/API client for the first live trial. It supports OAuth start/callback, short-lived OAuth state, refresh-token reuse, message polling with Gmail query syntax, message normalization across nested MIME parts, and attachment download into the existing ingestion service. The trial token store is file-backed only to make a single-tenant staging test runnable without adding a new dependency; it is not the production credential store.


## Universal engineering calculation and compliance layer — Phase 5

The platform now has a shared `code_engine` for governed code documents, structured
requirements, applicability and compliance checks. Engineering skills can consume
this layer without embedding code values in prompts.

The first integrated vertical is `facade_u_factor`. It calculates a preliminary
area-weighted U-factor from component/system inputs and emits a structured
compliance record containing authority, edition, clause, requirement, project
value, required value and PASS/FAIL/NOT_APPLICABLE/NOT_VERIFIABLE status.

The initial standards metadata includes BIS NBC 2016, BEE ECBC 2017 and ASHRAE
90.1-2025. The registry stores metadata and structured requirements rather than
reproducing copyrighted standards. Applicability is project-specific; a listed
standard is not automatically treated as mandatory for every project.

This is the first vertical of the universal engine, not the final coverage set.
Additional HVAC, facade, electrical, plumbing, fire/life-safety, structural and
construction requirements should be added through the same registry/skill
contract as their authoritative source and applicability are verified.


## Universal engineering planning
The platform now separates AI request interpretation from engineering execution: compound requests can be decomposed into ordered tasks, each mapped internally to a registered capability or explicitly marked as requiring a capability. Numerical engineering work remains outside the AI interpretation layer and subject to human review.


## Deployment verification

The production deployment must correspond to the latest tested `main` commit before end-to-end audit and dispatch trials.
