from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from skill_framework.implementation_bindings import ImplementationBinding, binding_map
from skill_framework.registry import SkillRegistry, load_skill_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "skill_registry" / "registry.yaml"

@dataclass(frozen=True)
class Capability:
    skill_id: str
    domain: str
    task: str
    aliases: Tuple[str, ...]
    routing_terms: Tuple[str, ...]
    required_inputs: Tuple[str, ...]
    optional_inputs: Tuple[str, ...]
    conditional_inputs: Tuple[str, ...]
    implementation: ImplementationBinding
    report_type: str
    report_title: str
    deliverables: Tuple[str, ...]
    verified_check_ids: Tuple[str, ...]

def _registry() -> SkillRegistry:
    return load_skill_registry(REGISTRY_PATH)

def build_capability_catalog() -> Dict[str, Capability]:
    registry = _registry()
    bindings = binding_map()
    catalog: Dict[str, Capability] = {}
    for skill_id in registry.executable_ids:
        definition = registry.get(skill_id)
        binding = bindings.get(skill_id)
        if binding is None:
            raise RuntimeError(f"Executable skill has no implementation binding: {skill_id}")
        raw = registry.entries[skill_id].raw
        catalog[skill_id] = Capability(
            skill_id=skill_id, domain=definition.domain, task=definition.name,
            aliases=tuple(raw.get("aliases", [])),
            routing_terms=tuple(raw.get("routing_terms", [])),
            required_inputs=tuple(i.name for i in definition.required_inputs),
            optional_inputs=tuple(i.name for i in definition.optional_inputs),
            conditional_inputs=tuple(i.name for i in definition.conditional_inputs),
            implementation=binding,
            report_type=str(raw.get("report_type", f"{skill_id}_engineering")),
            report_title=str(raw.get("report_title", definition.name)),
            deliverables=tuple(raw.get("deliverables", [])),
            verified_check_ids=tuple(raw.get("verified_check_ids", [])),
        )
    return catalog

CAPABILITY_CATALOG = build_capability_catalog()

def get_capability(skill_id: str) -> Optional[Capability]:
    return CAPABILITY_CATALOG.get(skill_id)

def executable_skill_ids() -> List[str]:
    return sorted(CAPABILITY_CATALOG)

def routing_terms() -> Dict[str, Tuple[str, ...]]:
    return {skill_id: capability.routing_terms for skill_id, capability in CAPABILITY_CATALOG.items()}
