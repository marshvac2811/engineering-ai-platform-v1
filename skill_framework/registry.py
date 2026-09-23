from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

from .skill_definition import SkillDefinition, definition_from_dict, validate_definition_dict


class RegistryValidationError(ValueError):
    """Raised when the authoritative skill registry is invalid."""


@dataclass(frozen=True)
class RegistryEntry:
    definition: SkillDefinition
    raw: dict


@dataclass(frozen=True)
class SkillRegistry:
    version: int
    status: str
    entries: Dict[str, RegistryEntry]

    @property
    def skill_ids(self) -> List[str]:
        return sorted(self.entries)

    @property
    def executable_ids(self) -> List[str]:
        return sorted(
            skill_id
            for skill_id, entry in self.entries.items()
            if entry.definition.executable
        )

    @property
    def pending_ids(self) -> List[str]:
        return sorted(
            skill_id
            for skill_id, entry in self.entries.items()
            if not entry.definition.executable
        )

    def get(self, skill_id: str) -> SkillDefinition:
        try:
            return self.entries[skill_id].definition
        except KeyError as exc:
            raise KeyError(f"Skill is not registered: {skill_id}") from exc


def _validate_top_level(data: dict) -> None:
    if not isinstance(data, dict):
        raise RegistryValidationError("Registry root must be an object.")

    if "version" not in data:
        raise RegistryValidationError("Registry requires 'version'.")

    if "skills" not in data:
        raise RegistryValidationError("Registry requires 'skills'.")

    if not isinstance(data["skills"], list):
        raise RegistryValidationError("Registry 'skills' must be a list.")


def _display_name(raw: dict) -> str:
    if raw.get("name"):
        return str(raw["name"])

    return str(raw["skill_id"]).replace("_", " ").strip().title()


def _purpose(raw: dict) -> str:
    if raw.get("purpose"):
        return str(raw["purpose"])

    return (
        "Engineering workflow for "
        + str(raw["skill_id"]).replace("_", " ")
        + "."
    )


def _executable_status(raw: dict) -> bool:
    """
    Preserve an explicit executable flag when present.

    For the existing authoritative registry format, integration_status is
    the source of executable status:
        integrated -> executable
        source_audit_pending -> pending

    Unknown non-integrated statuses remain non-executable rather than being
    assumed executable.
    """
    if "executable" in raw:
        return bool(raw["executable"])

    return str(raw.get("integration_status", "")).strip().lower() == "integrated"


def _definition_payload(raw: dict) -> dict:
    """
    Adapt the existing registry representation to SkillDefinition.

    This mapper does not invent engineering calculations, standards,
    assumptions, input requirements, or engineering constants.
    """
    payload = dict(raw)

    payload["name"] = _display_name(raw)
    payload["purpose"] = _purpose(raw)

    payload.setdefault("version", str(raw.get("version", "1")))
    payload.setdefault("classification", raw.get("classification", "pending"))
    payload.setdefault(
        "integration_status",
        raw.get("integration_status", "registry_only"),
    )
    payload["executable"] = _executable_status(raw)

    payload.setdefault(
        "execution_type",
        raw.get("execution_type", "deterministic_calculation"),
    )
    payload.setdefault(
        "implementation_binding",
        raw.get("implementation_binding", ""),
    )

    payload.setdefault("required_inputs", [])
    payload.setdefault("optional_inputs", [])
    payload.setdefault("conditional_inputs", [])
    payload.setdefault("standards", [])
    payload.setdefault("assumptions", [])
    payload.setdefault("validation_rules", [])
    payload.setdefault("warning_rules", [])
    payload.setdefault("perfection_filter_rules", [])

    payload.setdefault(
        "review",
        {
            "required": bool(raw.get("human_review_required", False)),
            "roles": [],
            "conditions": [],
        },
    )

    payload.setdefault("output_fields", [])
    payload.setdefault("audit_fields", [])
    payload.setdefault("source_revision", raw.get("source_revision", ""))

    return payload


def load_skill_registry(path: str | Path) -> SkillRegistry:
    registry_path = Path(path)

    if not registry_path.exists():
        raise RegistryValidationError(
            f"Skill registry file not found: {registry_path}"
        )

    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RegistryValidationError(
            f"Invalid YAML in skill registry: {exc}"
        ) from exc

    _validate_top_level(data)

    entries: Dict[str, RegistryEntry] = {}

    for index, raw in enumerate(data["skills"]):
        if not isinstance(raw, dict):
            raise RegistryValidationError(
                f"Registry skill entry {index} must be an object."
            )

        payload = _definition_payload(raw)
        errors = validate_definition_dict(payload)

        if errors:
            raise RegistryValidationError(
                f"Invalid definition for registry entry {index}: "
                + "; ".join(errors)
            )

        skill_id = payload["skill_id"]

        if skill_id in entries:
            raise RegistryValidationError(
                f"Duplicate skill_id in registry: {skill_id}"
            )

        definition = definition_from_dict(payload)

        entries[skill_id] = RegistryEntry(
            definition=definition,
            raw=raw,
        )

    return SkillRegistry(
        version=int(data["version"]),
        status=str(data.get("status", "")),
        entries=entries,
    )

