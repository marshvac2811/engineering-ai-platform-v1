from __future__ import annotations
from skills.common import SkillRequest, SkillResult
from skills.energy.retrofit import retrofit_study


class RetrofitStudySkill:
    skill_id = "retrofit_study"
    version = "1.0.0"
    source_revision = "internal-governed-2026-10-14"

    def validate(self, request: SkillRequest):
        i = request.inputs
        errors = []
        if i.get("tariff_per_kwh") in (None, ""):
            errors.append("Missing required input: tariff_per_kwh")
        for k, what in (("survey", "existing plant items {name, type, rated_kw, load_factor, annual_hours}"),
                        ("measures", "retrofit options {name, type, investment, ...}")):
            if not isinstance(i.get(k), list) or not i.get(k):
                errors.append(f"{k} must be a non-empty list of {what}")
        for k in ("tariff_per_kwh", "measured_annual_kwh", "grid_factor_kg_kwh"):
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
        if i.get("measured_annual_kwh") not in (None, ""):
            kw["measured_annual_kwh"] = float(i["measured_annual_kwh"])
        try:
            res = retrofit_study(tariff_per_kwh=float(i["tariff_per_kwh"]), survey=i["survey"], measures=i["measures"], **kw)
        except (ValueError, TypeError, KeyError) as exc:
            return SkillResult(skill_id=self.skill_id, status="calculation_failed", validation_errors=[str(exc)],
                               source_revision=self.source_revision, skill_version=self.version)
        extra = res.pop("_warnings")
        rec = res["baseline_reconciliation"]
        assumptions = [
            {"name": "baseline", "value": rec["baseline_used"],
             "basis": "Measured annual consumption supplied by the user." if rec["baseline_used"] == "measured"
             else "No measured consumption supplied, so the baseline is the surveyed rated kW x load factor x hours. Supply the billed kWh to reconcile it."},
            {"name": "grid_factor_kg_kwh", "value": res["grid_factor_kg_kwh"],
             "basis": "Supplied by the user." if "grid_factor_kg_kwh" in kw else "Indicative Indian grid average; replace with the current CEA CO2 Baseline Database value."},
            {"name": "measure_interaction", "value": "none", "basis": "Each option is evaluated against the same baseline; interactions between options (e.g. VFD plus chiller replacement) are not modelled."},
            {"name": "efficiency_upgrade", "value": "same duty", "basis": "A replacement is assumed to deliver the same cooling/pumping duty at the new efficiency; part-load behaviour is not modelled."},
            {"name": "tariff_currency", "value": "as supplied", "basis": "Costs are in the currency of the tariff; no escalation or discounting."},
        ]
        warnings = extra + ["Preliminary retrofit screening, not an investment-grade audit; measure and verify before committing."]
        trace = [
            {"step": 1, "operation": "survey", "detail": f"{len(res['survey'])} existing item(s): rated kW x load factor x hours = {rec['surveyed_kwh']:,.0f} kWh/yr"},
            {"step": 2, "operation": "reconcile", "detail": "Compared with measured consumption: " + (f"{rec['gap_pct']:+.1f}%" if rec["gap_pct"] is not None else "no measured value supplied")},
            {"step": 3, "operation": "options", "detail": f"{res['measure_count']} retrofit option(s) evaluated; savings x tariff - O&M; efficiency upgrades = E x (1 - new/old)"},
            {"step": 4, "operation": "phase", "detail": "Ranked by payback and grouped into Phase 1 (<=2 y), Phase 2 (2-5 y), Phase 3 (>5 y or undefined)"},
        ]
        return SkillResult(skill_id=self.skill_id, status="draft_ready", engineering_result=res, assumptions=assumptions,
                           warnings=warnings, calculation_trace=trace, source_revision=self.source_revision, skill_version=self.version)
