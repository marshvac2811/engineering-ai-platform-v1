# Engineering AI Platform V1

Private production repository for the Engineering & Operations Automation Platform.

## Current V1 baseline

The local V1 implementation has completed Phases 1–18 and commissioning, including:

- universal engineering skills and registry
- engineering job lifecycle and validation
- human review and approval
- universal standards/compliance architecture
- governed HVAC, facade, electrical, BMS, energy, plumbing and construction requirements
- client-ready engineering reports and evidence
- structured drawing model
- Upwork/Gmail/Fiverr workflow task layer
- production hardening and synthetic end-to-end commissioning

## Repository policy

- `main` = stable production baseline
- `trial/dashboard-v1` = 7–10 day trial/integration work
- Do not commit secrets, `.env` files, virtual environments, caches, generated reports, or credentials.
- Existing local V1 architecture remains authoritative; changes should be incremental and tested.

## Deployment direction

Local development → GitHub trial branch → Vercel Preview → user trial/observations → fixes → repeat → production only after stability.
