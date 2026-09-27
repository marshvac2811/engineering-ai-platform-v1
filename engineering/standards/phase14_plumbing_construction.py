"""Phase 14 governed requirement metadata for plumbing and construction.

These entries are scope/traceability records, not universal legal conclusions.
Structured PASS/FAIL evaluation must only occur when the applicable requirement
and project context are explicitly established in the governed registry.
"""

PHASE14_REQUIREMENTS = [
    {
        "id": "NBC2016-P9-WATER-SUPPLY-DESIGN",
        "discipline": "plumbing",
        "standard": "NBC 2016",
        "clause": "Part 9, Section 1",
        "title": "Water supply",
        "type": "scope_reference",
        "verification": "Requires project-specific water-demand, fixture, storage and pressure inputs plus applicable local requirements.",
    },
    {
        "id": "NBC2016-P9-DRAINAGE-SANITATION",
        "discipline": "plumbing",
        "standard": "NBC 2016",
        "clause": "Part 9, Section 2",
        "title": "Drainage and sanitation",
        "type": "scope_reference",
        "verification": "Requires project-specific fixture discharge, drainage layout, gradients, pipe sizing and applicable authority requirements.",
    },
    {
        "id": "NBC2016-P9-SOLID-WASTE",
        "discipline": "plumbing",
        "standard": "NBC 2016",
        "clause": "Part 9, Section 3",
        "title": "Solid waste management",
        "type": "scope_reference",
        "verification": "Requires occupancy, waste generation, segregation and building/site management inputs.",
    },
    {
        "id": "NBC2016-P9-GAS-SUPPLY",
        "discipline": "plumbing",
        "standard": "NBC 2016",
        "clause": "Part 9, Section 4",
        "title": "Gas supply",
        "type": "scope_reference",
        "verification": "Requires gas type, demand, pressure, routing and applicable authority/safety requirements.",
    },
    {
        "id": "NBC2016-P6-LOADS",
        "discipline": "structural",
        "standard": "NBC 2016",
        "clause": "Part 6, Section 1",
        "title": "Loads, forces and effects",
        "type": "scope_reference",
        "verification": "Requires occupancy/use, geometry, location and governing load cases; local adoption and project design basis must be established.",
    },
    {
        "id": "NBC2016-P6-SOIL-FOUNDATION",
        "discipline": "structural",
        "standard": "NBC 2016",
        "clause": "Part 6, Section 2",
        "title": "Soils and foundations",
        "type": "scope_reference",
        "verification": "Requires geotechnical investigation/design inputs and the applicable foundation design basis.",
    },
    {
        "id": "NBC2016-P7-CONSTRUCTION-SAFETY",
        "discipline": "construction",
        "standard": "NBC 2016",
        "clause": "Part 7",
        "title": "Construction management, practices and safety",
        "type": "scope_reference",
        "verification": "Requires project execution method, site conditions, sequencing, safety controls and applicable authority requirements.",
    },
]

def phase14_requirements():
    return list(PHASE14_REQUIREMENTS)
