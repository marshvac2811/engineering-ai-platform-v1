"""Client-readable formatting for engineering results.

Raw engineering results are dictionaries such as ``{"savings_pct_corrected": 28.9}``.
These helpers turn them into labelled, unit-aware rows so the PDF and Excel
reports show tables and numbers instead of JSON text. Nothing here changes any
calculated value; it only changes how a value is presented.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

# Unit tokens that may appear inside a key such as ``reduced_power_kw_pure``.
_UNIT_TOKENS = {
    "kw": "kW", "kwh": "kWh", "mw": "MW", "mwh": "MWh", "kva": "kVA", "kwp": "kWp",
    "pct": "%", "percent": "%",
    "m3hr": "m³/hr", "m3h": "m³/hr", "m3s": "m³/s", "cfm": "CFM", "lps": "L/s",
    "mm": "mm", "cm": "cm", "m2": "m²", "m3": "m³", "km": "km",
    "kpa": "kPa", "pa": "Pa", "bar": "bar", "psi": "psi",
    "tr": "TR", "btu": "BTU", "mj": "MJ", "gj": "GJ",
    "degc": "°C", "c": "°C", "hz": "Hz", "rpm": "rpm",
    "kg": "kg", "tco2": "tCO₂", "kgco2": "kgCO₂", "yr": "years", "years": "years",
    "ms": "m/s", "mps": "m/s", "wm2k": "W/m²K",
}
# Tokens kept in the label but written with the right capitalisation.
_ACRONYMS = {
    "hvac": "HVAC", "vfd": "VFD", "vrf": "VRF", "bms": "BMS", "cop": "COP", "eer": "EER",
    "iplv": "IPLV", "ach": "ACH", "boq": "BOQ", "ahu": "AHU", "fcu": "FCU", "co2": "CO₂",
    "ecbc": "ECBC", "nbc": "NBC", "bee": "BEE", "u": "U", "id": "ID", "o&m": "O&M", "om": "O&M",
    "roi": "ROI", "npv": "NPV", "irr": "IRR", "ppa": "PPA", "bess": "BESS", "pv": "PV",
}
_SMALL_WORDS = {"of", "and", "per", "to", "vs", "in", "at", "the"}


def _tokens(key: str) -> List[str]:
    return [t for t in str(key).replace("-", "_").replace(" ", "_").split("_") if t]


# Explicit display overrides where the generic key->label rule is ambiguous or loses the unit.
# Currency is deliberately not assumed: values are in the currency of the tariff supplied.
_DISPLAY_OVERRIDES: Dict[str, Tuple[str, str]] = {
    "motor_kw": ("Motor power", "kW"),
    "block_load_tr": ("Block cooling load", "TR"),
    "block_load_kw": ("Block cooling load", "kW"),
    "sum_of_room_loads_tr": ("Sum of room loads", "TR"),
    "total_area_m2": ("Total conditioned area", "m²"),
    "total_supply_airflow_m3h": ("Total supply airflow", "m³/hr"),
    "diversity_factor_pct": ("Diversity factor", "%"),
    "speed_reduction_pct": ("Speed reduction", "%"),
    "static_head_fraction": ("Static head fraction", "%"),
    "annual_hours": ("Annual operating hours", "hours"),
    "tariff_per_kwh": ("Electricity tariff", "currency per kWh"),
    "speed_ratio": ("Speed ratio (new / rated)", "-"),
    "savings_pct_pure": ("Energy saving - theoretical (affinity law)", "%"),
    "savings_pct_corrected": ("Energy saving - after static-head correction", "%"),
    "reduced_power_kw_pure": ("Power at reduced speed - theoretical", "kW"),
    "reduced_power_kw_corrected": ("Power at reduced speed - after static-head correction", "kW"),
    "annual_savings_kwh_pure": ("Annual energy saving - theoretical", "kWh"),
    "annual_savings_kwh_corrected": ("Annual energy saving - after static-head correction", "kWh"),
    "annual_savings_cost_pure": ("Annual cost saving - theoretical", "currency"),
    "annual_savings_cost_corrected": ("Annual cost saving - after static-head correction", "currency"),
    "plant_summary_chilled_water_flow_m3h": ("Chilled-water flow (block)", "m³/hr"),
    "plant_summary_chilled_water_flow_usgpm": ("Chilled-water flow (block)", "US gpm"),
    "plant_summary_chilled_water_delta_t_c": ("Chilled-water temperature difference", "K"),
    "plant_summary_chilled_water_header_dn": ("Chilled-water header size", "DN"),
    "plant_summary_chilled_water_header_velocity_ms": ("Header velocity", "m/s"),
    "plant_summary_chilled_water_header_friction_pa_per_m": ("Header friction", "Pa/m"),
    "plant_summary_plant_option_single_tr": ("Plant option A: one unit, nominal size", "TR"),
    "plant_summary_plant_option_two_equal_units_tr": ("Plant option B: two equal units, nominal size each", "TR"),
    "plant_summary_total_fan_motor_kw": ("Total fan motor rating (room units)", "kW"),
    "plant_summary_total_outdoor_air_l_s": ("Total outdoor air (ASHRAE 62.1)", "L/s"),
    "plant_summary_total_ventilation_load_kw_not_included": ("Ventilation load - NOT included in room loads", "kW"),
}


def split_unit(key: str) -> Tuple[str, str]:
    """Return ``(label, unit)`` for a result key, e.g. ``annual_savings_kwh`` -> (Annual Savings, kWh)."""
    if str(key) in _DISPLAY_OVERRIDES:
        return _DISPLAY_OVERRIDES[str(key)]
    tokens = _tokens(key)
    lowered = [t.lower() for t in tokens]
    unit = ""
    keep: List[str] = []
    i = 0
    while i < len(tokens):
        low = lowered[i]
        # "tariff_per_kwh" -> unit "per kWh"
        if low == "per" and i + 1 < len(tokens) and lowered[i + 1] in _UNIT_TOKENS and not unit:
            unit = "per " + _UNIT_TOKENS[lowered[i + 1]]
            i += 2
            continue
        if low in _UNIT_TOKENS and not unit and len(tokens) > 1:
            unit = _UNIT_TOKENS[low]
            i += 1
            continue
        keep.append(tokens[i])
        i += 1
    words = []
    for t in keep:
        low = t.lower()
        if low in _ACRONYMS:
            words.append(_ACRONYMS[low])
        elif low in _SMALL_WORDS and words:
            words.append(low)
        else:
            words.append(t[:1].upper() + t[1:])
    label = " ".join(words) or str(key)
    return label, unit


def humanize(text: Any) -> str:
    """Readable text for statuses and operation names, e.g. apply_affinity_law -> Apply affinity law."""
    s = str(text if text is not None else "").replace("_", " ").strip()
    if not s:
        return ""
    words = [(_ACRONYMS.get(w.lower(), w)) for w in s.split(" ")]
    s = " ".join(words)
    return s[:1].upper() + s[1:]


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def format_value(value: Any) -> str:
    """Format a scalar for display: thousands separators, sensible decimals, Yes/No."""
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return "-"
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        if value != 0 and abs(value) < 0.001:
            return f"{value:.3g}"  # keep tiny constants (e.g. 1.81e-05) visible
        text = f"{value:,.3f}".rstrip("0").rstrip(".")
        return text or "0"
    return str(value)


_LONG_TEXT = 500


def shorten_for_report(key: str, value: Any) -> Any:
    """Keep very long strings (an uploaded file as base64, a pasted schedule) out of single table cells.

    A cell taller than a page makes PDF layout fail and Excel caps cells at 32,767 characters. The complete
    value stays in the evidence record; the report shows a short note instead.
    """
    if not isinstance(value, str) or len(value) <= _LONG_TEXT:
        return value
    if str(key).lower().endswith(("_b64", "base64")) or " " not in value[:200]:
        return f"(uploaded file content, {len(value):,} characters; kept in the evidence record)"
    return value[:_LONG_TEXT].rstrip() + f" ... ({len(value):,} characters in total; full text kept in the evidence record)"


def flatten_rows(data: Dict[str, Any], prefix: str = "", path: str = "") -> List[Tuple[str, Any, str]]:
    """Flatten a (possibly nested) dict into ``(label, value, unit)`` rows.

    Lists of scalars become one comma-separated cell. Lists of dicts become one
    row per item. Nothing is dropped; nesting is shown in the label.
    """
    rows: List[Tuple[str, Any, str]] = []
    for key, value in (data or {}).items():
        label, unit = split_unit(key)
        full = f"{path}_{key}" if path else str(key)
        if path and full in _DISPLAY_OVERRIDES:      # nested keys such as plant_summary.total_outdoor_air_l_s
            label, unit = _DISPLAY_OVERRIDES[full]
        elif prefix:
            label = f"{prefix} - {label}"
        if is_scalar(value):
            rows.append((label, shorten_for_report(key, value), unit))
        elif isinstance(value, dict):
            rows.extend(flatten_rows(value, label, full))
        elif isinstance(value, (list, tuple)):
            if all(is_scalar(v) for v in value):
                rows.append((label, shorten_for_report(key, ", ".join(format_value(v) for v in value) or "-"), unit))
            else:
                for n, item in enumerate(value, 1):
                    if isinstance(item, dict):
                        rows.extend(flatten_rows(item, f"{label} {n}"))
                    else:
                        rows.append((f"{label} {n}", shorten_for_report(key, str(item)), unit))
        else:
            rows.append((label, shorten_for_report(key, str(value)), unit))
    return rows


def extract_tables(results: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Pull lists of flat dicts (schedules) out of a results dict so they render as real tables.

    Returns ``(remaining_results, tables)``; each table is ``{"title", "headers", "rows"}`` with
    values formatted for display. Nothing is dropped: only uniform lists of scalar-only dicts move.
    """
    rest: Dict[str, Any] = {}
    tables: List[Dict[str, Any]] = []
    for key, value in (results or {}).items():
        if (isinstance(value, (list, tuple)) and value and all(isinstance(v, dict) and v and all(is_scalar(x) for x in v.values()) for v in value)):
            columns: List[str] = []
            for item in value:
                for col in item:
                    if col not in columns:
                        columns.append(col)
            headers = []
            for col in columns:
                label, unit = split_unit(col)
                headers.append(f"{label} ({unit})" if unit and unit != "-" else label)
            rows = [[format_value(item.get(col)) for col in columns] for item in value]
            tables.append({"title": split_unit(key)[0], "headers": headers, "rows": rows})
        else:
            rest[key] = value
    return rest, tables


def split_inputs_and_results(inputs: Dict[str, Any], results: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return results without keys that merely echo an input value (avoids duplicate rows)."""
    inputs = inputs or {}
    only_results = {
        k: v for k, v in (results or {}).items()
        if not (k in inputs and is_scalar(v) and inputs[k] == v)
    }
    return inputs, only_results


def trace_steps(trace: Iterable[Any]) -> List[Dict[str, str]]:
    """Normalise a calculation trace (strings or dicts) into display rows."""
    steps: List[Dict[str, str]] = []
    for n, item in enumerate(trace or [], 1):
        if isinstance(item, dict):
            number = item.get("step", n)
            operation = item.get("operation") or item.get("description") or item.get("name") or ""
            extras = {k: v for k, v in item.items() if k not in {"step", "operation", "description", "name", "detail"} and is_scalar(v)}
            detail = str(item.get("detail") or "") or "; ".join(f"{split_unit(k)[0]}: {format_value(v)}" for k, v in extras.items())
            steps.append({"step": str(number), "operation": humanize(operation), "detail": detail})
        else:
            steps.append({"step": str(n), "operation": str(item), "detail": ""})
    return steps


_ASSUMPTION_LABELS = {
    "cfm_per_tr": ("Supply airflow basis", "CFM per TR"), "target_velocity_ms": ("Branch duct velocity", "m/s"),
    "duct_material": ("Duct material", ""), "diversity_factor_pct": ("Diversity factor", "%"),
    "fan_pressure_pa": ("Total fan pressure per unit", "Pa"), "chw_delta_t_c": ("Chilled-water temperature difference", "K"),
    "climate_zone": ("Climate zone", ""), "building_type": ("Building type", ""),
}
_VALUE_WORDS = {"gss": "Galvanised steel sheet", "hot_dry": "Hot and dry", "warm_humid": "Warm and humid", "composite": "Composite", "moderate": "Moderate", "cold": "Cold"}


def assumption_parts(item: Any) -> Tuple[str, str, str]:
    """(label, value, basis) for an assumption dict; plain strings become (text, '', '')."""
    if isinstance(item, dict) and any(k in item for k in ("name", "parameter", "value")):
        key = str(item.get("name") or item.get("parameter") or "assumption")
        label, unit = _ASSUMPTION_LABELS.get(key, (split_unit(key)[0], ""))
        value = format_value(item.get("value")) if item.get("value") not in (None, "") else "-"
        value = _VALUE_WORDS.get(value, value)
        if unit and value != "-":
            value = f"{value} {unit}"
        basis = str(item.get("basis") or item.get("reason") or "").strip()
        status = str(item.get("status") or "").strip()
        if status:
            basis = f"{status}. {basis}".strip()
        return label, value, basis
    return describe_item(item), "", ""


def describe_item(item: Any) -> str:
    """One readable line for an assumption/warning that may be a string or dict."""
    if isinstance(item, dict):
        parts = [f"{split_unit(k)[0]}: {format_value(v)}" for k, v in item.items() if is_scalar(v)]
        return "; ".join(parts) or "-"
    return str(item)
