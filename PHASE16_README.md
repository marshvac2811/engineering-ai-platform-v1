# Phase 16 — Structured Engineering Drawing Model

Adds a CAD-neutral, deterministic geometry model:
- points
- lines/layers
- dimensions
- drawing metadata
- geometry validation
- deterministic JSON serialization
- parametric facade elevation example

This phase deliberately does not claim DWG/DXF generation. Downstream renderers
can consume the validated model. Geometry is the source of truth, allowing
drawings to be regenerated when engineering inputs change.
