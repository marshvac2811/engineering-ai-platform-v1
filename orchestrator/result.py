"""Cross-task engineering QA and result consolidation.

This layer checks workflow completeness and traceability. It does not judge
engineering correctness itself; numerical/discipline-specific correctness
remains the responsibility of registered capabilities and human review.
"""
from __future__ import annotations
from typing import Any, Dict, List

from knowledge.evidence import build_evidence_bundle


def build_workflow_result(*, workflow: Dict[str, Any], request_understanding: Dict[str, Any],
                          governance: Dict[str, Any], inputs: Dict[str, Any],
                          assumptions: Dict[str, Any]) -> Dict[str, Any]:
    task_outputs = workflow.get("task_outputs") or {}
    results = workflow.get("engineering_results") or []
    assumptions_out: List[Any] = []
    warnings: List[Any] = []
    evidence: List[Any] = []
    calculations: List[Any] = []

    for item in results:
        er = item.get("engineering_result") or {}
        for key, target in (("assumptions", assumptions_out), ("warnings", warnings),
                            ("evidence", evidence), ("calculation_trace", calculations)):
            value = er.get(key) or item.get(key)
            if isinstance(value, list):
                target.extend(value)
        calculations.append({
            "task_id": item.get("task_id"),
            "capability_id": item.get("capability_id"),
            "outputs": er,
        })

    evidence_bundle = build_evidence_bundle(
        governance=governance,
        project_context=workflow.get("project_context") or {},
        result_evidence=evidence,
    )

    task_statuses = [
        {"task_id": t.get("task_id"), "status": t.get("status"),
         "capability_id": t.get("capability_id"), "depends_on": t.get("depends_on", [])}
        for t in (workflow.get("engineering_plan", {}).get("tasks") or [])
    ]
    completed = sum(1 for t in task_statuses if t["status"] == "completed")
    total = len(task_statuses)
    qa = {
        "status": "ready_for_human_review" if workflow.get("status") == "completed" and completed == total else "not_ready",
        "task_count": total,
        "completed_tasks": completed,
        "all_tasks_completed": bool(total) and completed == total,
        "dependency_integrity": all(
            dep in {t["task_id"] for t in task_statuses}
            for t in task_statuses for dep in t["depends_on"]
        ),
        "calculation_authority": workflow.get("calculation_authority"),
        "checks": [
            "All planned tasks must complete before the workflow can enter human review.",
            "Results are attributable to registered capabilities.",
            "Dependency relationships are retained in the execution trace.",
            "Standards/governance references are metadata unless verified evidence establishes applicability.",
        ],
    }
    return {
        "status": workflow.get("status"),
        "request_understanding": request_understanding,
        "governance": governance,
        "inputs": inputs,
        "assumptions": assumptions_out + list(assumptions.get("items") or []) if isinstance(assumptions, dict) else assumptions_out,
        "calculations": calculations,
        "results": results,
        "recommendations": [],
        "risks_warnings": warnings + list(workflow.get("blockers") or []),
        "evidence": evidence_bundle["records"],
        "evidence_bundle": evidence_bundle,
        "qa": qa,
        "task_statuses": task_statuses,
        "execution_trace": workflow.get("execution_trace") or [],
        "human_review": {
            "required": True,
            "status": "required" if qa["status"] == "ready_for_human_review" else "blocked",
        },
        "task_outputs": task_outputs,
    }
