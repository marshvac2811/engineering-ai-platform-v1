from pathlib import Path

from skill_framework.registry import load_skill_registry
from validators.skill_inputs import validate_skill_inputs

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "skill_registry" / "registry.yaml"


def validate_registered_skill_inputs(skill_id: str, inputs):
    registry = load_skill_registry(REGISTRY_PATH)

    if skill_id not in registry.skill_ids:
        return [f"Skill is not registered in current registry: {skill_id}"]

    definition = registry.get(skill_id)

    if definition.executable is not True:
        return [f"Skill is not executable in current registry: {skill_id}"]

    return validate_skill_inputs(inputs, definition)
