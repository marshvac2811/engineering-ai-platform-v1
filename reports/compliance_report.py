from typing import Any, Dict, List

def build_compliance_report(*, skill_id: str, engineering_result: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = list(engineering_result.get("compliance") or [])
    rows = []
    for check in checks:
        rows.append({
            "authority": check.get("authority"),
            "code": check.get("code_name"),
            "edition": check.get("edition"),
            "clause": check.get("clause_reference"),
            "requirement_type": check.get("requirement_type"),
            "project_value": check.get("input_value"),
            "required_value": check.get("required_value"),
            "unit": check.get("unit"),
            "calculation": check.get("calculation"),
            "status": check.get("status"),
            "evidence": check.get("evidence", {}),
        })
    return {
        "report_type": "engineering_compliance_report",
        "skill_id": skill_id,
        "compliance_checks": rows,
        "summary": {
            "checks": len(rows),
            "pass": sum(1 for x in rows if x["status"] == "PASS"),
            "fail": sum(1 for x in rows if x["status"] == "FAIL"),
            "not_applicable": sum(1 for x in rows if x["status"] == "NOT_APPLICABLE"),
            "not_verifiable": sum(1 for x in rows if x["status"] == "NOT_VERIFIABLE"),
        },
        "note": "Code applicability is project-specific. A cited requirement is not automatically mandatory unless applicability has been established.",
    }
