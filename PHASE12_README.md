# Phase 12 — Auditable HVAC + Facade Requirement Packs

Phase 12 adds the first expanded set of structured, clause-backed engineering requirements to the governed standards registry. It does not reproduce copyrighted standards.

## Added governed requirements

### BEE ECBC 2017 — HVAC
- Water-cooled chiller minimum COP, ECBC level, capacity bands:
  - <260 kWr: 4.7
  - >=260 and <530 kWr: 4.9
  - >=530 and <1,050 kWr: 5.4
  - >=1,050 and <1,580 kWr: 5.8
  - >=1,580 kWr: 6.3
- Air-cooled chiller minimum COP:
  - <260 kWr: 2.8
  - >=260 kWr: 3.0
- Unitary/split/packaged air-conditioner EER above 10.5 kWr:
  - water-cooled: 3.3
  - air-cooled: 2.8

All are mapped to ECBC 2017 §5.2.2.1 / Table 5-1, §5.2.2.1 / Table 5-2, and §5.2.2.2 / Table 5-3 respectively.

### Facade
The existing ECBC 2017 vertical fenestration U-factor requirement remains governed at §4.3.3 / Table 4-10.

## Important behavior

The universal compliance executor now evaluates only requirements whose applicability predicates are established. Non-applicable requirements are not emitted as false compliance checks. If no governed requirement is applicable, the gate remains `NO_GOVERNED_REQUIREMENT`.

This prevents unrelated capacity bands or missing project context from being reported as `NOT_APPLICABLE` compliance rows for a calculation that has not established the relevant code pathway.

## Verification

115 tests passed, 1 existing Uvicorn WSGI deprecation warning.

Test-only Supabase environment was used for the deterministic suite; no production `.env` values were changed.
