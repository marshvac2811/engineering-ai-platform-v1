"""Generic recipe-driven quantity takeoff skill.

This is the SiteTrack-style material engine for the platform. Vertical-specific
knowledge lives in scope_engine/catalog.yaml, not in this calculator.
"""
from __future__ import annotations
from skills.common import SkillRequest, SkillResult


class QuantityTakeoffSkill:
    skill_id = "quantity_takeoff"

    def validate(self, request: SkillRequest):
        text = str(request.inputs.get("request_text", "")).strip()
        return ["request_text is required"] if not text else []

    def run(self, request: SkillRequest) -> SkillResult:
        errors = self.validate(request)
        if errors:
            return SkillResult(self.skill_id, "input_validation_failed", validation_errors=errors)
        from scope_engine.analyzer import analyze_scope
        scope = analyze_scope(str(request.inputs["request_text"]))
        if not scope["work_items"]:
            return SkillResult(
                self.skill_id,
                "input_validation_failed",
                engineering_result=scope,
                validation_errors=scope["unsupported_scope"] or ["No supported quantity recipe matched the request."],
            )
        return SkillResult(
            self.skill_id,
            "calculated",
            engineering_result=scope,
            warnings=list(scope["unsupported_scope"]),
            calculation_trace=[{"step": "recipe_quantity", "description": "Work quantity × recipe consumption × (1 + wastage%)."}],
            human_review_required=True,
            source_revision="scope-engine-v1",
        )
