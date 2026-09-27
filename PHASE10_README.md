# Phase 10 — Registry-Driven Universal Compliance Execution

## Purpose
Phase 9 established standards applicability candidates. Phase 10 removes the next source of duplication: compliance rules should not have to be embedded in every engineering skill.

## What changed
- Added `code_engine/universal.py`.
- Loads governed requirements from the existing `standards/registry.yaml` through `CodeRegistry`.
- Evaluates simple, auditable applicability predicates from project context.
- Finds requirements by discipline + parameter.
- Executes registered requirements through the existing `ComplianceEngine`.
- Produces a single compliance gate: `COMPLIANT`, `NON_COMPLIANT`, `NOT_VERIFIABLE`, `NOT_APPLICABLE`, `NO_GOVERNED_REQUIREMENT`, or `REVIEW_REQUIRED`.
- No requirement means no invented PASS/FAIL result.

## Architecture
Skill calculator -> engineering value -> universal compliance executor -> governed requirement -> clause/evidence -> report.

The calculator remains responsible for engineering mathematics. The standards registry remains responsible for governed requirements. This separation lets additional standards/clauses be added without rewriting the calculators.

## Current governed executable requirement
The existing ECBC 2017 vertical-fenestration U-factor requirement remains the representative end-to-end governed check. Other standards remain metadata/candidate references until their authorized structured requirements are loaded.
