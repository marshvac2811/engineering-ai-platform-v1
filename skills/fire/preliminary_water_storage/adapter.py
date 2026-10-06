from __future__ import annotations
from skills.common import SkillRequest, SkillResult
from skills.fire.preliminary_water_storage import calculate_fire_water_storage

class FireWaterStorageSkill:
    skill_id = "fire_water_storage"
    version = "1.0.0"
    source_revision = "internal-governed-2026-10-06"

    def validate(self, request: SkillRequest) -> list[str]:
        i=request.inputs; e=[]
        for k in ("required_flow_lpm","duration_min"):
            if k not in i: e.append(f"Missing required input: {k}")
            else:
                try:
                    if float(i[k]) <= 0: e.append(f"{k} must be positive")
                except (TypeError,ValueError): e.append(f"{k} must be numeric")
        if "reserve_pct" in i:
            try:
                if float(i["reserve_pct"]) < 0: e.append("reserve_pct must be non-negative")
            except (TypeError,ValueError): e.append("reserve_pct must be numeric")
        return e

    def run(self, request: SkillRequest) -> SkillResult:
        errors=self.validate(request)
        if errors: return SkillResult(skill_id=self.skill_id,status="input_validation_failed",validation_errors=errors,source_revision=self.source_revision)
        try: result=calculate_fire_water_storage(required_flow_lpm=float(request.inputs["required_flow_lpm"]),duration_min=float(request.inputs["duration_min"]),reserve_pct=float(request.inputs.get("reserve_pct",0)))
        except (ValueError,TypeError) as exc: return SkillResult(skill_id=self.skill_id,status="calculation_failed",validation_errors=[str(exc)],source_revision=self.source_revision)
        return SkillResult(skill_id=self.skill_id,status="draft_ready",engineering_result=result,assumptions=result["assumptions"],warnings=result["limitations"],calculation_trace=[{"step":1,"operation":"flow_times_duration"},{"step":2,"operation":"apply_explicit_reserve_percentage"},{"step":3,"operation":"convert_litres_to_m3"}],human_review_required=True,source_revision=self.source_revision)
