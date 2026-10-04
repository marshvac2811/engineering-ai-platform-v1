"""Production adapter for the audited duct-sizing calculator."""

from __future__ import annotations

from typing import Any, Dict

from skills.common import SkillRequest, SkillResult
from validators.basic import require_enum, require_positive
from validators.governance import resolve_assumption, resolve_standards_context, validate_governance_context
from skills.hvac.duct_sizing import source_calculator as engine

SOURCE_REVISION = "1410b71e16a4fe4b1c6b04f023291d7b0f458d68"


class DuctSizingSkill:
    skill_id = "duct_sizing"
    version = "1.2.0"

    def validate(self, request: SkillRequest) -> list[str]:
        errors: list[str] = []
        errors += validate_governance_context(request)
        airflow = request.inputs.get("flow_m3hr", request.inputs.get("airflow"))
        if airflow is None:
            errors.append("Required design airflow: provide flow_m3hr in m3/hr")
        elif not isinstance(airflow, (int, float)) or isinstance(airflow, bool) or airflow <= 0:
            errors.append("Input flow_m3hr must be greater than zero")
        if "airflow_unit" in request.inputs:
            errors += require_enum(request.inputs, "airflow_unit", ["m3/hr", "m3/h", "m³/hr", "m³/h", "cfm"])
        errors += require_enum(request.inputs, "method", ["velocity", "equal_friction"])
        errors += require_enum(request.inputs, "duct_type", ["round", "rectangular"])

        method = request.inputs.get("method")
        duct_type = request.inputs.get("duct_type")

        if duct_type == "rectangular":
            has_width = request.inputs.get("width_mm") is not None
            has_height = request.inputs.get("height_mm") is not None
            if has_width != has_height:
                errors.append("Rectangular existing-duct check requires both width_mm and height_mm")
            elif has_width and has_height:
                errors += require_positive(request.inputs, ["width_mm", "height_mm"])
            elif method == "velocity":
                errors += require_positive(request.inputs, ["target_velocity_ms"])
            elif method == "equal_friction":
                errors += require_positive(request.inputs, ["target_friction_pa_per_m"])
        elif method == "velocity":
            errors += require_positive(request.inputs, ["target_velocity_ms"])
        elif method == "equal_friction":
            errors += require_positive(request.inputs, ["target_friction_pa_per_m"])

        material = request.inputs.get("material", "gss")
        if material not in engine.DUCT_MATERIALS:
            errors.append(
                f"Invalid material: {material}. Allowed: {', '.join(sorted(engine.DUCT_MATERIALS))}"
            )
        return errors

    def run(self, request: SkillRequest) -> SkillResult:
        errors = self.validate(request)
        if errors:
            return SkillResult(
                skill_id=self.skill_id,
                status="input_validation_failed",
                validation_errors=errors,
                source_revision=SOURCE_REVISION,
            )

        inputs = request.inputs
        airflow = float(inputs.get("flow_m3hr", inputs.get("airflow")))
        airflow_unit = str(inputs.get("airflow_unit", "cfm")).strip().lower()
        airflow_unit_aliases = {
            "m3/hr": "m3/hr",
            "m3/h": "m3/hr",
            "m³/hr": "m3/hr",
            "m³/h": "m3/hr",
            "cfm": "cfm",
        }
        normalized_airflow_unit = airflow_unit_aliases.get(airflow_unit)
        if normalized_airflow_unit is None:
            return SkillResult(
                skill_id=self.skill_id,
                status="input_validation_failed",
                validation_errors=[
                    "Invalid airflow_unit. Allowed values: m3/hr, m3/h, m³/hr, m³/h, cfm"
                ],
                source_revision=SOURCE_REVISION,
            )
        if normalized_airflow_unit == "m3/hr":
            flow_m3hr = airflow
            airflow_cfm = airflow / 1.6990107955
        else:
            airflow_cfm = airflow
            flow_m3hr = airflow_cfm * 1.6990107955
        material = inputs.get("material", "gss")
        roughness_mm = engine.DUCT_MATERIALS[material]["roughness_mm"]
        method = inputs["method"]
        duct_type = inputs["duct_type"]

        air_density = resolve_assumption("duct.air_density.source_default", override_context=request.assumptions_context)
        air_viscosity = resolve_assumption("duct.air_dynamic_viscosity.source_default", override_context=request.assumptions_context)
        effective_air_density = float(air_density["value"])
        effective_air_viscosity = float(air_viscosity["value"])

        try:
            if duct_type == "round":
                if method == "velocity":
                    result = engine.size_duct_velocity_method(
                        flow_m3hr, float(inputs["target_velocity_ms"]), roughness_mm,
                        effective_air_density, effective_air_viscosity
                    )
                else:
                    result = engine.size_duct_equal_friction_method(
                        flow_m3hr, float(inputs["target_friction_pa_per_m"]), roughness_mm,
                        effective_air_density, effective_air_viscosity
                    )
            else:
                if inputs.get("width_mm") is not None and inputs.get("height_mm") is not None:
                    result = engine.calculate_rectangular_equivalent(
                        float(inputs["width_mm"]),
                        float(inputs["height_mm"]),
                        flow_m3hr,
                    )
                elif method == "velocity":
                    # Preliminary rectangular sizing when dimensions are not supplied:
                    # use a governed 1:1 aspect-ratio starting point and round up to
                    # a practical 50 mm fabrication increment. This is sizing, not
                    # an existing-duct check; final dimensions remain subject to review.
                    q_m3s = flow_m3hr / 3600.0
                    area_m2 = q_m3s / float(inputs["target_velocity_ms"])
                    side_mm = (area_m2 ** 0.5) * 1000.0
                    recommended_side_mm = int(((side_mm + 49.999) // 50) * 50)
                    actual_area_m2 = (recommended_side_mm / 1000.0) ** 2
                    actual_velocity = q_m3s / actual_area_m2
                    d_eq_mm = 1.30 * ((recommended_side_mm * recommended_side_mm) ** 0.625) / ((2 * recommended_side_mm) ** 0.25)
                    actual_friction = engine.pressure_loss_per_m(
                        actual_velocity, d_eq_mm / 1000.0, roughness_mm,
                        effective_air_density, effective_air_viscosity
                    )
                    result = {
                        "method": "Velocity Method — Rectangular Sizing",
                        "flow_m3hr": flow_m3hr,
                        "target_velocity_ms": float(inputs["target_velocity_ms"]),
                        "required_area_m2": round(area_m2, 6),
                        "required_side_mm": round(side_mm, 1),
                        "recommended_width_mm": recommended_side_mm,
                        "recommended_height_mm": recommended_side_mm,
                        "actual_area_m2": round(actual_area_m2, 6),
                        "actual_velocity_ms": round(actual_velocity, 2),
                        "equivalent_diameter_mm": round(d_eq_mm, 1),
                        "actual_friction_pa_per_m": round(actual_friction, 3),
                        "sizing_assumption": "1:1 rectangular aspect ratio; dimensions rounded up to 50 mm increment because no aspect ratio was supplied.",
                    }
                else:
                    raise ValueError("For rectangular equal-friction sizing, existing width_mm and height_mm are currently required")
        except (ValueError, KeyError, ZeroDivisionError) as exc:
            return SkillResult(
                skill_id=self.skill_id,
                status="calculation_failed",
                validation_errors=[str(exc)],
                source_revision=SOURCE_REVISION,
            )

        warnings = [
            "Source defaults are air density 1.2 kg/m³ and viscosity 1.81e-5 Pa·s; explicit governed overrides are supported.",
            "Material roughness values are typical reference values and are not manufacturer-specific.",
            "Rectangular sizing without supplied dimensions uses a preliminary 1:1 aspect-ratio assumption and 50 mm upward rounding; verify the final aspect ratio, standard size, fittings and system pressure before design release.",
            "Fitting equivalent-length ratios are typical reference values.",
            "Output is preliminary and requires engineering review before design release.",
        ]
        if method == "equal_friction" and duct_type == "round":
            warnings.append("Source equal-friction solver searches a fixed 20 mm to 3000 mm diameter bracket.")
        if material in {"fabric", "flexible"}:
            warnings.append("Selected material has source roughness assumptions that should be verified against the actual product.")
        if not request.standards_context.get("standards"):
            warnings.append("No governed standards context was supplied; standard-dependent review remains pending.")
        assumptions = [
            {**air_density, "parameter": "air_density", "unit": "kg/m3"},
            {**air_viscosity, "parameter": "air_dynamic_viscosity", "unit": "Pa.s"},
            {"parameter": "duct_roughness", "value": roughness_mm, "unit": "mm", "source": "source_material_reference", "material": material},
        ]
        standards = resolve_standards_context(request.standards_context)

        trace = [
            {"step": 1, "operation": "normalize_airflow", "input": airflow, "input_unit": normalized_airflow_unit, "output": round(flow_m3hr, 6), "output_unit": "m3/hr"},
            {"step": 2, "operation": "select_material_roughness", "material": material, "roughness_mm": roughness_mm},
            {"step": 3, "operation": "resolve_governance", "standards_count": len(standards)},
            {"step": 4, "operation": "execute_source_calculator", "function": self._source_function_name(duct_type, method)},
        ]

        return SkillResult(
            skill_id=self.skill_id,
            status="draft_ready",
            engineering_result={
                **result,
                "input_airflow": airflow,
                "input_airflow_unit": normalized_airflow_unit,
                "input_airflow_m3hr": round(flow_m3hr, 6),
                "input_airflow_cfm": round(airflow_cfm, 6),
            },
            assumptions=assumptions,
            standards=standards,
            warnings=warnings,
            calculation_trace=trace,
            human_review_required=True,
            source_revision=SOURCE_REVISION,
        )

    @staticmethod
    def _source_function_name(duct_type: str, method: str) -> str:
        if duct_type == "rectangular":
            return "calculate_rectangular_equivalent"
        if method == "velocity":
            return "size_duct_velocity_method"
        return "size_duct_equal_friction_method"
