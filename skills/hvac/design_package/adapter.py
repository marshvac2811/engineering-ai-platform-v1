from __future__ import annotations
from skills.common import SkillRequest, SkillResult
from engineering.building.schedule import extract_room_schedule
from skills.hvac.design_package import design_package


class HVACDesignPackageSkill:
    skill_id = "hvac_design_package"
    version = "1.0.0"
    source_revision = "internal-governed-2026-10-10"

    @staticmethod
    def _rooms(i):
        if isinstance(i.get("rooms"), list) and i["rooms"]:
            return i["rooms"]
        if str(i.get("rooms_text") or "").strip():
            return [{"room_id": f"R{n}", "name": r["name"], "area_m2": r["area_m2"],
                     **({"occupancy": r["occupancy"]} if r.get("occupancy") is not None else {})}
                    for n, r in enumerate(extract_room_schedule(str(i["rooms_text"]))["rooms"], 1)]
        return []

    def validate(self, request: SkillRequest) -> list[str]:
        i = request.inputs
        errors = []
        for key in ("building_type", "climate_zone"):
            if not i.get(key):
                errors.append(f"Missing required input: {key}")
        rooms = self._rooms(i)
        if not rooms:
            errors.append("rooms must be a non-empty list of {room_id, name, area_m2[, occupancy]}, or rooms_text containing rows with a room name and an area with unit")
        for key in ("cfm_per_tr", "target_velocity_ms", "diversity_factor_pct", "fan_pressure_pa", "chw_delta_t_c", "outdoor_db_c", "outdoor_rh_pct", "room_db_c", "room_rh_pct"):
            if key in i and i[key] is not None:
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
        kwargs = {}
        for key in ("cfm_per_tr", "target_velocity_ms", "diversity_factor_pct", "fan_pressure_pa", "chw_delta_t_c", "outdoor_db_c", "outdoor_rh_pct", "room_db_c", "room_rh_pct"):
            if i.get(key) is not None:
                kwargs[key] = float(i[key])
        if i.get("duct_material"):
            kwargs["duct_material"] = str(i["duct_material"])
        try:
            result = design_package(building_type=str(i["building_type"]), climate_zone=str(i["climate_zone"]),
                                    rooms=self._rooms(i), **kwargs)
        except (ValueError, TypeError, KeyError) as exc:
            return SkillResult(skill_id=self.skill_id, status="calculation_failed", validation_errors=[str(exc)],
                               source_revision=self.source_revision, skill_version=self.version)
        n = result["room_count"]
        trace = [
            {"step": 1, "operation": "estimate_room_cooling_loads", "detail": f"Benchmark load per room for {n} room(s) ({result['building_type']}, {result['climate_zone']}); sum = {result['sum_of_room_loads_tr']} TR"},
            {"step": 2, "operation": "apply_diversity", "detail": f"{result['sum_of_room_loads_tr']} TR x {result['diversity_factor_pct']:g}% = block load {result['block_load_tr']} TR"},
            {"step": 3, "operation": "derive_supply_airflow", "detail": "Room load (TR) x airflow basis (CFM/TR) converted to m3/h; total " + f"{result['total_supply_airflow_m3h']:,.0f} m3/h"},
            {"step": 4, "operation": "size_room_branch_ducts", "detail": "Round duct by velocity method per room using the governed duct-sizing calculator"},
            {"step": 5, "operation": "assemble_equipment_schedule", "detail": f"Terminal class per room and plant suggestion: {result['plant_equipment_suggestion']}"},
            {"step": 6, "operation": "plant_summary", "detail": f"Block load {result['block_load_kw']} kW -> chilled water {result['plant_summary']['chilled_water_flow_m3h']} m3/h, header DN{result['plant_summary']['chilled_water_header_dn']}; fan motors total {result['plant_summary']['total_fan_motor_kw']} kW"},
        ]
        return SkillResult(skill_id=self.skill_id, status="draft_ready", engineering_result=result,
                           assumptions=result["assumptions"], warnings=result["limitations"], calculation_trace=trace,
                           source_revision=self.source_revision, skill_version=self.version)
