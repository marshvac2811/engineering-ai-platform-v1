"""Validation and resolution helpers for governed assumptions and standards."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSUMPTIONS_PATH = ROOT / "assumptions" / "registry.yaml"
STANDARDS_PATH = ROOT / "standards" / "registry.yaml"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_assumption_registry() -> dict:
    return _load_yaml(ASSUMPTIONS_PATH)


def load_standard_registry() -> dict:
    return _load_yaml(STANDARDS_PATH)


def resolve_assumption(
    assumption_id: str,
    *,
    override_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    override_context = override_context or {}
    if assumption_id in override_context:
        value = override_context[assumption_id]
        return {
            "assumption_id": assumption_id,
            "value": value,
            "source": "project_override",
            "override": True,
        }

    for item in load_assumption_registry().get("assumptions", []):
        if item.get("assumption_id") == assumption_id:
            resolved = dict(item)
            resolved["source"] = item.get("provenance", "registry")
            resolved["override"] = False
            return resolved

    return {
        "assumption_id": assumption_id,
        "source": "unresolved",
        "override": False,
        "status": "not_registered",
    }


def resolve_standards_context(context: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Return caller-supplied governed standards context without inventing values."""
    context = context or {}
    standards = context.get("standards", [])
    if standards is None:
        return []
    if not isinstance(standards, list):
        raise TypeError("standards_context['standards'] must be a list")
    return [dict(item) if isinstance(item, dict) else {"value": item} for item in standards]


def validate_governance_context(request) -> List[str]:
    errors: List[str] = []
    if not isinstance(request.assumptions_context, dict):
        errors.append("assumptions_context must be an object/dict")
    if not isinstance(request.standards_context, dict):
        errors.append("standards_context must be an object/dict")
    else:
        standards = request.standards_context.get("standards", [])
        if standards is not None and not isinstance(standards, list):
            errors.append("standards_context.standards must be a list")
    return errors
