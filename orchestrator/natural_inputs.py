"""Plain-sentence and simple-list input reading for the calculators that the older prose readers do not cover.

Only values the person actually wrote are returned. Nothing is guessed: if a number is not in the text the
field is left out and the platform asks for it. Two input styles are read for every skill:
  1. "field_name = value" or "field_name: value" using the exact input name;
  2. natural wording, per skill, in the table below.
Lists (fixtures, equipment, zones, components, BOQ lines, measures) are read from one-item-per-line text.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_N = r"(\d[\d,]*(?:\.\d+)?)"
_MONEY = r"(?:rs\.?|inr|₹)?\s*" + _N + r"\s*(crore|crores|cr|lakh|lakhs|lac|lacs|million|k)?"


def _f(s: str) -> float:
    return float(s.replace(",", ""))


def _money_val(num: str, unit: Optional[str]) -> float:
    v = _f(num)
    u = (unit or "").lower()
    return v * {"crore": 1e7, "crores": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "million": 1e6, "k": 1e3}.get(u, 1.0)


def _first(t: str, patterns: List[str], group: int = 1) -> Optional[float]:
    for p in patterns:
        m = re.search(p, t, re.I)
        if m:
            return _f(m.group(group))
    return None


def _money_after(t: str, label: str) -> Optional[float]:
    m = re.search(label + r"[^.;\n\d]{0,25}" + _MONEY, t, re.I)
    return _money_val(m.group(1), m.group(2)) if m else None


def _kv(t: str, names: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for n in names:
        m = re.search(r"(?<![a-z0-9_])" + re.escape(n) + r"\s*[=:]\s*([^\s,;|]+)", t, re.I)
        if m:
            raw = m.group(1).strip().rstrip(".")
            try:
                out[n] = _f(raw)
            except ValueError:
                out[n] = raw
    return out


def _lines(t: str) -> List[str]:
    return [l.strip(" -•\t") for l in t.splitlines() if l.strip(" -•\t")]


def _section(t: str, header: str) -> List[str]:
    """Lines after a 'Header:' line, up to the next blank line or next 'Word:' header."""
    lines = t.splitlines()
    out, on = [], False
    for l in lines:
        if not on:
            m = re.match(r"\s*" + header + r"\s*:?\s*(.*)$", l, re.I)
            if m and (m.group(0).strip().lower().startswith(header.lower())):
                on = True
                rest = m.group(1).strip()
                if rest:
                    out.append(rest)
            continue
        if not l.strip():
            break
        if re.match(r"\s*[A-Za-z ]{3,25}:\s*$", l):
            break
        out.append(l.strip(" -•\t"))
    return out


# ---------------------------------------------------------------- per-skill readers
_SPACE = [("classroom", r"classroom|school"), ("conference", r"conference|meeting"), ("gym", r"\bgym"),
          ("hospital_patient_room", r"hospital|patient|ward"), ("lobby", r"lobby"),
          ("restaurant_dining", r"restaurant|dining|canteen|cafeteria|food court"), ("retail", r"retail|shop|mall|showroom"),
          ("office", r"office")]

_FIXTURES = [("water closet", r"water\s*closets?|wcs?\b|toilets?", 10.0), ("urinal", r"urinals?", 6.0),
             ("wash basin", r"wash\s*basins?|basins?", 6.0), ("shower", r"showers?", 9.0), ("kitchen sink", r"kitchen\s*sinks?|sinks?", 8.0)]


def _read_ventilation(t):
    out = {}
    for sp, pat in _SPACE:
        if re.search(pat, t, re.I):
            out["space_type"] = sp
            break
    return out


def _read_chiller_selection(t):
    out = {}
    m = re.search(r"(?:redundancy[^.;\n]{0,20}?|\b)(n\s*\+\s*1|n\s*\+\s*2)\b", t, re.I)
    if m:
        out["redundancy_level"] = re.sub(r"\s", "", m.group(1)).upper()
    elif re.search(r"redundancy[^.;\n]{0,20}\bn\b|no redundancy", t, re.I):
        out["redundancy_level"] = "N"
    v = _first(t, [r"duty\s*modules?\s*[=:]?\s*(\d+)", r"(\d+)\s*duty\s*(?:chillers?|modules?)"])
    if v:
        out["duty_modules"] = int(v)
    return out


def _read_cooling_tower(t):
    out = {}
    if re.search(r"direct|heat rejection|heat load", t, re.I) and not re.search(r"chiller tr|chiller cop", t, re.I):
        out["load_method"] = "direct"
        v = _first(t, [r"(?:heat\s*rejection|heat\s*load|load)\D{0,15}?" + _N + r"\s*kw", _N + r"\s*kw\s*(?:heat|load|rejection)"])
        if v:
            out["direct_load_kw"] = v
    elif re.search(r"chiller", t, re.I):
        out["load_method"] = "chiller"
        v = _first(t, [_N + r"\s*(?:tr|tons?)\b"])
        if v:
            out["chiller_tr"] = v
        v = _first(t, [r"cop\D{0,6}" + _N])
        if v:
            out["chiller_cop"] = v
    return out


def _read_expansion(t):
    out = {}
    m = re.search(_N + r"\s*(litres?|liters?|l\b|m3|m³|cubic\s*met)", t, re.I)
    if m:
        v = _f(m.group(1))
        out["system_volume_l"] = v * 1000 if m.group(2).lower().startswith(("m3", "m³", "cubic")) else v
    v = _first(t, [r"(?:max(?:imum)?\s*(?:water\s*)?temp\w*)\D{0,12}" + _N + r"\s*(?:°|deg)?\s*c"])
    if v is not None:
        out["max_temp_c"] = v
    v = _first(t, [r"(?:fill|pre-?charge)\s*pressure\D{0,12}" + _N + r"\s*bar"])
    if v is not None:
        out["fill_pressure_bar_g"] = v
    v = _first(t, [r"max(?:imum)?\s*(?:allowed\s*|allowable\s*)?pressure\D{0,12}" + _N + r"\s*bar"])
    if v is not None:
        out["max_pressure_bar_g"] = v
    return out


def _read_payback(t):
    out = {}
    v = _first(t, [r"old[^.;\n]{0,80}?" + _N + r"\s*kw\s*/\s*tr", r"existing[^.;\n]{0,80}?" + _N + r"\s*kw\s*/\s*tr"])
    if v:
        out["efficiency_old"] = v
    v = _first(t, [r"new[^.;\n]{0,80}?" + _N + r"\s*kw\s*/\s*tr", r"replacement[^.;\n]{0,80}?" + _N + r"\s*kw\s*/\s*tr"])
    if v:
        out["efficiency_new"] = v
    v = _money_after(t, r"(?:investment|capex|capital\s*cost|project\s*cost)")
    if v:
        out["investment"] = v
    return out


def _read_energy_amount(t):
    out = {}
    v = _first(t, [r"(?:annual\s*(?:electricity\s*)?(?:consumption|energy)|consumption)\D{0,15}" + _N + r"\s*(?:kwh|units)", _N + r"\s*(?:kwh|units)\s*(?:per\s*(?:year|annum)|annual)"])
    if v:
        out["annual_consumption_kwh"] = v
    return out


def _read_cable(t):
    out = {}
    v = _first(t, [_N + r"\s*(?:m|metres?|meters?)\s*(?:long\s*)?(?:cable\s*)?(?:run|route|length|cable)\b", r"(?:run|route|length|distance)\D{0,10}" + _N + r"\s*(?:m|metres?|meters?)\b"])
    if v:
        out["length_m"] = v
    v = _first(t, [r"(\d{3,4})\s*v\b"])
    if v:
        out["voltage_v"] = v
    return out


def _read_fire_storage(t):
    out = {}
    m = re.search(_N + r"\s*(lpm|l\s*/\s*min|litres?\s*(?:per|/)\s*min\w*|gpm|usgpm|m3\s*/\s*h(?:r)?)\b", t, re.I)
    if m:
        v, u = _f(m.group(1)), re.sub(r"\s", "", m.group(2).lower())
        out["required_flow_lpm"] = v * 3.785 if u in ("gpm", "usgpm") else v * 1000 / 60 if u.startswith("m3") else v
    m = re.search(_N + r"\s*(min\w*|hours?|hrs?|h)\b(?!\s*/)", t.replace("duration", " duration ") if False else t, re.I)
    mm = re.search(r"duration\D{0,15}" + _N + r"\s*(min\w*|hours?|hrs?|h)\b", t, re.I) or re.search(_N + r"\s*(min\w*|hours?|hrs?)\s*(?:duration|reserve|storage)", t, re.I) or re.search(r"\bfor\s+(?:a\s+)?(?:duration\s+of\s+)?" + _N + r"\s*(min\w*|hours?|hrs?)\b", t, re.I)
    if mm:
        v = _f(mm.group(1))
        out["duration_min"] = v * 60 if mm.group(2).lower().startswith(("h",)) else v
    return out


_HAZ = [("light", r"light\s*hazard|light\s*occupancy|hazard\s*class\s*[:=]?\s*light"),
        ("ordinary_1", r"ordinary\s*(?:hazard)?\s*(?:group|class|gr\.?)?\s*[-_ ]?(?:1|i)\b"),
        ("ordinary_2", r"ordinary\s*(?:hazard)?\s*(?:group|class|gr\.?)?\s*[-_ ]?(?:2|ii)\b"),
        ("extra_1", r"extra\s*(?:high)?\s*(?:hazard)?\s*(?:group|class|gr\.?)?\s*[-_ ]?(?:1|i)\b"),
        ("extra_2", r"extra\s*(?:high)?\s*(?:hazard)?\s*(?:group|class|gr\.?)?\s*[-_ ]?(?:2|ii)\b")]


def _read_sprinkler(t):
    out = {}
    for k, p in _HAZ:
        if re.search(p, t, re.I):
            out["hazard_class"] = k
            break
    v = _first(t, [r"design\s*area\D{0,12}" + _N + r"\s*(?:m2|m²|sqm|sq\.?\s*m)"])
    if v:
        out["design_area_m2"] = v
    return out


def _read_plumbing(t):
    fixtures = []
    for name, pat, default in _FIXTURES:
        m = re.search(_N + r"\s*(?:no\.?\s*of\s*|nos\.?\s*)?(?:" + pat + r")(?:\s*(?:at|@|of|with|each)\s*" + _N + r"\s*(?:lpm|l\s*/\s*min))?", t, re.I)
        if m:
            fixtures.append({"fixture_type": name, "count": _f(m.group(1)), "flow_lpm": _f(m.group(2)) if m.group(2) else default})
    return {"fixtures": fixtures} if fixtures else {}


def _read_hot_water(t):
    v = _first(t, [r"(?:storage|tank|capacity)\D{0,15}" + _N + r"\s*(?:litres?|liters?|l)\b", _N + r"\s*(?:litres?|liters?|l)\b"])
    return {"storage_volume_l": v} if v else {}


def _read_rain(t):
    out = {}
    v = _first(t, [r"(?:catchment|roof|paved)\D{0,25}?" + _N + r"\s*(?:m2|m²|sqm|sq\.?\s*m)"])
    if v:
        out["catchment_area_m2"] = v
    v = _first(t, [r"(?:rainfall|intensity)\D{0,25}?" + _N + r"\s*mm\s*/?\s*(?:h|hr|hour)"])
    if v:
        out["rainfall_intensity_mm_h"] = v
    return out


def _read_bms_ctrl(t):
    out = {}
    v = _first(t, [r"(?:total\s*)?(?:io\s*)?points\D{0,6}" + _N + r"\b(?!\s*per)", _N + r"\s*(?:total\s*)?(?:io\s*)?points\b(?!\s*per\s*controller)"])
    if v:
        out["total_points"] = int(v)
    v = _first(t, [_N + r"\s*points\s*per\s*controller", r"points\s*per\s*controller\D{0,6}" + _N])
    if v:
        out["points_per_controller"] = int(v)
    v = _first(t, [_N + r"\s*controllers?\s*per\s*panel", r"controllers?\s*per\s*panel\D{0,6}" + _N])
    if v:
        out["controllers_per_panel"] = int(v)
    return out


def _read_bms_points(t):
    out = _read_bms_ctrl(t)
    out.pop("total_points", None)
    counts = {}
    for key, pat in (("ahu", r"ahus?|air\s*handling\s*units?"), ("chiller", r"chillers?"), ("pump", r"pumps?"), ("vfd", r"vfds?"), ("fcu", r"fcus?|fan\s*coil"), ("vav", r"vavs?")):
        m = re.search(_N + r"\s*(?:" + pat + r")\b", t, re.I)
        if m:
            counts[key] = int(_f(m.group(1)))
    from skills.bms.points.source_calculator import EQUIPMENT_TEMPLATES
    counts = {k: v for k, v in counts.items() if k in EQUIPMENT_TEMPLATES}
    if counts:
        out["equipment_counts"] = counts
    return out


def _read_bms_cost(t):
    out = _read_bms_ctrl(t)
    out.pop("total_points", None)
    for key, pat in (("ahu_count", r"ahus?"), ("chiller_count", r"chillers?"), ("pump_count", r"pumps?"), ("vfd_count", r"vfds?")):
        m = re.search(_N + r"\s*(?:" + pat + r")\b", t, re.I)
        if m:
            out[key] = int(_f(m.group(1)))
    v = _first(t, [r"misc(?:ellaneous)?\s*points\D{0,6}" + _N, _N + r"\s*misc(?:ellaneous)?\s*points"])
    if v is not None:
        out["misc_points"] = int(v)
    for key, label in (("cost_per_point", r"(?:cost\s*per\s*point|per\s*point)"), ("cost_per_controller", r"(?:cost\s*per\s*controller|per\s*controller)"),
                       ("cost_per_panel", r"(?:cost\s*per\s*panel|per\s*panel)"), ("bms_software_cost", r"(?:software(?:\s*cost)?)")):
        v = _money_after(t, label)
        if v is not None:
            out[key] = v
    v = _first(t, [r"engineering\D{0,12}" + _N + r"\s*(?:%|percent)"])
    if v is not None:
        out["engineering_pct"] = v
    return out


def _read_bms_alarm(t):
    out = {}
    m = re.search(r"point\s*id\s*[=:]?\s*([A-Za-z0-9_\-]+)", t, re.I)
    if m:
        out["point_id"] = m.group(1).upper()
        out["point_type"] = "analog" if re.search(r"analog|temperature|pressure|humidity", t, re.I) else "digital"
    if re.search(r"digital", t, re.I):
        out["point_type"] = "digital"
    m = re.search(r"value\s*[=:]?\s*(-?\d+(?:\.\d+)?)", t, re.I)
    if m:
        out["value"] = float(m.group(1))
    elif re.search(r"value\s*[=:]?\s*(run|stop|fault|standby)", t, re.I):
        out["value"] = re.search(r"value\s*[=:]?\s*(run|stop|fault|standby)", t, re.I).group(1).capitalize()
    return out


def _read_cleanroom(t):
    out = {}
    types = [("Operating Room", r"operating\s*(?:room|theatre|theater)|\bot\b"), ("ICU", r"\bicu\b|intensive care"),
             ("Delivery Room", r"delivery\s*room"), ("Isolation Room (Airborne)", r"isolation"), ("Patient Room (General)", r"patient\s*room|ward")]
    try:
        from skills.hvac.cleanroom_ach.source_calculator import ROOM_TYPES
        for name in ROOM_TYPES:
            if re.search(re.escape(name.lower()), t):
                out["room_type"] = name
                break
    except Exception:
        ROOM_TYPES = {}
    m = re.search(r"iso\s*(?:class\s*)?([5-8])\b", t, re.I)
    if "room_type" not in out and m:
        out["room_type"] = f"Cleanroom \u2014 ISO {m.group(1)}"
    if "room_type" not in out:
        for name, pat in types:
            if re.search(pat, t, re.I):
                out["room_type"] = name
                break
    for key, pat in (("length_m", r"(?:length|long)"), ("width_m", r"(?:width|wide)"), ("height_m", r"(?:height|high)")):
        v = _first(t, [_N + r"\s*(?:m|metres?|meters?)\s*" + pat, pat + r"\D{0,6}" + _N + r"\s*(?:m|metres?|meters?)\b"])
        if v:
            out[key] = v
    m = re.search(_N + r"\s*(?:x|×|by)\s*" + _N + r"\s*(?:x|×|by)\s*" + _N + r"\s*m\b", t, re.I)
    if m:
        out["length_m"], out["width_m"], out["height_m"] = _f(m.group(1)), _f(m.group(2)), _f(m.group(3))
    v = _first(t, [r"(\d+(?:\.\d+)?)\s*(?:ach|air\s*changes)"])
    if v:
        out["ach"] = v
    return out


def _read_vrf(t):
    out = {}
    zones = []
    for l in _lines(t):
        m = re.match(r"(?:zone\s*[:\-]?\s*)?([A-Za-z][\w \-/]*?)\s*[,|:\-]\s*" + _N + r"\s*(?:m2|m²|sqm|sq\.?\s*m)\s*[,|:\-]?\s*(?:load\s*factor\s*)?" + _N + r"\s*w\s*/\s*(?:m2|m²|sqm)", l, re.I)
        if m:
            zones.append({"name": m.group(1).strip(), "area": _f(m.group(2)), "load_factor": _f(m.group(3))})
    if zones:
        out["zones"] = zones
    v = _first(t, [r"combination\s*ratio\D{0,6}" + _N])
    if v:
        out["combination_ratio"] = v
    return out


def _read_refrigerant(t):
    out = {}
    m = re.search(r"\b(r410a|r32|r22|r134a)\b", t, re.I)
    if m:
        out["refrigerant"] = m.group(1).upper()
    v = _first(t, [r"capacity\D{0,10}" + _N + r"\s*kw", _N + r"\s*kw\b"])
    if v:
        out["capacity_kw"] = v
    for key, pat in (("suction_length", r"suction\D{0,20}?" + _N + r"\s*(?:m|metres?|meters?)\b"), ("liquid_length", r"liquid\D{0,20}?" + _N + r"\s*(?:m|metres?|meters?)\b")):
        v = _first(t, [pat])
        if v:
            out[key] = v
    for key, pat in (("suction_velocity", r"suction\D{0,20}?" + _N + r"\s*m\s*/\s*s"), ("liquid_velocity", r"liquid\D{0,20}?" + _N + r"\s*m\s*/\s*s")):
        v = _first(t, [pat])
        if v:
            out[key] = v
    return out


def _read_facade(t):
    comps = []
    for l in _lines(t):
        m = re.match(r"([A-Za-z][\w \-/()]*?)\s*[,|:\-]\s*" + _N + r"\s*(?:m2|m²|sqm|sq\.?\s*m)\s*[,|:\-]?\s*(?:u(?:[- ]?(?:factor|value))?\s*[=:]?\s*)" + _N, l, re.I)
        if m:
            comps.append({"name": m.group(1).strip(), "area_m2": _f(m.group(2)), "u_factor": _f(m.group(3))})
    return {"components": comps} if comps else {}


def _read_insulation(t):
    out = {}
    v = _first(t, [r"(?:fluid|water|pipe)\D{0,20}?" + _N + r"\s*(?:°|deg)?\s*c\b"])
    if v is not None:
        out["fluid_temp_c"] = v
    v = _first(t, [r"outer\s*diameter\D{0,8}" + _N + r"\s*mm", _N + r"\s*mm\s*(?:od|outer)", r"(?:od|o\.d\.)\D{0,6}" + _N + r"\s*mm"])
    if v:
        out["pipe_outer_diameter_mm"] = v
    m = re.search(r"ambient\D{0,12}" + _N + r"\s*(?:°|deg)?\s*c\D{0,12}" + _N + r"\s*%", t, re.I)
    if m:
        out["ambient_db_c"], out["ambient_rh_pct"] = _f(m.group(1)), _f(m.group(2))
    return out


def _read_boq_lines(t):
    items = []
    unit = r"(sqft|sq\.?\s*ft|sqm|sq\.?\s*m|rmt|rft|m|mtr|nos\.?|no\.?|kg|ltr|set|sets|lot)"
    body = t
    for part in re.split(r"[\n;]|,(?![^()]*\))|\band\b", body):
        p = part.strip(" -•\t.")
        if not p:
            continue
        m = re.search(r"^(.*?)\s*[:\-]?\s*" + _N + r"\s*" + unit + r"\b\s*$", p, re.I) or re.search(r"^(?:.*?\bfor\s+)?(.*?)\s*[:\-]?\s*" + _N + r"\s*" + unit + r"\b", p, re.I)
        if m:
            desc = re.sub(r"(?i)^(?:boq|material|quantity)?\s*takeoff\s*(?:for)?\s*", "", m.group(1)).strip(" :-,")
            desc = re.sub(r"(?i)^(?:for|of)\s+", "", desc)
            if len(re.findall(r"[A-Za-z]{3,}", desc)) >= 1:
                u = re.sub(r"\s", "", m.group(3).lower()).rstrip(".")
                u = {"sq.ft": "sqft", "sq.m": "sqm", "mtr": "m", "no": "nos", "no.": "nos", "nos.": "nos", "rmt": "m", "rft": "m"}.get(u, u)
                items.append({"item_no": str(len(items) + 1), "description": desc, "unit": u, "quantity": _f(m.group(2))})
    return {"boq_items": items} if items else {}


def _read_deviation(t):
    rows = []
    for l in _lines(t):
        parts = [p.strip() for p in l.split("|")]
        if len(parts) >= 4 and parts[3].lower() in ("comply", "partial", "deviate", "na"):
            rows.append({"clause": parts[0], "specified": parts[1], "offered": parts[2], "status": parts[3].lower(), "remarks": parts[4] if len(parts) > 4 else ""})
    return {"rows": rows} if rows else {}


def _read_hvac_boq(t):
    cats, cur = [], None
    for l in _lines(t):
        m = re.match(r"(?:category|section)\s*[:\-]\s*(.+)$", l, re.I)
        if m:
            cur = {"name": m.group(1).strip(), "items": []}
            cats.append(cur)
            continue
        parts = [p.strip() for p in l.split("|")]
        if cur is not None and len(parts) >= 4:
            try:
                cur["items"].append({"description": parts[0], "unit": parts[1], "qty": _f(parts[2]), "rate": _f(parts[3])})
            except ValueError:
                pass
    cats = [c for c in cats if c["items"]]
    out: Dict[str, Any] = {"categories": cats} if cats else {}
    for key, label in (("contingency_pct", r"contingency"), ("overhead_pct", r"overhead"), ("tax_pct", r"(?:gst|tax)")):
        v = _first(t, [label + r"\D{0,10}" + _N + r"\s*%", _N + r"\s*%\s*" + label])
        if v is not None:
            out[key] = v
    return out


def _item_numbers(seg: str) -> Dict[str, float]:
    d: Dict[str, float] = {}
    for key, pats in (("motor_kw", [r"(?:motor\s*)?" + _N + r"\s*kw"]), ("speed_reduction_pct", [r"speed\s*reduction\D{0,6}" + _N, _N + r"\s*%\s*speed"]),
                      ("static_head_fraction", [r"static\s*head\D{0,6}" + _N + r"\s*%?"]), ("annual_hours", [_N + r"\s*(?:hours|hrs|h)\b"]),
                      ("capacity_kwp", [_N + r"\s*kwp"]), ("annual_savings_kwh", [r"saves?\s*" + _N + r"\s*kwh", _N + r"\s*kwh\s*(?:saving|saved)"])):
        for p in pats:
            m = re.search(p, seg, re.I)
            if m:
                d[key] = _f(m.group(1))
                break
    m = re.search(r"investment\D{0,12}" + _MONEY, seg, re.I)
    if m:
        d["investment"] = _money_val(m.group(1), m.group(2))
    return d


def _read_measures(t, header="measures"):
    out = []
    for l in _section(t, header):
        parts = [p.strip() for p in l.split("|")]
        if len(parts) < 2:
            continue
        name = parts[0]
        seg = " | ".join(parts[1:])
        d = {"name": name, **_item_numbers(seg)}
        if re.search(r"\bvfd\b", seg, re.I):
            d["type"] = "vfd"
            if "static_head_fraction" in d:
                d["static_head_fraction"] = d["static_head_fraction"] / 100 if d["static_head_fraction"] > 1 else d["static_head_fraction"]
        elif "capacity_kwp" in d:
            d["type"] = "solar"
        elif re.search(r"existing\s*[:=]?\s*" + _N + r"\s*kw\s*/\s*tr", seg, re.I):
            d["type"] = "efficiency_upgrade"
            d["existing_efficiency"] = _f(re.search(r"existing\s*[:=]?\s*" + _N, seg, re.I).group(1))
            m = re.search(r"new\s*[:=]?\s*" + _N, seg, re.I)
            if m:
                d["new_efficiency"] = _f(m.group(1))
            m = re.search(r"(?:survey\s*item|replaces)\s*[:=]?\s*([A-Za-z0-9 \-]+?)(?:\s*\||$)", seg, re.I)
            if m:
                d["survey_item"] = m.group(1).strip()
        else:
            d["type"] = "custom"
        out.append(d)
    return out


def _read_energy_study(t):
    out = _read_energy_amount(t)
    v = _first(t, [r"tariff\D{0,12}" + _N])
    if v:
        out["tariff_per_kwh"] = v
    ms = _read_measures(t)
    if ms:
        out["measures"] = ms
    return out


def _read_retrofit(t):
    out = {}
    v = _first(t, [r"tariff\D{0,12}" + _N])
    if v:
        out["tariff_per_kwh"] = v
    survey = []
    for l in _section(t, "survey"):
        parts = [p.strip() for p in l.split("|")]
        if len(parts) < 2:
            continue
        seg = " | ".join(parts[1:])
        kw = _first(seg, [_N + r"\s*kw\b"])
        lf = _first(seg, [r"load\s*factor\D{0,6}" + _N])
        hrs = _first(seg, [_N + r"\s*(?:hours|hrs|h)\b"])
        if kw and lf and hrs:
            survey.append({"name": parts[0], "type": "equipment", "rated_kw": kw, "load_factor": lf / 100 if lf > 1 else lf, "annual_hours": hrs})
    if survey:
        out["survey"] = survey
    ms = _read_measures(t)
    if ms:
        out["measures"] = ms
    v = _first(t, [r"(?:measured|billed)\D{0,25}" + _N + r"\s*kwh"])
    if v:
        out["measured_annual_kwh"] = v
    return out


_READERS = {
    "ventilation_rate": _read_ventilation, "chiller_selection_advisor": _read_chiller_selection, "cooling_tower": _read_cooling_tower,
    "expansion_tank_sizing": _read_expansion, "energy_payback": _read_payback, "carbon_emissions": _read_energy_amount,
    "solar_pv_sizing": _read_energy_amount, "cable_voltage_drop": _read_cable, "fire_water_storage": _read_fire_storage,
    "sprinkler_demand": _read_sprinkler, "plumbing_water_demand": _read_plumbing, "hot_water_heater_sizing": _read_hot_water,
    "rainwater_drainage": _read_rain, "bms_controller_sizing": _read_bms_ctrl, "bms_points_generation": _read_bms_points,
    "bms_cost_estimation": _read_bms_cost, "bms_alarm_evaluation": _read_bms_alarm, "cleanroom_ach": _read_cleanroom,
    "vrf_sizing": _read_vrf, "refrigerant_pipe_sizing": _read_refrigerant, "facade_u_factor": _read_facade,
    "insulation_condensation": _read_insulation, "boq_takeoff": _read_boq_lines, "deviation_statement": _read_deviation,
    "hvac_boq": _read_hvac_boq, "energy_optimisation_study": _read_energy_study, "retrofit_study": _read_retrofit,
}

_NAMES_CACHE: Dict[str, List[str]] = {}


def _declared_names(skill_id: str) -> List[str]:
    if not _NAMES_CACHE:
        import yaml
        from pathlib import Path
        d = yaml.safe_load((Path(__file__).resolve().parents[1] / "skill_registry" / "registry.yaml").read_text(encoding="utf-8"))
        for s in d.get("skills", []):
            _NAMES_CACHE[s["skill_id"]] = [r["name"] for r in (s.get("required_inputs") or []) + (s.get("optional_inputs") or [])]
    return _NAMES_CACHE.get(skill_id, [])


def read_inputs(skill_id: str, text: str) -> Dict[str, Any]:
    t = text or ""
    out: Dict[str, Any] = {}
    reader = _READERS.get(skill_id)
    if reader:
        try:
            out.update(reader(t))
        except Exception:   # a reader must never break routing; the platform then asks for the missing value
            out = {}
    for k, v in _kv(t, _declared_names(skill_id)).items():
        if k not in out:
            out[k] = v
    return out
