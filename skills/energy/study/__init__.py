"""Energy optimisation and decarbonisation study (preliminary).

Composes governed calculators: VFD affinity-law savings, solar PV sizing and the carbon estimate, plus
user-supplied measures, into one ranked measure list with cost, payback and avoided CO2e. Nothing is
invented: every measure needs an explicit saving (or inputs that produce one) and an investment cost.
Interactions between measures are not modelled; the total is only capped at the baseline consumption.
"""
from __future__ import annotations

from typing import Any, Dict, List

from skills.calculators import formulas as F
from skills.energy.vfd import source_calculator as vfd

MEASURE_TYPES = ("vfd", "solar", "custom")


def _num(m: Dict[str, Any], key: str, name: str, *, minimum: float = 0.0, default: float | None = None) -> float:
    v = m.get(key, default)
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"Measure '{name}': {key} is required and must be numeric")
    if x < minimum:
        raise ValueError(f"Measure '{name}': {key} must be >= {minimum:g}")
    return x


def _saving_kwh(m: Dict[str, Any], name: str, tariff: float) -> tuple[float, str]:
    t = str(m.get("type", "custom")).lower()
    if t == "vfd":
        o = vfd.calculate_energy_savings(motor_kw=_num(m, "motor_kw", name, minimum=0.001),
                                         speed_reduction_pct=_num(m, "speed_reduction_pct", name),
                                         static_head_fraction=_num(m, "static_head_fraction", name),
                                         annual_hours=_num(m, "annual_hours", name, minimum=1),
                                         tariff_per_kwh=tariff)
        return float(o["annual_savings_kwh_corrected"]), "VFD affinity-law saving with static-head correction (governed VFD calculator)"
    if t == "solar":
        yld = _num(m, "specific_yield_kwh_kwp_yr", name, default=1500)
        if m.get("capacity_kwp") not in (None, ""):
            kwp = _num(m, "capacity_kwp", name, minimum=0.001)
        else:
            raise ValueError(f"Measure '{name}': capacity_kwp is required for a solar measure")
        return kwp * yld, f"{kwp:g} kWp x {yld:g} kWh/kWp/yr yield (default 1500 unless supplied; no degradation or shading)"
    if t == "custom":
        return _num(m, "annual_savings_kwh", name, minimum=0.001), "Annual saving supplied by the user"
    raise ValueError(f"Measure '{name}': unknown type '{t}' (use {', '.join(MEASURE_TYPES)})")


def energy_study(*, annual_consumption_kwh: float, tariff_per_kwh: float, measures: List[Dict[str, Any]],
                 grid_factor_kg_kwh: float = 0.71) -> Dict[str, Any]:
    if annual_consumption_kwh <= 0 or tariff_per_kwh <= 0:
        raise ValueError("annual_consumption_kwh and tariff_per_kwh must be greater than zero")
    if not measures:
        raise ValueError("measures must be a non-empty list")
    rows, seen = [], set()
    for n, m in enumerate(measures, 1):
        name = str(m.get("name") or f"Measure {n}")
        if name in seen:
            raise ValueError(f"Duplicate measure name: {name}")
        seen.add(name)
        kwh, basis = _saving_kwh(m, name, tariff_per_kwh)
        invest = _num(m, "investment", name)
        om = _num(m, "annual_om", name, default=0.0)
        gross = kwh * tariff_per_kwh
        net = gross - om
        rows.append({
            "measure": name, "type": str(m.get("type", "custom")).lower(), "annual_saving_kwh": round(kwh, 0),
            "annual_cost_saving": round(gross, 0), "annual_om": round(om, 0), "net_annual_saving": round(net, 0),
            "investment": round(invest, 0),
            "simple_payback_years": round(invest / net, 2) if net > 0 and invest > 0 else (0.0 if invest == 0 and net > 0 else None),
            "avoided_tco2e_per_year": round(kwh * grid_factor_kg_kwh / 1000, 2), "basis": basis,
        })
    rows.sort(key=lambda r: (r["simple_payback_years"] is None, r["simple_payback_years"] or 0))
    for rank, r in enumerate(rows, 1):
        r["rank_by_payback"] = rank
    total_kwh = sum(r["annual_saving_kwh"] for r in rows)
    warnings = []
    capped = min(total_kwh, annual_consumption_kwh)
    if total_kwh > annual_consumption_kwh:
        warnings.append("Sum of measure savings exceeds baseline consumption; the combined saving is capped at the baseline. Check for overlap between measures.")
    if any(r["simple_payback_years"] is None for r in rows):
        warnings.append("One or more measures have no positive net saving, so payback is not defined.")
    base_t = annual_consumption_kwh * grid_factor_kg_kwh / 1000
    invest_total = sum(r["investment"] for r in rows)
    net_total = sum(r["net_annual_saving"] for r in rows)
    return {
        "baseline_consumption_kwh": round(annual_consumption_kwh, 0), "tariff_per_kwh": tariff_per_kwh,
        "baseline_scope2_tco2e": round(base_t, 2), "measure_count": len(rows), "measures_ranked": rows,
        "combined_saving_kwh": round(capped, 0), "combined_saving_pct_of_baseline": round(capped / annual_consumption_kwh * 100, 1),
        "residual_consumption_kwh": round(annual_consumption_kwh - capped, 0),
        "combined_avoided_tco2e_per_year": round(capped * grid_factor_kg_kwh / 1000, 2),
        "residual_scope2_tco2e": round(base_t - capped * grid_factor_kg_kwh / 1000, 2),
        "total_investment": round(invest_total, 0), "total_net_annual_saving": round(net_total, 0),
        "portfolio_simple_payback_years": round(invest_total / net_total, 2) if net_total > 0 and invest_total > 0 else None,
        "grid_factor_kg_kwh": grid_factor_kg_kwh, "_warnings": warnings,
    }
