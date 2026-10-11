"""Conservative plain-sentence extraction for the governed calculator catalogue.

Only unambiguous, unit-bearing values are extracted. Nothing is guessed: a value
is returned only when the sentence states it with a unit (or an unmistakable label).
"""
from __future__ import annotations
import re
from typing import Any, Dict

_NUM = r"(\d[\d,]*(?:\.\d+)?)"


def _f(x: str) -> float:
    return float(x.replace(",", ""))


def _airflow_m3h(t: str):
    m = re.search(_NUM + r"\s*(cfm|m3\s*/?\s*h(?:r)?|m³\s*/?\s*h(?:r)?|cmh|l\s*/\s*s|lps)\b", t, re.I)
    if not m:
        return None
    v, u = _f(m.group(1)), re.sub(r"\s", "", m.group(2).lower())
    if u == "cfm":
        return round(v * 1.699011, 3)
    if u in {"l/s", "lps"}:
        return round(v * 3.6, 3)
    return v


def _flow_water_m3h(t: str):
    m = re.search(_NUM + r"\s*(gpm|usgpm|m3\s*/?\s*h(?:r)?|m³\s*/?\s*h(?:r)?|l\s*/\s*s|lps|l\s*/\s*min|lpm)\b", t, re.I)
    if not m:
        return None
    v, u = _f(m.group(1)), re.sub(r"\s", "", m.group(2).lower())
    if u in {"gpm", "usgpm"}:
        return round(v * 0.227125, 3)
    if u in {"l/s", "lps"}:
        return round(v * 3.6, 3)
    if u in {"l/min", "lpm"}:
        return round(v * 0.06, 3)
    return v


def _pressure_pa(t: str):
    m = re.search(r"(?:static|pressure|esp|tsp|head)\D{0,25}?" + _NUM + r"\s*(pa|kpa|mmwg|mm\s*wg|inwg|in\s*wg)\b", t, re.I)
    if not m:
        m = re.search(_NUM + r"\s*(pa|kpa|mmwg|mm\s*wg|inwg|in\s*wg)\s*(?:static|pressure|esp|tsp)", t, re.I)
    if not m:
        return None
    v, u = _f(m.group(1)), re.sub(r"\s", "", m.group(2).lower())
    return {"pa": v, "kpa": v * 1000, "mmwg": v * 9.80665, "inwg": v * 249.089}[u]


def _length_m(t: str):
    m = (re.search(r"(?:length|long|run|distance)\D{0,15}?" + _NUM + r"\s*(m|metres?|meters?|ft|feet)\b", t, re.I)
         or re.search(_NUM + r"\s*(m|metres?|meters?|ft|feet)\s*(?:long|length|run)", t, re.I))
    if not m:
        return None
    v = _f(m.group(1))
    return round(v * 0.3048, 3) if m.group(2).lower() in {"ft", "feet"} else v


def _area_m2(t: str):
    m = re.search(_NUM + r"\s*(m2|m²|sqm|sq\.?\s*m|sqft|sq\.?\s*ft|square\s*feet|square\s*met(?:er|re)s?)\b", t, re.I)
    if not m:
        return None
    v, u = _f(m.group(1)), re.sub(r"[\s.]", "", m.group(2).lower())
    return round(v * 0.09290304, 3) if u in {"sqft", "squarefeet"} else v


def _occupants(t: str):
    m = re.search(_NUM + r"\s*(?:people|persons?|occupants?|pax|staff|seats)\b", t, re.I)
    return int(_f(m.group(1))) if m else None


def _temp_rh_pairs(t: str):
    pairs = []
    for m in re.finditer(_NUM + r"\s*(?:°|deg(?:rees?)?)?\s*c\b(?:\s*db)?[^\d%]{0,12}" + _NUM + r"\s*%\s*(?:rh)?", t, re.I):
        pairs.append((_f(m.group(1)), _f(m.group(2))))
    return pairs


def extract_catalogue_inputs(skill_id: str, text: str) -> Dict[str, Any]:
    t = text or ""
    out: Dict[str, Any] = {}
    low = t.lower()
    if skill_id in {"fan_power_sizing", "cooling_coil_load", "duct_pressure_drop"}:
        v = _airflow_m3h(t)
        if v is not None:
            out["airflow_m3h"] = v
    if skill_id == "fan_power_sizing":
        v = _pressure_pa(t)
        if v is not None:
            out["total_static_pressure_pa"] = v
    if skill_id == "duct_pressure_drop":
        v = _length_m(t)
        if v is not None:
            out["length_m"] = v
    if skill_id in {"water_pipe_sizing"}:
        v = _flow_water_m3h(t)
        if v is not None:
            out["flow_m3h"] = v
        v = _length_m(t)
        if v is not None:
            out["length_m"] = v
    if skill_id == "heat_recovery_assessment":
        v = _airflow_m3h(t)
        if v is not None:
            out["outdoor_air_m3h"] = v
        pairs = _temp_rh_pairs(t)
        if pairs:
            out["outdoor_db_c"], out["outdoor_rh_pct"] = pairs[0]
            if len(pairs) > 1:
                out["exhaust_db_c"], out["exhaust_rh_pct"] = pairs[1]
    if skill_id == "cooling_coil_load":
        pairs = _temp_rh_pairs(t)
        if pairs:
            out["entering_db_c"], out["entering_rh_pct"] = pairs[0]
            if len(pairs) > 1:
                out["leaving_db_c"], out["leaving_rh_pct"] = pairs[1]
    if skill_id == "psychrometric_properties":
        pairs = _temp_rh_pairs(t)
        if pairs:
            out["dry_bulb_c"], out["rh_pct"] = pairs[0]
    if skill_id == "ventilation_rate":
        v = _area_m2(t)
        if v is not None:
            out["floor_area_m2"] = v
        o = _occupants(t)
        if o is not None:
            out["occupants"] = o
    if skill_id in {"generator_sizing", "transformer_sizing"}:
        m = re.search(_NUM + r"\s*(kw|kva|mw)\b", t, re.I)
        if m:
            v = _f(m.group(1))
            out["connected_load_kw"] = v * 1000 if m.group(2).lower() == "mw" else v
    if skill_id == "pump_power_sizing":
        v = _flow_water_m3h(t)
        if v is not None:
            out["flow_m3h"] = v
        m = re.search(_NUM + r"\s*(m|mwc|metres?|meters?|ft|feet)\s*(?:of\s*)?(?:head|tdh)\b|(?:head|tdh)\D{0,12}?" + _NUM + r"\s*(m|mwc|metres?|meters?|ft|feet)\b", t, re.I)
        if m:
            val = m.group(1) or m.group(3)
            unit = (m.group(2) or m.group(4) or "m").lower()
            out["head_m"] = round(_f(val) * 0.3048, 3) if unit in {"ft", "feet"} else _f(val)
    if skill_id == "domestic_water_tank_sizing":
        o = _occupants(t)
        if o is not None:
            out["occupants"] = o
    if skill_id == "cable_voltage_drop":
        m = re.search(_NUM + r"\s*kw\b", t, re.I)
        if m:
            out["load_kw"] = _f(m.group(1))
        v = _length_m(t)
        if v is not None:
            out["length_m"] = v
    return out
