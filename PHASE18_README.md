# Phase 18 — Production Hardening, Controlled Trial & Launch Readiness

Phase 18 is the final planned Engineering AI Platform V1 phase.

## Purpose

Harden the V1 boundary for real client work without replacing the authoritative JobService/orchestrator or inventing a live Upwork connection.

## Added

- `production/readiness.py`: deterministic launch/readiness gate.
- `production/trial.py`: controlled Upwork-style intake trial using in-memory stores.
- `tests/test_phase18_launch_readiness.py`: production-gate regression tests.

## Safety rules

- No OAuth secrets or token values are printed by readiness checks.
- Missing Upwork credentials produce a warning for local development and a blocking result when a live Upwork configuration is explicitly required.
- The platform does not claim Upwork production authorization or webhook approval.
- The controlled trial uses synthetic data only.

## Upwork production condition

Before enabling a real Upwork connection, obtain the required Upwork API credentials/approval for the intended use case and configure the callback securely. Upwork states that unauthorized automation can lead to account restrictions and that API access must remain within the approved use case.

## V1 definition of done

The planned V1 engineering workflow is complete when:

1. A client request can enter as a business Workflow Task.
2. Requirements can move through the governed task state machine.
3. A task can link to the existing Engineering Job execution layer.
4. Engineering results can pass through standards/compliance and reporting layers.
5. Structured drawing geometry is available as a source of truth.
6. Human review remains a delivery gate.
7. A controlled synthetic trial passes.
8. Live external integrations are enabled only after their provider authorization/configuration is actually available.

This phase deliberately does not mark an unconfigured external integration as "live".

## Verification in the existing project environment

Run the normal project test command from the repository root with the existing `.env`/environment loaded. Phase 18 itself has three focused tests and all three pass in the package build environment.

A clean environment without `SUPABASE_URL` cannot import the API test suite; this is an environment/configuration condition, not a code-pass claim.
