from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_orchestrator_binding_inventory_matches_compatibility_layer():
    from orchestrator.engine import registered_skills
    from skill_framework.registry import load_skill_registry
    from skill_framework.implementation_bindings import binding_map

    registry = load_skill_registry(ROOT / "skill_registry" / "registry.yaml")
    bindings = binding_map()

    assert set(registry.executable_ids) == set(registered_skills())
    assert set(registry.executable_ids) == set(bindings)


def test_orchestrator_contains_all_compatibility_classes():
    from orchestrator.engine import SKILLS
    from skill_framework.registry import load_skill_registry
    from skill_framework.implementation_bindings import binding_map

    registry = load_skill_registry(ROOT / "skill_registry" / "registry.yaml")
    bindings = binding_map()

    assert set(SKILLS) == set(registry.executable_ids)

    for skill_id in registry.executable_ids:
        binding = bindings[skill_id]
        skill = SKILLS[skill_id]
        assert skill.__class__.__name__ == binding.implementation_class
        assert skill.__class__.__module__ == binding.implementation_path


def test_orchestrator_skill_ids_match_registry_executable_ids():
    from orchestrator.engine import registered_skills
    from skill_framework.registry import load_skill_registry

    registry = load_skill_registry(ROOT / "skill_registry" / "registry.yaml")

    assert set(registered_skills()) == set(registry.executable_ids)
    assert "chiller_efficiency" not in registered_skills()
