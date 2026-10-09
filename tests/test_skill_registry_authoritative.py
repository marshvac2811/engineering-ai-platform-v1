from pathlib import Path

import pytest

from skill_framework.registry import (
    RegistryValidationError,
    load_skill_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "skill_registry" / "registry.yaml"


def test_authoritative_registry_loads_expected_inventory():
    registry = load_skill_registry(REGISTRY)

    assert len(registry.skill_ids) == 26
    assert len(registry.executable_ids) == 25
    assert registry.pending_ids == ["chiller_efficiency"]
    assert registry.skill_ids == sorted(registry.skill_ids)


def test_authoritative_registry_has_expected_pending_skill():
    registry = load_skill_registry(REGISTRY)

    skill = registry.get("chiller_efficiency")

    assert skill.skill_id == "chiller_efficiency"
    assert skill.executable is False
    assert skill.integration_status == "source_audit_pending"


def test_authoritative_registry_has_no_duplicate_ids(tmp_path):
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        """version: 1
status: test
skills:
  - skill_id: duplicate
    domain: TEST
  - skill_id: duplicate
    domain: TEST
""",
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="Duplicate skill_id"):
        load_skill_registry(duplicate)


def test_malformed_definition_is_rejected(tmp_path):
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text(
        """version: 1
status: test
skills:
  - name: Bad
    domain: TEST
    purpose: Missing skill id
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_skill_registry(malformed)


def test_existing_registry_metadata_is_preserved():
    registry = load_skill_registry(REGISTRY)

    skill = registry.get("preliminary_load_estimation")

    assert skill.skill_id == "preliminary_load_estimation"
    assert skill.domain == "HVAC"
    assert skill.name == "Preliminary Load Estimation"
    assert skill.purpose


def test_integrated_status_maps_to_executable():
    registry = load_skill_registry(REGISTRY)

    integrated = [
        entry.definition
        for entry in registry.entries.values()
        if entry.raw.get("integration_status") == "integrated"
    ]

    assert len(integrated) == 25
    assert all(skill.executable for skill in integrated)


def test_pending_status_does_not_map_to_executable():
    registry = load_skill_registry(REGISTRY)

    pending = registry.get("chiller_efficiency")

    assert registry.entries["chiller_efficiency"].raw["integration_status"] == "source_audit_pending"
    assert pending.executable is False


