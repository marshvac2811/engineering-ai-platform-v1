from __future__ import annotations
from skills.common import SkillRequest, SkillResult
from skills.energy.study import energy_study


class EnergyStudySkill:
    skill_id = "energy_optimisation_study"
    version = "1.0.0"
    source_revision = "internal-governed-2026-10-10"

    def validate(self, request: SkillRequest):
        i = request.inputs
        errors = [f"Missing required input: {k}" for k in ("annual_consumption_kwh", "tariff_per_kwh") if i.get(k) in (None, "")]
        if not isinstance(i.get("measures"), list) or not i.get("measures"):
            errors.append("measures must be a non-empty list of {name, type, investment, ...}")
        for k in ("annual_consumption_kwh", "tariff_per_kwh", "grid_factor_kg_kwh"):
            if i.get(k) not in (None, ""):
                try:
                    float(i[k])
                except (TypeError, ValueError):
                    errors.append(f"{k} must be numeric")
        return errors

    def run(self, request: SkillRequest) -> SkillResult:
        errors = self.validate(request)
        if errors:
            return SkillResult(skill_id=self.skill_id, status="input_validation_failed", validation_errors=errors,
                               source_revision=self.source_revision, skill_version=self.version)
        i = request.inputs
        kw = {}
        if i.get("grid_factor_kg_kwh") not in (None, ""):
            kw["grid_factor_kg_kwh"] = float(i["grid_factor_kg_kwh"])
        try:
            res = energy_study(annual_consumption_kwh=float(i["annual_consumption_kwh"]), tariff_per_kwh=float(i["tariff_per_kwh"]),
                               measures=i["measures"], **kw)
        except (ValueError, TypeError, KeyError) as exc:
            return SkillResult(skill_id=self.skill_id, status="calculation_failed", validation_errors=[str(exc)],
                               source_revision=self.source_revision, skill_version=self.version)
        extra = res.pop("_warnings")
        assumptions = [
            {"name": "grid_factor_kg_kwh", "value": res["grid_factor_kg_kwh"],
             "basis": "Supplied by the user." if "grid_factor_kg_kwh" in kw else "Indicative Indian grid average; replace with the current CEA CO2 Baseline Database value."},
            {"name": "measure_interaction", "value": "none", "basis": "Each measure is evaluated independently against the same baseline; interactions are not modelled."},
            {"name": "tariff_currency", "value": "as supplied", "basis": "Costs are in the currency of the tariff; no escalation or discounting is applied."},
        ]
        warnings = extra + ["Preliminary screening study, not an investment-grade audit; savings need measurement and verification before commitments."]
        n = res["measure_count"]
        trace = [
            {"step": 1, "operation": "baseline", "detail": f"{res['baseline_consumption_kwh']:,.0f} kWh x {res['grid_factor_kg_kwh']} kg/kWh = {res['baseline_scope2_tco2e']} tCO2e"},
            {"step": 2, "operation": "measure_savings", "detail": f"{n} measure(s): saving kWh from governed calculators or user-supplied values; cost = kWh x tariff - O&M"},
            {"step": 3, "operation": "payback_and_rank", "detail": "Simple payback = investment / net annual saving; measures ranked by payback"},
            {"step": 4, "operation": "combine", "detail": f"Combined saving {res['combined_saving_kwh']:,.0f} kWh ({res['combined_saving_pct_of_baseline']}% of baseline); residual {res['residual_scope2_tco2e']} tCO2e"},
        ]
        return SkillResult(skill_id=self.skill_id, status="draft_ready", engineering_result=res, assumptions=assumptions,
                           warnings=warnings, calculation_trace=trace, source_revision=self.source_revision, skill_version=self.version)
