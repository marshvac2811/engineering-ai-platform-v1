"""Universal engineering planning layer.

The planner turns an interpreted request into an auditable execution graph.
It never performs engineering calculations and never invents missing inputs.
Capabilities are discovered from the authoritative registry rather than from a
client-facing list of vertical recipes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from skill_framework.input_resolver import resolve_input_requirements


@dataclass
class EngineeringTask:
    task_id: str
    objective: str
    capability_id: Optional[str]
    sequence: int
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"
    required_inputs: List[str] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)
    requested_outputs: List[str] = field(default_factory=list)
    methodology: Dict[str, Any] = field(default_factory=dict)
    governance: Dict[str, Any] = field(default_factory=dict)
    execution_mode: str = "deterministic_or_capability"
    human_review_required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _capability_card(definition: Any) -> Dict[str, Any]:
    required = list(getattr(definition, "required_inputs", []) or [])
    optional = list(getattr(definition, "optional_inputs", []) or [])
    conditional = list(getattr(definition, "conditional_inputs", []) or [])
    return {
        "capability_id": getattr(definition, "skill_id", ""),
        "domain": getattr(definition, "domain", ""),
        "description": getattr(definition, "description", ""),
        "execution": getattr(definition, "execution", ""),
        "required_inputs": [getattr(x, "name", "") for x in required],
        "optional_inputs": [getattr(x, "name", "") for x in optional],
        "conditional_inputs": [getattr(x, "name", "") for x in conditional],
        "standards": list(getattr(definition, "standards", []) or []),
    }


def build_engineering_plan(
    *,
    understanding: Dict[str, Any],
    registry: Any,
    inputs: Dict[str, Any],
    work_items: Optional[List[Dict[str, Any]]] = None,
    governance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an execution plan from AI interpretation + registered capabilities."""
    governance = dict(governance or {})
    tasks: List[EngineeringTask] = []
    candidates = work_items or []
    if not candidates and understanding.get("capability_id"):
        candidates = [{"capability_id": understanding.get("capability_id")}]
    ai_tasks = [x for x in (understanding.get("tasks") or []) if isinstance(x, dict)]
    if ai_tasks and not work_items:
        candidates = [{
            "capability_id": x.get("capability_id") or x.get("skill_id"),
            "objective": x.get("objective"),
            "depends_on": x.get("depends_on") or [],
            "requested_outputs": x.get("requested_outputs") or understanding.get("requested_outputs") or [],
            "methodology": x.get("methodology") or understanding.get("methodology") or {},
        } for x in ai_tasks]

    for index, item in enumerate(candidates, 1):
        capability_id = item.get("capability_id") or item.get("skill_id")
        if not capability_id or capability_id not in registry:
            tasks.append(EngineeringTask(
                task_id=f"task-{index}",
                objective=str(item.get("objective") or understanding.get("objective") or "Engineering analysis"),
                capability_id=None,
                sequence=index,
                status="capability_required",
                requested_outputs=list(understanding.get("requested_outputs") or []),
                methodology=dict(understanding.get("methodology") or {}),
                governance=governance,
            ))
            continue

        definition = registry.get(capability_id)
        resolution = resolve_input_requirements(definition, inputs)
        required = [getattr(x, "name", "") for x in list(definition.required_inputs or []) + list(definition.conditional_inputs or [])]
        task_status = "ready" if not resolution.missing_inputs else "awaiting_information"
        tasks.append(EngineeringTask(
            task_id=f"task-{index}",
            objective=str(item.get("objective") or understanding.get("objective") or f"Execute {capability_id}"),
            capability_id=capability_id,
            sequence=index,
            depends_on=[str(x) for x in (item.get("depends_on") or [])] or ([f"task-{index-1}"] if index > 1 else []),
            status=task_status,
            required_inputs=required,
            missing_inputs=list(resolution.missing_inputs),
            requested_outputs=list(item.get("requested_outputs") or understanding.get("requested_outputs") or []),
            methodology=dict(item.get("methodology") or understanding.get("methodology") or {}),
            governance=governance,
        ))

    task_ids = {t.task_id for t in tasks}
    for task in tasks:
        task.depends_on = [d for d in task.depends_on if d in task_ids and d != task.task_id]
    ready_ids = [t.task_id for t in tasks if t.status == "ready"]
    return {
        "status": "ready" if tasks and all(t.status == "ready" for t in tasks) else ("awaiting_information" if tasks else "capability_required"),
        "tasks": [t.to_dict() for t in tasks],
        "execution_order": [t.task_id for t in tasks],
        "ready_tasks": ready_ids,
        "parallel_groups": [ready_ids] if ready_ids else [],
        "human_review_required": True,
        "calculation_authority": "registered_engineering_capability",
        "ai_boundary": "AI interprets, plans and orchestrates; registered capabilities perform calculations/analysis.",
    }


def capability_catalog(registry: Any) -> List[Dict[str, Any]]:
    """Return internal semantic capability metadata for an AI planner."""
    return [_capability_card(definition) for definition in registry.values()]
