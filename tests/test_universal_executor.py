from pathlib import Path

from orchestrator.executor import execute_engineering_plan
from skill_framework.registry import load_skill_registry


def _registry():
    return load_skill_registry(Path(__file__).resolve().parents[1] / "skill_registry" / "registry.yaml")


def test_executor_runs_registered_single_task_and_returns_trace():
    plan = {
        "status": "ready_for_execution",
        "tasks": [{
            "task_id": "task-1",
            "objective": "Calculate pump duty",
            "capability_id": "pump_head",
            "sequence": 1,
            "depends_on": [],
            "status": "ready",
        }],
    }
    workflow = execute_engineering_plan(
        plan=plan,
        inputs={
            "flow_m3hr": 25,
            "diameter_mm": 80,
            "roughness_mm": 0.15,
            "straight_length_m": 120,
            "static_head_m": 12,
            "margin_pct": 10,
            "material": "gi",
        },
        project_context={},
        standards_context={},
        assumptions_context={},
        request_id="test-job",
    )
    assert workflow["status"] == "completed"
    assert workflow["engineering_results"][0]["capability_id"] == "pump_head"
    assert workflow["execution_trace"][0]["task_id"] == "task-1"
    assert workflow["engineering_plan"]["tasks"][0]["status"] == "completed"


def test_executor_stops_at_missing_task_inputs_without_calculating():
    plan = {
        "status": "ready_for_execution",
        "tasks": [{
            "task_id": "task-1",
            "objective": "Calculate pump duty",
            "capability_id": "pump_head",
            "sequence": 1,
            "depends_on": [],
            "status": "ready",
        }],
    }
    workflow = execute_engineering_plan(
        plan=plan,
        inputs={"flow_m3hr": 25},
        project_context={},
        standards_context={},
        assumptions_context={},
    )
    assert workflow["status"] == "awaiting_information"
    assert workflow["engineering_results"] == []
    assert workflow["engineering_plan"]["tasks"][0]["status"] == "awaiting_information"
    assert workflow["engineering_plan"]["tasks"][0]["missing_inputs"]


def test_executor_honors_dependency_outputs():
    # The second task intentionally has no independent input contract in this
    # test; a mocked capability would consume the first task output. This test
    # verifies the dependency gate at the plan level without duplicating a
    # vertical-specific calculation.
    plan = {
        "status": "ready_for_execution",
        "tasks": [
            {
                "task_id": "task-1",
                "objective": "First engineering task",
                "capability_id": "pump_head",
                "sequence": 1,
                "depends_on": [],
                "status": "ready",
            },
            {
                "task_id": "task-2",
                "objective": "Dependent engineering task",
                "capability_id": "pump_head",
                "sequence": 2,
                "depends_on": ["task-1"],
                "status": "ready",
            },
        ],
    }
    workflow = execute_engineering_plan(
        plan=plan,
        inputs={
            "flow_m3hr": 25,
            "diameter_mm": 80,
            "roughness_mm": 0.15,
            "straight_length_m": 120,
            "static_head_m": 12,
            "margin_pct": 10,
            "material": "gi",
        },
        project_context={},
        standards_context={},
        assumptions_context={},
    )
    assert workflow["status"] == "completed"
    assert [x["task_id"] for x in workflow["execution_trace"]] == ["task-1", "task-2"]
    assert workflow["engineering_plan"]["tasks"][1]["depends_on"] == ["task-1"]


def test_executor_enforces_explicit_dependency_binding():
    plan = {"tasks": [
        {"task_id": "task-1", "objective": "upstream", "capability_id": "pump_head", "status": "ready", "depends_on": [], "sequence": 1},
        {"task_id": "task-2", "objective": "downstream", "capability_id": "pump_head", "status": "ready", "depends_on": ["task-1"], "sequence": 2,
         "input_bindings": {"flow_m3hr": "task-1.not_an_output"}}]}
    workflow = execute_engineering_plan(plan=plan, inputs={"flow_m3hr": 25, "diameter_mm": 80, "roughness_mm": 0.15, "straight_length_m": 120, "static_head_m": 12, "margin_pct": 10, "material": "gi"}, project_context={}, standards_context={}, assumptions_context={})
    assert workflow["engineering_plan"]["tasks"][1]["status"] == "blocked"
    assert any("not_an_output" in x for x in workflow["blockers"])
