from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "skill_registry" / "registry.yaml"

def load_registry() -> dict:
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def skill_metadata(skill_id: str) -> dict:
    for skill in load_registry().get("skills", []):
        if skill.get("skill_id") == skill_id:
            return skill
    raise KeyError(f"Unknown skill: {skill_id}")
