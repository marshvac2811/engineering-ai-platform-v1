from __future__ import annotations

import importlib
from pathlib import Path
from typing import Dict

from skills.common import SkillRequest, SkillResult
from skill_framework.registry import load_skill_registry
from skill_framework.implementation_bindings import binding_map


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "skill_registry" / "registry.yaml"


def _build_skills() -> Dict[str, object]:
    registry = load_skill_registry(REGISTRY_PATH)
    bindings = binding_map()

    skills: Dict[str, object] = {}

    for skill_id in registry.executable_ids:
        definition = registry.get(skill_id)
        binding = bindings.get(skill_id)

        if binding is None:
            raise RuntimeError(
                f"Executable skill has no implementation binding: {skill_id}"
            )

        if definition.executable is not True:
            continue

        module = importlib.import_module(binding.implementation_path)
        implementation_class = getattr(module, binding.implementation_class)
        skills[skill_id] = implementation_class()

    return skills


SKILLS = _build_skills()


def execute(request: SkillRequest) -> SkillResult:
    skill = SKILLS.get(request.skill_id)
    if skill is None:
        return SkillResult(
            request.skill_id,
            "skill_not_registered",
            validation_errors=[
                f"Skill is not executable in current registry batch: {request.skill_id}"
            ],
        )
    return skill.run(request)


def registered_skills():
    return sorted(SKILLS)
