from pathlib import Path

from governance.engine import build_governance_context
from orchestrator.planner import build_engineering_plan
from skill_framework.registry import load_skill_registry


def _registry():
    return load_skill_registry(Path(__file__).resolve().parents[1] / "skill_registry" / "registry.yaml")


def test_planner_builds_registered_task_without_calculating():
    registry = _registry()
    plan = build_engineering_plan(
        understanding={
            "objective": "Calculate pump duty",
            "capability_id": "pump_head",
            "requested_outputs": ["velocity", "total dynamic head"],
            "methodology": {"method": "Darcy-Weisbach"},
        },
        registry=registry,
        inputs={
            "flow_m3hr": 25,
            "diameter_mm": 80,
            "straight_length_m": 120,
            "static_head_m": 12,
            "margin_pct": 10,
            "material": "gi",
        },
        governance=build_governance_context(skill_id="pump_head"),
    )
    assert plan["status"] == "ready"
    assert plan["tasks"][0]["capability_id"] == "pump_head"
    assert plan["tasks"][0]["status"] == "ready"
    assert "total_dynamic_head" not in plan["tasks"][0]


def test_planner_refuses_unknown_capability():
    registry = _registry()
    plan = build_engineering_plan(
        understanding={"objective": "Perform a new engineering analysis", "capability_id": "not_registered"},
        registry=registry,
        inputs={},
    )
    assert plan["status"] == "capability_required"
    assert plan["tasks"][0]["status"] == "capability_required"
    assert plan["tasks"][0]["capability_id"] is None


def test_planner_preserves_ai_task_dependencies_and_parallel_ready_tasks():
    registry = _registry()
    plan = build_engineering_plan(
        understanding={
            "objective": "Coordinate engineering assessment",
            "tasks": [
                {"capability_id": "pump_head", "objective": "Calculate pump duty"},
                {"capability_id": "duct_sizing", "objective": "Size supply duct", "depends_on": []},
            ],
        },
        registry=registry,
        inputs={
            "flow_m3hr": 25, "diameter_mm": 80, "straight_length_m": 120,
            "static_head_m": 12, "margin_pct": 10, "material": "gi",
            "airflow": 2000, "method": "velocity", "duct_type": "round",
            "target_velocity_ms": 6, "material": "gi",
        },
    )
    assert len(plan["tasks"]) == 2
    assert plan["tasks"][0]["task_id"] == "task-1"
    assert plan["tasks"][1]["task_id"] == "task-2"
    assert plan["tasks"][1]["depends_on"] == []
