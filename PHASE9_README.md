# Phase 9 — Universal Standards Applicability Layer

## Purpose
Phase 9 adds the missing universal standards-selection layer above the existing Phase 8 report adapters. It does **not** rewrite engineering calculators and does **not** invent code requirements.

## What changed
- Added `code_engine/coverage.py`.
- Every executable skill now has a governed standards-coverage mapping.
- Candidate standards are explicitly separated from verified compliance requirements.
- Reports now contain `standards_applicability` and a `compliance_gate`.
- Missing project context produces `CONTEXT_REQUIRED` instead of an automatic compliance conclusion.
- Added metadata for ASHRAE 55-2023 and ASHRAE 62.1-2025 to the standards registry.

## Compliance rule
A standards reference is **not** a compliance result. A PASS/FAIL result requires:
1. a structured requirement in `standards/registry.yaml`, and
2. project applicability established by the applicability context.

If either is missing, the platform must not manufacture a requirement.

## Current coverage
- NBC 2016: building/services/glazing reference across applicable skills.
- BEE ECBC 2017: commercial energy/building-envelope reference where applicable.
- ASHRAE 55-2023: thermal-comfort reference candidate.
- ASHRAE 62.1-2025: ventilation/IAQ reference candidate.
- ASHRAE 90.1-2025: energy-performance reference where applicable.

## Verification
Full regression: **106 passed, 1 warning**.

The warning is the existing Uvicorn WSGI deprecation warning and is unrelated to Phase 9 functionality.
