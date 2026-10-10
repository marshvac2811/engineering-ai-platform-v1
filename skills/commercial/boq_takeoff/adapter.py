from __future__ import annotations
from skills.common import SkillRequest, SkillResult
from skills.commercial.boq_takeoff import takeoff, parse_boq_csv, parse_recipes_csv


class BoqTakeoffSkill:
    skill_id = "boq_takeoff"
    version = "1.0.0"
    source_revision = "internal-governed-2026-10-10"

    def _lines(self, i):
        if isinstance(i.get("boq_items"), list) and i["boq_items"]:
            return i["boq_items"]
        if str(i.get("boq_csv") or "").strip():
            return parse_boq_csv(str(i["boq_csv"]))
        return []

    def validate(self, request: SkillRequest):
        i = request.inputs
        errors = []
        if not self._lines(i):
            errors.append("Provide boq_items (list of {item_no, description, unit, quantity}) or boq_csv text with a header row")
        if i.get("recipes") is not None and not isinstance(i.get("recipes"), list):
            errors.append("recipes must be a list of recipe objects")
        return errors

    def run(self, request: SkillRequest) -> SkillResult:
        errors = self.validate(request)
        if errors:
            return SkillResult(skill_id=self.skill_id, status="input_validation_failed", validation_errors=errors,
                               source_revision=self.source_revision, skill_version=self.version)
        try:
            custom = list(request.inputs.get("recipes") or [])
            if str(request.inputs.get("recipes_csv") or "").strip():
                custom += parse_recipes_csv(str(request.inputs["recipes_csv"]))
            res = takeoff(self._lines(request.inputs), custom or None)
        except (ValueError, TypeError, KeyError) as exc:
            return SkillResult(skill_id=self.skill_id, status="calculation_failed", validation_errors=[str(exc)],
                               source_revision=self.source_revision, skill_version=self.version)
        warnings = ["Preliminary material takeoff for engineering/commercial review."]
        if res["unmatched_lines"]:
            warnings.append(f"{res['unmatched_line_count']} BOQ line(s) were not taken off (no recipe, bad unit or bad quantity); see the unmatched list.")
        if res["unvalidated_recipes_used"]:
            warnings.append("Consumption and wastage factors for these recipes are unvalidated defaults: " + ", ".join(res["unvalidated_recipes_used"]))
        trace = [
            {"step": 1, "operation": "match_recipes", "detail": f"{res['matched_line_count']} of {res['line_count']} BOQ lines matched to a recipe by description"},
            {"step": 2, "operation": "convert_units", "detail": "BOQ quantity converted to the recipe base unit (sqm/sqft, m/rft)"},
            {"step": 3, "operation": "materials", "detail": "Quantity x consumption per unit x (1 + wastage %) for each material"},
            {"step": 4, "operation": "consolidate", "detail": f"Identical material/unit pairs summed into {len(res['material_totals'])} procurement line(s)"},
        ]
        assumptions = [{"name": "recipe_factors", "value": "recipe catalogue", "basis": "Consumption and wastage come from the recipe catalogue (scope_engine/catalog.yaml) or the recipes supplied with this request; confirm them for the project."}]
        return SkillResult(skill_id=self.skill_id, status="draft_ready", engineering_result=res, assumptions=assumptions,
                           warnings=warnings, calculation_trace=trace, source_revision=self.source_revision, skill_version=self.version)
