from __future__ import annotations
import re
from typing import Any, Dict

# Common engineering-language aliases. These normalize wording; they do not
# decide whether an input is required or safe to assume.
ALIASES = {
    "flow_m3hr": ["design water flow", "water flow", "design flow", "flow rate", "circulation flow"],
    "diameter_mm": ["pipe internal diameter", "pipe diameter", "internal diameter", "nominal diameter", "pipe dia"],
    "straight_length_m": ["total straight pipe length", "straight pipe length", "pipe length", "pipeline length", "pipe run"],
    "static_head_m": ["static head", "static elevation", "elevation head", "static lift", "static/elevation head"],
    "margin_pct": ["design margin", "design allowance", "margin", "allowance"],
    "roughness_mm": ["pipe roughness", "roughness"],
    "airflow": ["airflow", "air flow", "air volume", "air quantity"],
    "area_sqft": ["building area", "floor area", "area"],
    "width_mm": ["duct width", "width"],
    "height_mm": ["duct height", "height"],
    "target_velocity_ms": ["target velocity", "air velocity", "design velocity"],
    "target_friction_pa_per_m": ["target friction rate", "friction rate", "friction loss rate"],
    "wet_bulb_c": ["wet bulb", "wet-bulb temperature", "entering wet bulb"],
    "approach_c": ["cooling tower approach", "approach temperature", "approach"],
    "range_c": ["cooling tower range", "temperature range", "range"],
    "ambient_temp_c": ["ambient temperature", "ambient temp"],
    "altitude_m": ["site altitude", "altitude", "elevation above sea level"],
    "annual_hours": ["annual hours", "operating hours", "hours per year"],
    "load_factor_pct": ["load factor", "loading factor"],
    "speed_reduction_pct": ["speed reduction", "speed reduction percentage"],
    "motor_kw": ["motor power", "motor rating", "motor capacity"],
    "pump_efficiency_pct": ["pump efficiency", "pump hydraulic efficiency"],
    "supply_temp_c": ["supply temperature", "supply water temperature"],
    "return_temp_c": ["return temperature", "return water temperature"],
    "capacity_kw": ["cooling capacity", "capacity in kw"],
    "total_load_tr": ["total cooling load", "cooling load"],
    "chiller_tr": ["chiller capacity", "chiller load"],
    "efficiency_kw_per_tr": ["chiller efficiency", "efficiency kw/tr", "kw per tr"],
    "combination_ratio": ["combination ratio", "vrf combination ratio"],
    "annual_energy_kwh": ["annual energy", "annual energy consumption", "yearly energy"],
    "tariff_per_kwh": ["electricity tariff", "energy tariff", "power tariff"],
    "investment": ["investment", "project investment", "capital investment", "capex"],
    "engineering_pct": ["engineering percentage", "engineering fee"],
    "total_vfd_kva": ["total vfd load", "vfd load"],
    "transformer_kva": ["transformer capacity", "transformer rating"],
    "test_pressure_pa": ["test pressure"],
    "measured_leakage_ls": ["measured leakage", "leakage flow"],
}

UNIT_PATTERNS = {
    "flow_m3hr": r"m3/hr|m3/h|m³/hr|m³/h|l/s|l/sec|l/min|lpm|gpm",
    "airflow": r"cfm|m3/hr|m3/h|m³/hr|m³/h|l/s",
    "diameter_mm": r"mm|m|in|inch|inches",
    "straight_length_m": r"m|metres?|ft|feet",
    "static_head_m": r"m|metres?|ft|feet",
    "roughness_mm": r"mm|m",
    "width_mm": r"mm|m",
    "height_mm": r"mm|m",
    "target_velocity_ms": r"m/s|mps|ft/s",
    "target_friction_pa_per_m": r"pa/m|pa\s*/\s*m",
    "wet_bulb_c": r"°?c|deg c|°?f|deg f",
    "approach_c": r"°?c|deg c|°?f|deg f",
    "range_c": r"°?c|deg c|°?f|deg f",
    "ambient_temp_c": r"°?c|deg c|°?f|deg f",
    "altitude_m": r"m|metres?|ft|feet",
    "area_sqft": r"sq\.?\s*ft|sqft|square\s*feet|m2|m²",
    "test_pressure_pa": r"pa|kpa|bar",
    "measured_leakage_ls": r"l/s|lps|ls",
    "motor_kw": r"kw|w",
    "pump_efficiency_pct": r"%|percent",
    "supply_temp_c": r"°?c|deg c|°?f|deg f",
    "return_temp_c": r"°?c|deg c|°?f|deg f",
}

def _label_pattern(labels):
    return "(?:" + "|".join(re.escape(x) for x in sorted(labels, key=len, reverse=True)) + ")"

def _convert(field: str, value: float, unit: str) -> float:
    u = unit.lower().replace("³", "3").replace("²", "2").replace(" ", "")
    if field == "flow_m3hr":
        if "l/s" in u or "l/sec" in u: return value * 3.6
        if "l/min" in u or "lpm" in u: return value * 0.06
        if "gpm" in u: return value * 0.2271247
    if field == "airflow":
        if "m3/h" in u: return value * 0.588578
        if "l/s" in u: return value * 2.11888
    if field.endswith("_mm"):
        if u in ("m", "metre", "meter", "metres", "meters"): return value * 1000
        if u in ("in", "inch", "inches"): return value * 25.4
    if field.endswith("_m") and field != "flow_m3hr":
        if u == "mm": return value / 1000
        if u in ("ft", "feet"): return value * 0.3048
    if field.endswith("_c") and u in ("f", "°f"): return (value - 32) * 5 / 9
    if field == "area_sqft" and u in ("m2", "m²"): return value * 10.7639
    return value

def normalize_engineering_inputs(text: str) -> Dict[str, Any]:
    text = " ".join(str(text or "").split())
    out: Dict[str, Any] = {}
    for field, aliases in ALIASES.items():
        units = UNIT_PATTERNS.get(field)
        if not units:
            continue
        labels = _label_pattern(aliases)
        pattern = rf"(?<![a-z]){labels}(?:\s*(?:is|are|of|at|=|:))?\s*([\d,.]+)\s*({units})(?![a-z])"
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        value = _convert(field, float(m.group(1).replace(",", "")), m.group(2))
        out[field] = int(value) if value.is_integer() else value

    for field in ("margin_pct", "speed_reduction_pct", "load_factor_pct", "engineering_pct", "combination_ratio", "static_head_fraction"):
        labels = _label_pattern(ALIASES.get(field, [field]))
        m = re.search(rf"(?<![a-z]){labels}(?:\s+(?:is|are|of|at|=|:))?\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:%|percent)?\b", text, re.IGNORECASE)
        if m:
            value = float(m.group(1).replace(",", ""))
            out[field] = int(value) if value.is_integer() else value
    return out
