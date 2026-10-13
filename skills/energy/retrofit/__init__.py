"""Retrofit study (preliminary): existing-plant survey -> baseline -> upgrade options -> ranked, phased savings.

Builds on the governed energy study. Adds what a retrofit needs on top of it:
- the existing plant survey (each item: rated kW x load factor x hours = annual kWh);
- reconciliation of the surveyed baseline against the measured (billed) consumption, flagged when they differ;
- an efficiency-upgrade measure (replace a machine with a better kW/TR or kW/kW one: saving = E x (1 - new/old));
- phasing of the ranked measures by payback.
Nothing is assumed: every survey item and measure needs explicit inputs.
"""
from __future__ import annotations

from typing import Any, Dict, List

from skills.energy.study import energy_study

RECONCILE_WARN_PCT = 15.0


def _num(d: Dict[str, Any], key: str, name: str, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    try:
        x = float(d.get(key))
    except (TypeError, ValueError):
        raise ValueError(f"'{name}': {key} is required and must be numeric")
    if x < minimum or (maximum is not None and x > maximum):
        raise ValueError(f"'{name}': {key} must be between {minimum:g} and {maximum if maximum is not None else 'unlimited'}")
    return x


def survey_baseline(survey: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not survey:
        raise ValueError("survey must list at least one existing plant item")
    rows, seen = [], set()
    for n, it in enumerate(survey, 1):
        name = str(it.get("name") or f"Item {n}")
        if name in seen:
            raise ValueError(f"Duplicate survey item name: {name}")
        seen.add(name)
        kw = _num(it, "rated_kw", name, minimum=0.001)
        lf = _num(it, "load_factor", name, minimum=0.01, maximum=1.0)
        hrs = _num(it, "annual_hours", name, minimum=1, maximum=8760)
        rows.append({"item": name, "type": str(it.get("type") or "equipment"), "rated_kw": kw, "load_factor": lf,
                     "annual_hours": hrs, "annual_kwh": round(kw * lf * hrs, 0),
                     "age_years": it.get("age_years") if it.get("age_years") not in ("", None) else None,
                     "condition": str(it.get("condition") or "")})
    total = sum(r["annual_kwh"] for r in rows)
    for r in rows:
        r["share_pct"] = round(r["annual_kwh"] / total * 100, 1) if total else 0.0
    rows.sort(key=lambda r: -r["annual_kwh"])
    return {"rows": rows, "total_kwh": round(total, 0)}


def _convert_measures(measures: List[Dict[str, Any]], items: Dict[str, float]):
    out, notes = [], {}
    for n, m in enumerate(measures, 1):
        name = str(m.get("name") or f"Measure {n}")
        if str(m.get("type", "")).lower() == "efficiency_upgrade":
            ref = str(m.get("survey_item") or "")
            if ref not in items:
                raise ValueError(f"Measure '{name}': survey_item must name an item in the survey ({', '.join(items)})")
            old = _num(m, "existing_efficiency", name, minimum=0.001)   # kW per unit of output (e.g. kW/TR): lower is better
            new = _num(m, "new_efficiency", name, minimum=0.001)
            if new >= old:
                raise ValueError(f"Measure '{name}': new_efficiency ({new:g}) must be lower than existing_efficiency ({old:g}) in kW per unit of output")
            e = items[ref]
            saving = e * (1 - new / old)
            notes[name] = f"{ref}: {e:,.0f} kWh/yr x (1 - {new:g}/{old:g}) kW per unit of output, same duty (replacement, not resizing)"
            out.append({"name": name, "type": "custom", "annual_savings_kwh": saving,
                        "investment": m.get("investment"), "annual_om": m.get("annual_om", 0)})
        else:
            out.append(m)
    return out, notes


def retrofit_study(*, tariff_per_kwh: float, survey: List[Dict[str, Any]], measures: List[Dict[str, Any]],
                   measured_annual_kwh: float | None = None, grid_factor_kg_kwh: float = 0.71) -> Dict[str, Any]:
    sv = survey_baseline(survey)
    items = {r["item"]: r["annual_kwh"] for r in sv["rows"]}
    conv, notes = _convert_measures(measures, items)
    warnings: List[str] = []
    baseline = sv["total_kwh"]
    recon: Dict[str, Any] = {"surveyed_kwh": sv["total_kwh"], "measured_kwh": None, "gap_pct": None, "baseline_used": "survey"}
    if measured_annual_kwh not in (None, ""):
        meas = float(measured_annual_kwh)
        if meas <= 0:
            raise ValueError("measured_annual_kwh must be greater than zero")
        gap = (sv["total_kwh"] - meas) / meas * 100
        recon.update({"measured_kwh": round(meas, 0), "gap_pct": round(gap, 1), "baseline_used": "measured"})
        baseline = meas
        if abs(gap) > RECONCILE_WARN_PCT:
            warnings.append(f"Surveyed consumption differs from the measured bill by {gap:+.1f}% (more than {RECONCILE_WARN_PCT:g}%). "
                            "Check load factors, hours and items not surveyed before relying on the savings.")
    res = energy_study(annual_consumption_kwh=baseline, tariff_per_kwh=tariff_per_kwh, measures=conv, grid_factor_kg_kwh=grid_factor_kg_kwh)
    warnings += res.pop("_warnings")
    for r in res["measures_ranked"]:
        if r["measure"] in notes:
            r["basis"] = notes[r["measure"]]
        p = r["simple_payback_years"]
        r["phase"] = "Phase 1 (payback up to 2 years)" if p is not None and p <= 2 else \
                     "Phase 2 (payback 2 to 5 years)" if p is not None and p <= 5 else "Phase 3 (over 5 years or undefined)"
    res["survey"] = sv["rows"]
    res["baseline_reconciliation"] = recon
    res["phase_summary"] = _phases(res["measures_ranked"])
    res["_warnings"] = warnings
    return res


def _phases(rows):
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        d = out.setdefault(r["phase"], {"phase": r["phase"], "measures": 0, "investment": 0.0, "net_annual_saving": 0.0})
        d["measures"] += 1
        d["investment"] += r["investment"]
        d["net_annual_saving"] += r["net_annual_saving"]
    for d in out.values():
        d["investment"], d["net_annual_saving"] = round(d["investment"], 0), round(d["net_annual_saving"], 0)
    return sorted(out.values(), key=lambda d: d["phase"])
