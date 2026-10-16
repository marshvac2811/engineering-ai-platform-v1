from __future__ import annotations
from skills.common import SkillRequest, SkillResult
from skills.commercial.boq_takeoff import takeoff, parse_boq_csv, parse_recipes_csv
from skills.commercial.boq_takeoff.ai_draft import make_draft_fn
from skills.commercial.boq_takeoff.xlsx_boq import parse_boq_xlsx
from skills.commercial.boq_takeoff.programme import build_programme
from engineering.services_takeoff.measure import measure_dxf
from engineering.services_takeoff.boq_link import apply_drawing, DEFAULTS as DRAWING_DEFAULTS


class BoqTakeoffSkill:
    skill_id = "boq_takeoff"
    version = "1.0.0"
    source_revision = "internal-governed-2026-10-10"

    def _lines(self, i):
        if isinstance(i.get("boq_items"), list) and i["boq_items"]:
            return i["boq_items"]
        if str(i.get("boq_xlsx_b64") or "").strip():
            import base64
            import binascii
            try:
                return parse_boq_xlsx(base64.b64decode(str(i["boq_xlsx_b64"]), validate=True))
            except (binascii.Error, ValueError):
                raise ValueError("The Excel BOQ could not be read: it must be an .xlsx file with Description, Qty and Unit columns")
            except Exception:
                raise ValueError("The Excel BOQ could not be opened; save it as .xlsx and try again")
        if str(i.get("boq_csv") or "").strip():
            return parse_boq_csv(str(i["boq_csv"]))
        return []

    def validate(self, request: SkillRequest):
        i = request.inputs
        errors = []
        try:
            lines = self._lines(i)
        except ValueError as exc:
            return [str(exc)]
        if not lines:
            errors.append("Provide boq_items (list of {item_no, description, unit, quantity}) boq_csv text with a header row, or an Excel BOQ (boq_xlsx_b64)")
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
            draft_fn = self.draft_fn if hasattr(self, 'draft_fn') else (make_draft_fn() if request.inputs.get('ai_draft', True) else None)
            boq_lines = self._lines(request.inputs)
            res = takeoff(boq_lines, custom or None, draft_fn=draft_fn)
        except (ValueError, TypeError, KeyError) as exc:
            return SkillResult(skill_id=self.skill_id, status="calculation_failed", validation_errors=[str(exc)],
                               source_revision=self.source_revision, skill_version=self.version)
        warnings = ["Preliminary material takeoff for engineering/commercial review."]
        drawing_assumptions = []
        b64 = str(request.inputs.get("drawing_dxf_b64") or "").strip()
        if b64 or request.inputs.get("drawing_filename"):
            fname = str(request.inputs.get("drawing_filename") or "drawing.dxf")
            if not b64:
                warnings.append("A drawing name was given but no drawing file was attached, so quantities are not measured from a drawing.")
            elif not fname.lower().endswith(".dxf"):
                warnings.append(f"Drawing {fname} was not measured: only DXF drawings can be measured on this server today. Export the services drawing as DXF (DWG reading needs the Docker upgrade; PDF drawings carry no layer or size data).")
            else:
                try:
                    import base64 as _b64
                    try:
                        _cmh = float(request.inputs.get("drawing_cmh_per_diffuser") or 0) or None
                    except (TypeError, ValueError):
                        _cmh = None
                    meas = measure_dxf(fname, _b64.b64decode(b64, validate=True), units=request.inputs.get("drawing_units"), duct_cmh_per_diffuser=_cmh)
                    try:
                        repeat = float(request.inputs.get("drawing_repeat") or 1)
                    except (TypeError, ValueError):
                        repeat = 1.0
                    if repeat > 1:
                        meas.repeated(repeat)
                        meas.warnings.append(f"The drawing was drawn once and its lengths, fittings and devices were multiplied by {repeat:g} (identical floors / blocks).")
                        res["drawing_repeat"] = repeat
                    schematic = any("schematic" in w.lower() for w in meas.warnings)
                    res = apply_drawing(res, boq_lines, meas, factors=request.inputs.get("drawing_factors") if isinstance(request.inputs.get("drawing_factors"), dict) else None,
                                        show_variance=not (schematic and repeat <= 1))
                    res["drawing_measurements"] = meas.rows()
                    if meas.devices:
                        res["drawing_devices"] = [{"device": k.replace("_", " "), "count": v} for k, v in sorted(meas.devices.items())]
                    res["drawing_file"] = fname
                    res["drawing_units"] = meas.units_note
                    warnings += meas.warnings + list(res.get("drawing_notes") or [])
                    if meas.layers_ignored:
                        warnings.append("Layers not recognised as a service and not measured: " + ", ".join(meas.layers_ignored[:12]))
                    if res.get("drawing_measured_item_count"):
                        drawing_assumptions.append({"name": "drawing_takeoff_factors", "value": f"{res['drawing_measured_item_count']} BOQ item(s) measured from {fname}",
                                                    "basis": "Lengths, fittings and device counts are measured from the drawing geometry (elbows, tees and crosses from line junctions; sizes from labels). Supports, joints, couplings, wastage and bend allowances use starting factors: " + "; ".join(f"{k}={v:g}" for k, v in {**DRAWING_DEFAULTS, **{k: v for k, v in (request.inputs.get('drawing_factors') or {}).items() if k in DRAWING_DEFAULTS}}.items()) + ". Confirm for the project."})
                    else:
                        warnings.append("The drawing was read but no BOQ item matched a service on it, so no quantity was taken from it.")
                except Exception as exc:
                    warnings.append(f"The drawing could not be measured ({type(exc).__name__}); quantities come from the BOQ and recipes only.")
        prog = build_programme(res.get("boq_breakdown") or [], gangs=request.inputs.get("gangs") if isinstance(request.inputs.get("gangs"), dict) else None,
                               productivity=request.inputs.get("productivity") if isinstance(request.inputs.get("productivity"), dict) else None,
                               working_days_per_week=request.inputs.get("working_days_per_week") or 6, start_date=request.inputs.get("start_date"))
        if prog["rows"]:
            res["work_programme"] = prog["rows"]
            res["total_duration_days"] = prog["total_days"]
            res["total_duration_weeks"] = round(prog["total_days"] / prog["working_days_per_week"], 1)
            res["programme_working_days_per_week"] = prog["working_days_per_week"]
            if prog.get("finish_date"):
                res["programme_finish_date"] = prog["finish_date"]
        res["programme_items_not_scheduled"] = len(prog["skipped"]) + res["unmatched_line_count"]
        if res["unmatched_lines"]:
            warnings.append(f"{res['unmatched_line_count']} BOQ line(s) were not taken off (no recipe, bad unit or bad quantity); see the unmatched list.")
        if res["unvalidated_recipes_used"]:
            warnings.append("Consumption and wastage factors for these recipes are unvalidated defaults: " + ", ".join(res["unvalidated_recipes_used"]))
        if res.get("procure_as_specified_count"):
            warnings.append(f"{res['procure_as_specified_count']} equipment or lump-sum line(s) have no material takeoff and are listed under procure_as_specified: buy to the specification in the BOQ.")
        if res.get("ai_drafted_items"):
            warnings.append("AI-DRAFTED, UNVERIFIED: BOQ item(s) " + ", ".join(res["ai_drafted_items"]) + " had no stored recipe, so consumption and wastage were drafted by AI. An engineer must confirm these quantities before ordering.")
        trace = [
            {"step": 1, "operation": "match_recipes", "detail": f"{res['matched_line_count']} of {res['line_count']} BOQ lines matched to a recipe by description"},
            {"step": 2, "operation": "convert_units", "detail": "BOQ quantity converted to the recipe base unit (sqm/sqft, m/rft)"},
            {"step": 3, "operation": "materials", "detail": "Quantity x consumption per unit x (1 + wastage %) for each material"},
            {"step": 4, "operation": "consolidate", "detail": f"Identical material/unit pairs summed into {len(res['material_totals'])} procurement line(s)"},
        ]
        assumptions = list(drawing_assumptions)
        if prog["rows"]:
            assumptions.append({"name": "work_programme_basis", "value": f"{prog['working_days_per_week']}-day week, 1 gang per trade unless stated",
                                "basis": "Indicative programme: days = quantity / (crew output per gang-day x gangs). Next stage starts when the previous stage is 40% through. Crew output values are neutral starting figures; override with 'productivity' and 'gangs' inputs for local conditions. No prices are used."})
        assumptions += [{"name": "recipe_factors", "value": "recipe catalogue", "basis": "Consumption and wastage come from the recipe catalogue (scope_engine/catalog.yaml) or the recipes supplied with this request; confirm them for the project."}]
        return SkillResult(skill_id=self.skill_id, status="draft_ready", engineering_result=res, assumptions=assumptions,
                           warnings=warnings, calculation_trace=trace, source_revision=self.source_revision, skill_version=self.version)
