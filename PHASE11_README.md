# Phase 11 — Governed Standards Scope Library

Phase 11 adds a governed, auditable standards-scope layer across the executable engineering skills.

## What changed

- Added `standards/scope_registry.yaml` with authoritative scope references for:
  - BIS NBC 2016
  - BEE ECBC 2017
  - ASHRAE 55-2023
  - ASHRAE 62.1-2025
  - ASHRAE 90.1-2025
- Added `code_engine/scope.py` to map executable skills to relevant standards scope references.
- Added coverage audit so every executable skill has at least one governed scope reference.
- Added `standards_scope_references` to the common report envelope.
- Scope references are explicitly marked `SCOPE_REFERENCE` and cannot create PASS/FAIL results.
- Existing structured requirements in `standards/registry.yaml` remain the only source for compliance PASS/FAIL.

## Boundary

This phase does not reproduce copyrighted standards and does not claim that every referenced standard is legally mandatory. Applicability remains project/jurisdiction/contract dependent.
