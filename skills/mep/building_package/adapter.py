from __future__ import annotations

import base64
import binascii

from skills.common import SkillRequest, SkillResult
from engineering.building_mep.design import design_building
from engineering.building_mep.boq import generate_boq
from engineering.building_mep.schedule import floors_from_text, read_plan_image, PlanReadError
from skills.commercial.boq_takeoff.programme import build_programme

_HVAC_KEYS = ("cfm_per_tr", "target_velocity_ms", "diversity_factor_pct", "fan_pressure_pa", "chw_delta_t_c", "outdoor_db_c", "outdoor_rh_pct", "room_db_c", "room_rh_pct")


class MEPBuildingPackageSkill:
    skill_id = "mep_building_package"
    version = "1.0.0"
    source_revision = "internal-governed-2026-10-19"

    def _floors(self, i):
        """Returns (floors, plan_notes). plan_notes is non-empty only when the rooms came from an AI-read plan image."""
        if isinstance(i.get("floors"), list) and i["floors"]:
            return i["floors"], []
        if str(i.get("floors_text") or i.get("rooms_text") or "").strip():
            fl = floors_from_text(str(i.get("floors_text") or i.get("rooms_text")), int(float(i.get("floor_count") or 1)))
            return fl, []
        b64 = str(i.get("plan_image_b64") or "").strip()
        if b64:
            try:
                data = base64.b64decode(b64, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("The plan image could not be decoded; attach it again as PNG or JPG")
            mime = str(i.get("plan_mime") or "image/png")
            if "pdf" in mime.lower():
                raise ValueError("PDF plans cannot be read yet; attach the plan as a PNG or JPG image, or send the room list as text")
            read = read_plan_image(data, mime)
            fc = int(float(i.get("floor_count") or 0))
            if fc and len(read["floors"]) == 1 and read["floors"][0]["count"] == 1:
                read["floors"][0]["count"] = fc
            notes = ["Rooms and areas below were READ FROM THE PLAN BY AI and are NOT confirmed. An engineer must check every room and area against the plan before this is used."] + read["issues"]
            self._plan_floor_height = read.get("floor_height_m")
            return read["floors"], notes
        return [], []

    def validate(self, request: SkillRequest):
        i = request.inputs
        errors = []
        if not i.get("building_type"):
            errors.append("Missing required input: building_type")
        try:
            floors, _ = self._floors(i)
        except (ValueError, PlanReadError) as exc:
            return [str(exc)]
        if not floors:
            errors.append("Provide floors (list of {name, count, rooms}), or floors_text (a 'Floor: Typical floor x5' line followed by one room per line with area and unit), or a plan image (plan_image_b64)")
        for key in _HVAC_KEYS + ("floor_height_m", "floor_count"):
            if i.get(key) not in (None, ""):
                try:
                    float(i[key])
                except (TypeError, ValueError):
                    errors.append(f"{key} must be numeric")
        return errors

    def run(self, request: SkillRequest) -> SkillResult:
        errors = self.validate(request)
        if errors:
            return SkillResult(skill_id=self.skill_id, status="input_validation_failed", validation_errors=errors,
                               source_revision=self.source_revision, skill_version=self.version)
        i = request.inputs
        floors, plan_notes = self._floors(i)
        kwargs = {k: float(i[k]) for k in _HVAC_KEYS if i.get(k) not in (None, "")}
        height = float(i.get("floor_height_m") or getattr(self, "_plan_floor_height", None) or 3.6)
        try:
            design = design_building(building_type=str(i["building_type"]), climate_zone=str(i.get("climate_zone") or "composite"),
                                     floors=floors, floor_height_m=height, **kwargs)
            res = generate_boq(design)
        except (ValueError, TypeError, KeyError) as exc:
            return SkillResult(skill_id=self.skill_id, status="calculation_failed", validation_errors=[str(exc)],
                               source_revision=self.source_revision, skill_version=self.version)
        prog = build_programme(res.get("boq_breakdown") or [])
        if prog["rows"]:
            res["work_programme"] = prog["rows"]
            res["total_duration_days"] = prog["total_days"]
            res["total_duration_weeks"] = round(prog["total_days"] / prog["working_days_per_week"], 1)
            res["programme_working_days_per_week"] = prog["working_days_per_week"]
        summary = {k: design[k] for k in ("building_type", "floors_total", "total_area_m2", "floor_height_m")}
        res.update({"building_summary": summary, "floor_schedule": design["floors"], "hvac_summary": design["hvac"],
                    "plumbing_summary": design["plumbing"], "fire_summary": design["fire"], "electrical_summary": design["electrical"],
                    "room_schedule_by_floor": [{"floor": f["name"], "repeat": f["count"], "room": r.get("name"), "area_m2": r.get("area_m2"), "occupancy": r.get("occupancy"),
                                                "area_source": r.get("area_source", "stated")} for f in floors for r in f["rooms"]]})
        warnings = plan_notes + list(design["limitations"])
        if res.get("procure_as_specified_count"):
            warnings.append(f"{res['procure_as_specified_count']} equipment or lump-sum item(s) are listed in the procure-as-specified list: buy to the BOQ specification.")
        trace = [{"step": 1, "operation": "design_building", "detail": f"{design['floors_total']} floor(s), {design['total_area_m2']} sqm: HVAC, plumbing, fire and electrical quantity model"},
                 {"step": 2, "operation": "generate_boq", "detail": f"{res['line_count']} BOQ lines generated and taken off into {len(res['material_totals'])} material lines"}]
        return SkillResult(skill_id=self.skill_id, status="draft_ready", engineering_result=res, assumptions=design["assumptions"],
                           warnings=warnings, calculation_trace=trace, source_revision=self.source_revision, skill_version=self.version)
