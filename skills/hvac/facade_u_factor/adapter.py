from skills.common import SkillRequest, SkillResult
from code_engine.registry import CodeRegistry
from code_engine.compliance import ComplianceEngine
from pathlib import Path

class FacadeUFactorSkill:
    def run(self, request: SkillRequest) -> SkillResult:
        i = request.inputs
        components = i.get("components")
        if not isinstance(components, list) or not components:
            return SkillResult("facade_u_factor", "input_validation_failed",
                validation_errors=["components must be a non-empty list of {name, area_m2, u_factor} objects."])
        total_area = 0.0
        weighted = 0.0
        trace = []
        for idx, c in enumerate(components):
            try:
                area = float(c["area_m2"]); u = float(c["u_factor"])
            except (KeyError, TypeError, ValueError):
                return SkillResult("facade_u_factor", "input_validation_failed",
                    validation_errors=[f"components[{idx}] requires numeric area_m2 and u_factor."])
            if area <= 0:
                return SkillResult("facade_u_factor", "input_validation_failed",
                    validation_errors=[f"components[{idx}].area_m2 must be > 0."])
            if u < 0:
                return SkillResult("facade_u_factor", "input_validation_failed",
                    validation_errors=[f"components[{idx}].u_factor must be >= 0."])
            total_area += area
            weighted += area * u
            trace.append({"component": c.get("name", f"component_{idx+1}"), "area_m2": area, "u_factor": u, "area_times_u": area*u})
        overall = weighted / total_area
        registry = CodeRegistry.from_yaml(Path(__file__).resolve().parents[3] / "standards" / "registry.yaml")
        req = registry.get_requirement("ecbc2017_vertical_fenestration_u_factor")
        ctx = request.project_context or {}
        building_type = str(ctx.get("building_type", "")).lower()
        component = str(ctx.get("component", "vertical_fenestration")).lower()
        applicable = building_type == "commercial" and component == "vertical_fenestration"
        check = ComplianceEngine().evaluate(
            req, overall, applicable=applicable,
            evidence={"calculation_method": "preliminary_area_weighted_u_factor", "project_context": ctx}
        )
        warnings = [
            "Preliminary area-weighted U-factor only; it is not a certified NFRC/ISO 15099 product rating.",
            "Final fenestration compliance must use the applicable project method and verified product/system data."
        ]
        if not applicable:
            warnings.append("ECBC vertical-fenestration check was not applied because applicability was not established as commercial vertical fenestration.")
        return SkillResult(
            "facade_u_factor", "completed",
            engineering_result={
                "overall_u_factor_w_m2k": overall,
                "total_area_m2": total_area,
                "component_count": len(components),
                "calculation_method": "area_weighted_u_factor",
                "compliance": [check.to_dict()],
            },
            standards=[{
                "authority": req.document.authority,
                "code": req.document.code_name,
                "edition": req.document.edition,
                "clause": req.clause,
                "requirement": f"U-factor {req.operator} {req.required_value} {req.unit}",
                "status": check.status.value,
            }],
            warnings=warnings,
            calculation_trace=trace,
            human_review_required=True,
            source_revision="phase5-facade-u-factor-1",
        )
