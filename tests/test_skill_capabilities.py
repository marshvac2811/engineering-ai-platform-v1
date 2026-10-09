from pathlib import Path
from skill_registry.capabilities import CAPABILITY_CATALOG, executable_skill_ids
from skill_framework.registry import load_skill_registry
from skill_framework.implementation_bindings import binding_map
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "skill_registry" / "registry.yaml"
def test_catalog_matches_registry_and_bindings():
    registry = load_skill_registry(REGISTRY); bindings = binding_map()
    assert len(registry.executable_ids) == 25
    assert set(CAPABILITY_CATALOG) == set(registry.executable_ids)
    assert set(CAPABILITY_CATALOG) == set(bindings)
    assert "chiller_efficiency" not in CAPABILITY_CATALOG
def test_capability_inputs_match_registry():
    registry = load_skill_registry(REGISTRY)
    for sid, cap in CAPABILITY_CATALOG.items():
        d=registry.get(sid)
        assert cap.required_inputs == tuple(i.name for i in d.required_inputs)
        assert cap.optional_inputs == tuple(i.name for i in d.optional_inputs)
        assert cap.conditional_inputs == tuple(i.name for i in d.conditional_inputs)
        assert cap.implementation.skill_id == sid
def test_every_executable_capability_has_routing_terms():
    assert executable_skill_ids() == sorted(CAPABILITY_CATALOG)
    assert all(CAPABILITY_CATALOG[s].routing_terms for s in CAPABILITY_CATALOG)
