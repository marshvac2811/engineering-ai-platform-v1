from __future__ import annotations

from pathlib import Path
from typing import Any

from skill_framework.registry import load_skill_registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "skill_registry" / "registry.yaml"

CONTRACT_SECTIONS = (
    "required_inputs",
    "optional_inputs",
    "conditional_inputs",
    "standards",
    "assumptions",
    "validation_rules",
    "warning_rules",
    "perfection_filter_rules",
    "output_fields",
    "audit_fields",
)


def _count(value: Any) -> int:
    return len(value) if isinstance(value, (list, tuple, dict, set)) else 0


def build_contract_report():
    registry = load_skill_registry(REGISTRY)

    rows = []

    for skill_id in registry.skill_ids:
        skill = registry.get(skill_id)

        rows.append(
            {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "domain": skill.domain,
                "executable": skill.executable,
                "execution_type": skill.execution_type,
                "implementation_binding": bool(skill.implementation_binding),
                "required_inputs": _count(skill.required_inputs),
                "optional_inputs": _count(skill.optional_inputs),
                "conditional_inputs": _count(skill.conditional_inputs),
                "standards": _count(skill.standards),
                "assumptions": _count(skill.assumptions),
                "validation_rules": _count(skill.validation_rules),
                "warning_rules": _count(skill.warning_rules),
                "perfection_filter_rules": _count(skill.perfection_filter_rules),
                "review_required": bool(skill.review.required),
                "output_fields": _count(skill.output_fields),
                "audit_fields": _count(skill.audit_fields),
                "source_revision": bool(skill.source_revision),
            }
        )

    return registry, rows


def test_all_registry_skills_load_as_skill_definitions():
    registry, rows = build_contract_report()

    assert len(rows) == 22
    assert all(row["skill_id"] for row in rows)
    assert all(row["name"] for row in rows)
    assert all(row["domain"] for row in rows)
    assert all(row["execution_type"] for row in rows)


def test_registry_executable_boundary_is_preserved():
    registry, rows = build_contract_report()

    executable = [row for row in rows if row["executable"]]
    pending = [row for row in rows if not row["executable"]]

    assert len(executable) == 21
    assert len(pending) == 1
    assert pending[0]["skill_id"] == "chiller_efficiency"


def test_no_executable_skill_is_missing_an_implementation_binding():
    registry, rows = build_contract_report()

    missing = [
        row["skill_id"]
        for row in rows
        if row["executable"] and not row["implementation_binding"]
    ]

    assert missing == []


def test_contract_sections_are_machine_readable():
    registry = load_skill_registry(REGISTRY)

    for skill_id in registry.skill_ids:
        skill = registry.get(skill_id)

        for section in CONTRACT_SECTIONS:
            value = getattr(skill, section)
            assert isinstance(
                value,
                list,
            ), f"{skill_id}.{section} must be a list"


def test_pending_skill_remains_non_executable():
    registry = load_skill_registry(REGISTRY)

    skill = registry.get("chiller_efficiency")

    assert skill.executable is False
    assert registry.entries[skill.skill_id].raw["integration_status"] == (
        "source_audit_pending"
    )
