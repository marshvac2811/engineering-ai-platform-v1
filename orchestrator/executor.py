"""Universal multi-capability engineering workflow executor.

The executor consumes an already interpreted engineering plan. It does not
interpret natural language or perform calculations itself. Each executable
task is delegated to the registered capability interface, with dependency
outputs made available only to downstream tasks.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from skills.common import SkillRequest
from orchestrator.engine import execute
from skill_framework.registry import load_skill_registry
from skill_framework.input_resolver import resolve_input_requirements
from pathlib import Path
from governance.assumption_policy import resolve_input_assumptions


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "skill_registry" / "registry.yaml"


_BLOCKING_STATUSES = {"input_validation_failed", "calculation_failed", "skill_not_registered"}


def _task_map(plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(t.get("task_id")): t for t in plan.get("tasks", []) if isinstance(t, dict) and t.get("task_id")}


def _dependency_ready(task: Dict[str, Any], tasks: Dict[str, Dict[str, Any]]) -> bool:
    return all(tasks.get(dep, {}).get("status") == "completed" for dep in task.get("depends_on", []))


def _dependency_outputs(task: Dict[str, Any], outputs: Dict[str, Dict[str, Any]]) -> tuple[Dict[str, Any], List[str]]:
    bindings = dict(task.get("input_bindings") or {})
    if not bindings:
        merged: Dict[str, Any] = {}
        for dep in task.get("depends_on", []):
            result = outputs.get(dep, {}).get("engineering_result") or {}
            if isinstance(result, dict): merged.update(deepcopy(result))
        return merged, []
    bound: Dict[str, Any] = {}
    errors: List[str] = []
    for target, source in bindings.items():
        text = str(source)
        if "." not in text:
            errors.append(f"{target}: invalid binding {text!r}; expected task-id.output-name")
            continue
        source_task, output_name = text.split(".", 1)
        if source_task not in task.get("depends_on", []):
            errors.append(f"{target}: source task {source_task} is not a declared dependency")
            continue
        result = outputs.get(source_task, {}).get("engineering_result") or {}
        if output_name not in result:
            errors.append(f"{target}: output {output_name} is not present in {source_task}")
            continue
        bound[target] = deepcopy(result[output_name])
    return bound, errors


def execute_engineering_plan(
    *,
    plan: Dict[str, Any],
    inputs: Dict[str, Any],
    project_context: Dict[str, Any],
    standards_context: Dict[str, Any],
    assumptions_context: Dict[str, Any],
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Execute all currently runnable tasks in dependency order.

    The function returns a resumable execution envelope. It stops rather than
    guessing when a capability is unavailable, inputs are missing, or a
    capability reports a validation/calculation failure.
    """
    registry = load_skill_registry(REGISTRY_PATH)
    tasks = _task_map(plan)
    outputs: Dict[str, Dict[str, Any]] = {str(k): deepcopy(v) for k, v in (plan.get("task_outputs") or {}).items() if isinstance(v, dict)}
    trace: List[Dict[str, Any]] = []
    blockers: List[str] = []

    # Work on a copy so the persisted orchestration plan is updated explicitly.
    planned = deepcopy(plan)
    # Reject malformed dependency graphs before any engineering capability runs.
    for task_id, task in tasks.items():
        unknown = [d for d in task.get("depends_on", []) if d not in tasks or d == task_id]
        if unknown:
            task["status"] = "blocked"
            blockers.append(f"{task_id}: invalid dependency {', '.join(map(str, unknown))}")
    def visit(node: str, active: set[str], done: set[str]) -> bool:
        if node in active: return True
        if node in done: return False
        active.add(node)
        cycle = any(visit(str(dep), active, done) for dep in tasks[node].get("depends_on", []) if dep in tasks)
        active.remove(node); done.add(node)
        return cycle
    done: set[str] = set()
    for task_id in tasks:
        if visit(task_id, set(), done):
            tasks[task_id]["status"] = "blocked"
            blockers.append(f"{task_id}: dependency cycle detected")

    progress = True
    while progress:
        progress = False
        for task_id, task in tasks.items():
            if task.get("status") in {"completed", "awaiting_information", "failed", "capability_required", "blocked"}:
                continue
            capability_id = task.get("capability_id")
            if not capability_id:
                task["status"] = "capability_required"
                blockers.append(f"{task_id}: no registered execution capability")
                continue
            if capability_id not in registry:
                task["status"] = "capability_required"
                blockers.append(f"{task_id}: capability {capability_id} is not registered")
                continue
            if not _dependency_ready(task, tasks):
                task["status"] = "waiting_dependency"
                continue

            task_inputs = dict(inputs)
            dependency_inputs, binding_errors = _dependency_outputs(task, outputs)
            if binding_errors:
                task["status"] = "blocked"
                blockers.extend(f"{task_id}: {e}" for e in binding_errors)
                continue
            task_inputs.update(dependency_inputs)
            definition = registry.get(capability_id)
            assumption_resolved, input_assumptions, assumption_blockers = resolve_input_assumptions(
                capability_id,
                task_inputs,
                assumptions_context,
            )
            task_inputs = assumption_resolved
            task["input_assumptions"] = deepcopy(input_assumptions)
            if assumption_blockers:
                task["assumption_blockers"] = list(assumption_blockers)
                blockers.extend(f"{task_id}: {e}" for e in assumption_blockers)
            resolution = resolve_input_requirements(definition, task_inputs)
            if resolution.missing_inputs:
                task["status"] = "awaiting_information"
                task["missing_inputs"] = list(resolution.missing_inputs)
                blockers.append(f"{task_id}: missing {', '.join(resolution.missing_inputs)}")
                continue

            task["status"] = "processing"
            request = SkillRequest(
                skill_id=capability_id,
                inputs=task_inputs,
                project_context=project_context,
                standards_context=standards_context,
                assumptions_context=assumptions_context,
                request_id=request_id,
            )
            try:
                result = execute(request).to_dict()
            except Exception as exc:
                result = {
                    "status": "calculation_failed",
                    "engineering_result": {},
                    "validation_errors": [f"{type(exc).__name__}: {exc}"],
                }
            result["task_id"] = task_id
            result["capability_id"] = capability_id
            outputs[task_id] = result
            trace.append({
                "task_id": task_id,
                "capability_id": capability_id,
                "status": result.get("status"),
                "inputs": task_inputs,
                "input_assumptions": deepcopy(input_assumptions),
                "depends_on": list(task.get("depends_on") or []),
            })
            progress = True

            if result.get("status") == "input_validation_failed":
                task["status"] = "awaiting_information"
                task["missing_inputs"] = list(result.get("validation_errors") or [])
                blockers.extend(f"{task_id}: {e}" for e in (result.get("validation_errors") or []))
                continue
            if result.get("status") in _BLOCKING_STATUSES:
                task["status"] = "failed"
                blockers.extend(f"{task_id}: {e}" for e in (result.get("validation_errors") or []))
                continue
            task["status"] = "completed"
            task["missing_inputs"] = []

    # Any task whose dependencies failed can no longer run in this execution.
    for task_id, task in tasks.items():
        if task.get("status") == "waiting_dependency":
            failed_deps = [
                dep for dep in task.get("depends_on", [])
                if tasks.get(dep, {}).get("status") in {"failed", "capability_required", "awaiting_information"}
            ]
            if failed_deps:
                task["status"] = "blocked"
                blockers.append(f"{task_id}: blocked by {', '.join(failed_deps)}")

    statuses = [t.get("status") for t in tasks.values()]
    if statuses and all(s == "completed" for s in statuses):
        status = "completed"
    elif any(s in {"awaiting_information", "capability_required", "blocked"} for s in statuses):
        status = "awaiting_information" if any(s == "awaiting_information" for s in statuses) else "blocked"
    elif any(s == "failed" for s in statuses):
        status = "failed"
    else:
        status = "pending"

    planned["tasks"] = list(tasks.values())
    planned["task_outputs"] = deepcopy(outputs)
    planned["execution_trace"] = deepcopy(trace)
    planned["status"] = status
    planned["ready_tasks"] = [
        t["task_id"] for t in tasks.values()
        if t.get("status") == "ready" and _dependency_ready(t, tasks)
    ]

    engineering_results = [
        {
            "task_id": task_id,
            "capability_id": result.get("capability_id"),
            "status": result.get("status"),
            "engineering_result": result.get("engineering_result", {}),
            "calculation_trace": result.get("calculation_trace") or [],
            "assumptions": (result.get("assumptions") or []) + list((tasks.get(task_id) or {}).get("input_assumptions") or []),
            "warnings": result.get("warnings") or [],
            # Preserve the full evidence chain produced by the skill so the
            # evidence bundle and report are not thinner than the execution.
            "objective": (tasks.get(task_id) or {}).get("objective"),
            "inputs": deepcopy(
                next((t.get("inputs") for t in trace if t.get("task_id") == task_id), None) or {}
            ),
            "standards": result.get("standards") or [],
            "compliance": (
                result.get("compliance")
                or (result.get("engineering_result") or {}).get("compliance")
                or []
            ),
            "evidence": result.get("evidence") or [],
            "validation_errors": result.get("validation_errors") or [],
            "skill_version": str(getattr(definition, "version", "") or ""),
            "source_revision": result.get("source_revision") or getattr(definition, "source_revision", "") or "",
            "limitations": result.get("limitations") or (result.get("engineering_result") or {}).get("limitations") or [],
            "human_review_required": result.get("human_review_required", True),
        }
        for task_id, result in outputs.items()
    ]
    return {
        "status": status,
        "engineering_plan": planned,
        "task_outputs": outputs,
        "engineering_results": engineering_results,
        "execution_trace": trace,
        "blockers": blockers,
        "human_review_required": True,
        "calculation_authority": "registered_engineering_capability",
        "project_context": deepcopy(project_context),
        "standards_context": deepcopy(standards_context),
    }
