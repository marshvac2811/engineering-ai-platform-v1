"""Production adapter for the audited pump-head calculator."""
from __future__ import annotations
from skills.common import SkillRequest, SkillResult
from validators.basic import require_positive
from validators.governance import resolve_assumption, resolve_standards_context, validate_governance_context
from . import source_calculator as engine

SOURCE_REVISION = "source-modified-2026-07-14T23:50:40Z"

class PumpHeadSkill:
    skill_id = "pump_head"
    version = "1.0.0"

    def validate(self, request: SkillRequest) -> list[str]:
        i = request.inputs
        errors: list[str] = []
        errors += validate_governance_context(request)
        errors += require_positive(i, ["flow_m3hr", "diameter_mm"])
        for key in ("straight_length_m", "static_head_m", "margin_pct"):
            if key not in i:
                errors.append(f"Missing required input: {key}")
            else:
                try:
                    if float(i[key]) < 0:
                        errors.append(f"{key} must be non-negative")
                except (TypeError, ValueError):
                    errors.append(f"{key} must be numeric")
        if "roughness_mm" not in i:
            material = i.get("material")
            if material not in engine.PIPE_MATERIALS:
                errors.append("Provide roughness_mm or a valid material")
        if "fittings" in i and not isinstance(i["fittings"], list):
            errors.append("fittings must be a list")
        if "equipment_losses_m" in i and not isinstance(i["equipment_losses_m"], list):
            errors.append("equipment_losses_m must be a list")
        return errors

    def run(self, request: SkillRequest) -> SkillResult:
        errors = self.validate(request)
        if errors:
            return SkillResult(skill_id=self.skill_id, status="input_validation_failed", validation_errors=errors, source_revision=SOURCE_REVISION)
        i = request.inputs
        material = i.get("material")
        roughness = float(i["roughness_mm"]) if "roughness_mm" in i else engine.PIPE_MATERIALS[material]["roughness_mm"]
        viscosity = resolve_assumption("pump.water_kinematic_viscosity.source_default", override_context=request.assumptions_context)
        gravity = resolve_assumption("pump.gravity.source_default", override_context=request.assumptions_context)
        effective_viscosity = float(viscosity["value"])
        effective_gravity = float(gravity["value"])
        try:
            result = engine.calculate(
                flow_m3hr=float(i["flow_m3hr"]),
                diameter_mm=float(i["diameter_mm"]),
                roughness_mm=roughness,
                straight_length_m=float(i["straight_length_m"]),
                fittings=i.get("fittings", []),
                static_head_m=float(i["static_head_m"]),
                equipment_losses_m=i.get("equipment_losses_m", []),
                margin_pct=float(i["margin_pct"]),
                viscosity_m2_s=effective_viscosity,
                gravity=effective_gravity,
            )
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            return SkillResult(skill_id=self.skill_id, status="calculation_failed", validation_errors=[str(exc)], source_revision=SOURCE_REVISION)

        v = result["velocity_ms"]
        standards = resolve_standards_context(request.standards_context)
        warnings = [
            "Source default water kinematic viscosity is 1.0e-6 m2/s; explicit governed overrides are supported.",
            "Pipe roughness is based on the source calculator's default/reference values unless explicitly supplied.",
            "Equipment/component losses should come from manufacturer pressure-drop data at design flow.",
            "The source recommends using resulting TDH and design flow together on the pump manufacturer's performance curve.",
            "Output is preliminary and requires engineering review before design release.",
        ]
        if v < 0.6:
            warnings.append("Source flag: velocity low — oversized pipe, sediment risk.")
        elif v > 3.0:
            warnings.append("Source flag: velocity high — noise/erosion risk above approximately 3 m/s.")
        elif not (1.0 <= v <= 2.5):
            warnings.append("Source flag: velocity is outside the displayed typical 1.0–2.5 m/s design range.")

        if not request.standards_context.get("standards"):
            warnings.append("No governed standards context was supplied; standard-dependent review remains pending.")
        return SkillResult(
            skill_id=self.skill_id,
            status="draft_ready",
            engineering_result=result,
            assumptions=[
                {**viscosity, "parameter": "water_kinematic_viscosity", "unit": "m2/s"},
                {**gravity, "parameter": "gravity", "unit": "m/s2"},
                {"parameter": "roughness", "value": roughness, "unit": "mm", "source": "source_material_default" if material else "user_input"},
            ],
            standards=standards,
            warnings=warnings,
            calculation_trace=[
                {"step": 1, "operation": "convert_units", "flow_to_m3s": float(i["flow_m3hr"]) / 3600.0, "diameter_to_m": float(i["diameter_mm"]) / 1000.0},
                {"step": 2, "operation": "calculate_velocity_reynolds_friction_factor", "method": "Darcy-Weisbach + Swamee-Jain"},
                {"step": 3, "operation": "calculate_fitting_equivalent_length"},
                {"step": 4, "operation": "calculate_friction_static_equipment_subtotal"},
                {"step": 5, "operation": "resolve_governance", "standards_count": len(standards)},
                {"step": 6, "operation": "apply_design_margin_and_unit_conversions"},
            ],
            human_review_required=True,
            source_revision=SOURCE_REVISION,
        )
