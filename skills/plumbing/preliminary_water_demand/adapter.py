from __future__ import annotations
from skills.common import SkillRequest, SkillResult
from skills.plumbing.preliminary_water_demand import calculate_plumbing_water_demand

class PlumbingWaterDemandSkill:
    skill_id = "plumbing_water_demand"
    version = "1.0.0"
    source_revision = "internal-governed-2026-10-06"

    def validate(self, request: SkillRequest) -> list[str]:
        i=request.inputs; e=[]
        if not isinstance(i.get("fixtures"),list) or not i["fixtures"]: e.append("fixtures must be a non-empty list")
        try:
            d=float(i.get("diversity_factor_pct",100))
            if d<=0 or d>100: e.append("diversity_factor_pct must be > 0 and <= 100")
        except (TypeError,ValueError): e.append("diversity_factor_pct must be numeric")
        return e

    def run(self, request: SkillRequest) -> SkillResult:
        errors=self.validate(request)
        if errors: return SkillResult(skill_id=self.skill_id,status="input_validation_failed",validation_errors=errors,source_revision=self.source_revision)
        try: result=calculate_plumbing_water_demand(fixtures=request.inputs["fixtures"],diversity_factor_pct=float(request.inputs.get("diversity_factor_pct",100)))
        except (ValueError,TypeError) as exc: return SkillResult(skill_id=self.skill_id,status="calculation_failed",validation_errors=[str(exc)],source_revision=self.source_revision)
        return SkillResult(skill_id=self.skill_id,status="draft_ready",engineering_result=result,assumptions=result["assumptions"],warnings=result["limitations"],calculation_trace=[{"step":1,"operation":"aggregate_explicit_fixture_flows"},{"step":2,"operation":"apply_explicit_diversity_factor"},{"step":3,"operation":"convert_lpm_to_m3hr"}],human_review_required=True,source_revision=self.source_revision)
