"""Cross-task engineering QA and result consolidation.

This layer checks workflow completeness and traceability. It does not judge
engineering correctness itself; numerical/discipline-specific correctness
remains the responsibility of registered capabilities and human review.
"""
from __future__ import annotations
from typing import Any, Dict, List

from knowledge.evidence import build_evidence_bundle
from orchestrator.reasoning import build_decision_package


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

    ai_reasoning = {
        "reasoning": dict(request_understanding.get("reasoning") or {}),
        "evidence_usage": list(request_understanding.get("evidence_usage") or []),
        "missing_evidence": list(request_understanding.get("missing_evidence") or []),
        "compliance_claims": list(request_understanding.get("compliance_claims") or []),
        "claim_gate": dict((governance.get("governed_knowledge") or {}).get("claim_gate") or {}),
    }
    if not ai_reasoning["claim_gate"].get("compliance_claim_allowed", False):
        ai_reasoning["compliance_claims"] = []
    decision_package = build_decision_package(request_understanding, governance, workflow.get("engineering_plan") or {})
    task_statuses = [
        {"task_id": t.get("task_id"), "status": t.get("status"),
         "capability_id": t.get("capability_id"), "depends_on": t.get("depends_on", [])}
        for t in (workflow.get("engineering_plan", {}).get("tasks") or [])
    ]
    completed = sum(1 for t in task_statuses if t["status"] == "completed")
    total = len(task_statuses)
    task_ids = {str(t["task_id"]) for t in task_statuses}
    trace_task_ids = {str(x.get("task_id")) for x in (workflow.get("execution_trace") or []) if isinstance(x, dict)}
    result_task_ids = {str(x.get("task_id")) for x in results if isinstance(x, dict)}
    dependency_integrity = all(dep in task_ids for t in task_statuses for dep in t["depends_on"])
    trace_integrity = bool(total) and all(task_id in trace_task_ids for task_id in task_ids)
    result_integrity = bool(total) and all(task_id in result_task_ids for task_id in task_ids)
    evidence_gate_consistent = (not decision_package.get("compliance_claims") or bool((decision_package.get("claim_gate") or {}).get("compliance_claim_allowed")))
    decision_status = str(decision_package.get("status") or "")
    qa_ready = (workflow.get("status") == "completed" and completed == total and bool(total) and dependency_integrity and trace_integrity and result_integrity and evidence_gate_consistent and decision_status != "evidence_incomplete")
    qa = {
        "status": "ready_for_human_review" if qa_ready else "not_ready",
        "task_count": total,
        "completed_tasks": completed,
        "all_tasks_completed": bool(total) and completed == total,
        "dependency_integrity": dependency_integrity,
        "trace_integrity": trace_integrity,
        "result_integrity": result_integrity,
        "evidence_gate_consistent": evidence_gate_consistent,
        "decision_package_status": decision_status,
        "calculation_authority": workflow.get("calculation_authority"),
        "checks": ["All planned tasks must complete before the workflow can enter human review.", "Every planned task must have an execution trace and attributable result.", "Dependency relationships must reference planned tasks.", "Compliance claims are permitted only when the governed evidence gate is open.", "Standards/governance references remain metadata unless verified evidence establishes applicability."],
    }
    return {
        "status": workflow.get("status"),
        "request_understanding": request_understanding,
        "ai_reasoning": ai_reasoning,
        "decision_package": decision_package,
        "governance": governance,
        "inputs": inputs,
        "assumptions": (assumptions_out + list(assumptions.get("items") or [])) if isinstance(assumptions, dict) else assumptions_out,
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
