"""Client information forms, one per executable skill, built from the skill registry.

A form lists what the client must provide (required) and may provide (optional) so that the
skill can run. The text is plain language for the client; it never mentions how results are calculated.
"""
from __future__ import annotations

import re
from typing import Any

from orchestrator.registry_loader import load_registry


def _title(skill_id: str) -> str:
    return skill_id.replace("_", " ").strip().capitalize()


# Wording for fields whose registry description is written for developers or is structured data.
LABELS: dict[str, str] = {
    "rooms": "Room list: room name, floor area (sq m) and number of people in each room",
    "floors": "Floor list: for each floor type, how many floors, and each room's name, area (sq m) and number of people",
    "zones": "Zone list: zone name, area (sq m) and cooling load per sq m for each zone",
    "boq_items": "Bill of quantities: item number, description, unit and quantity for each item",
    "boq_csv": "Bill of quantities as a spreadsheet (item number, description, unit, quantity)",
    "categories": "Bill of quantities by category: item, unit, quantity and rate",
    "rows": "Deviation list: item, specified requirement and offered alternative",
    "components": "Facade components: type, area (sq m) and U-factor of each",
    "sections": "Duct test sections: area and measured leakage of each",
    "measures": "Improvement measures to compare: name, type and investment cost of each",
    "survey": "Existing equipment list: name, type, rated power (kW), load, running hours per year and age",
    "load_factor_pct": "Average load as a percentage of full load",
    "required_flow_lpm": "Required fire water flow (L/min), if specified by your consultant or authority",
    "duration_min": "Required fire water duration (minutes), if specified",
    "method": "Preferred method, if you have one",
    "load_method": "Is the load known directly (kW) or from a chiller?",
    "mode": "What do you want assessed",
    "material": "Material",
    "fittings": "Fittings in the line and how many of each",
    "margin_pct": "Spare capacity you want to allow, %",
    "ach": "Air changes per hour required, if specified",
    "value": "Current reading",
    "space_type": "Type of space (office, conference, lobby, retail, classroom, restaurant, gym, hospital room)",
    "hazard_class": "Fire hazard class (light, ordinary 1, ordinary 2, extra 1, extra 2)",
    "diameter_mm": "Pipe inside diameter (mm)",
}
LABELS.update({
    "building_type": "Building type (office, hospital, hotel, school, retail, etc.)",
    "range_c": "Cooling water temperature range (°C)",
    "wet_bulb_c": "Design wet-bulb temperature (°C)",
    "approach_c": "Required approach temperature (°C)",
    "total_load_tr": "Total cooling load (TR)",
    "efficiency_kw_per_tr": "Chiller efficiency (kW per TR)",
    "annual_hours": "Running hours per year",
    "tariff_per_kwh": "Electricity tariff (per kWh)",
    "redundancy_level": "Standby required (none, N+1 or N+2)",
    "total_points": "Total number of control points",
    "equipment_counts": "Equipment counts: how many AHUs, chillers, pumps, VFDs, etc.",
    "ahu_count": "Number of AHUs", "chiller_count": "Number of chillers", "pump_count": "Number of pumps",
    "vfd_count": "Number of VFDs", "misc_points": "Other control points",
    "point_type": "Type of point (temperature, pressure, status, etc.)", "point_id": "Point name or tag",
    "motor_kw": "Motor rating (kW)", "speed_reduction_pct": "Expected speed reduction, %",
    "static_head_fraction": "Static head as a fraction of total head (0 to 1)",
    "ambient_temp_c": "Ambient temperature at the drive (°C)", "altitude_m": "Site altitude (m)",
    "total_vfd_kva": "Total VFD rating (kVA)", "transformer_kva": "Transformer rating (kVA)",
    "capacity_old": "Existing plant capacity (TR)", "efficiency_old": "Existing plant efficiency (kW per TR)",
    "capacity_new": "Proposed plant capacity (TR)", "efficiency_new": "Proposed plant efficiency (kW per TR)",
    "investment": "Investment cost",
    "cop_100": "Chiller COP at 100% load", "cop_75": "Chiller COP at 75% load",
    "cop_50": "Chiller COP at 50% load", "cop_25": "Chiller COP at 25% load",
    "test_pressure_pa": "Duct test pressure (Pa)", "measured_leakage_ls": "Measured leakage (L/s)",
    "target_class": "Leakage class required",
    "load": "Cooling or heating load (kW or TR)",
    "fixtures": "Fixtures: type, quantity and flow rate of each",
    "tariff_per_kwh_any": "Electricity tariff per kWh",
    "values": "Measured readings from the equipment",
    "rule_id": "Fault you want checked",
})
LABELS["tariff_per_kwh"] = "Electricity tariff (per kWh)"
# Engineering settings we choose ourselves. They stay in the form spec but are not asked of the client.
ENGINEER_FILLS = {"margin_pct", "coc", "drift_pct", "combination_ratio", "points_per_controller", "controllers_per_panel",
                  "cost_per_point", "cost_per_controller", "cost_per_panel", "bms_software_cost", "engineering_pct",
                  "rule_id", "static_head_fraction", "efficiency_new_default"}
# Optional inputs a client can reasonably supply. All other optional inputs are engineering settings we handle.
CLIENT_OPTIONAL = {"material", "fittings", "altitude_m", "space_type", "climate_zone", "floor_height_m",
                   "voltage_v", "power_factor", "water_temp_c", "length_m", "min_temp_c", "cold_water_c",
                   "hot_water_c", "rows", "sections", "boq_items", "floors"}
# Skills whose real requirement is "this or that": the client-facing input is promoted to required.
PROMOTE = {"boq_takeoff": {"boq_items"}, "mep_building_package": {"floors"}}
_CUT = re.compile(r"\s*(\(default|, default|; |\. Deterministic|\. Supply|\. Each zone| - validated)", re.I)
_INTERNAL = re.compile(r"deterministic|governed|source-ref|engine|internal|validated|[a-z]+_[a-z_]+", re.I)


def _label(spec: dict[str, Any]) -> str:
    name = str(spec.get("name", ""))
    if name in LABELS:
        return LABELS[name]
    text = str(spec.get("description") or name.replace("_", " "))
    text = _CUT.split(text)[0].rstrip(". ")
    if _INTERNAL.search(text):
        text = name.replace("_", " ").capitalize()
    return text.replace("?C", "°C")


def _field(spec: dict[str, Any], required: bool) -> dict[str, Any]:
    name = str(spec.get("name", ""))
    out = {
        "key": name,
        "label": _label(spec),
        "type": spec.get("data_type", "string"),
        "required": required,
        "client": name not in ENGINEER_FILLS,
    }
    if name == "tariff_per_kwh":
        out["label"] = LABELS["tariff_per_kwh"]
    if spec.get("allowed_values"):
        out["choices"] = [str(c).replace("_", " ") for c in spec["allowed_values"]]
    if spec.get("unit"):
        out["unit"] = spec["unit"]
    return out


def form_for(skill_id: str) -> dict[str, Any] | None:
    for s in load_registry().get("skills", []):
        if s.get("skill_id") == skill_id and "required_inputs" in s:
            fields = [_field(f, True) for f in s.get("required_inputs", [])]
            fields += [_field(f, False) for f in s.get("optional_inputs", []) or [] if f.get("name") in CLIENT_OPTIONAL]
            for f in fields:
                if f["key"] in PROMOTE.get(skill_id, ()):
                    f["required"] = True
            return {"skill_id": skill_id, "title": _title(skill_id), "domain": s.get("domain"), "fields": fields}
    return None


def all_forms() -> list[dict[str, Any]]:
    out = []
    for s in load_registry().get("skills", []):
        if "required_inputs" in s:
            f = form_for(s["skill_id"])
            if f:
                out.append(f)
    return out


def render_text(form: dict[str, Any], client_name: str = "") -> str:
    """Plain-text reply asking the client for the details, ready for the owner to approve and send."""
    greet = f"Dear {client_name}," if client_name else "Dear Sir/Madam,"
    lines = [greet, "", f"Thank you for your enquiry. To proceed with the {form['title'].lower()} work we need the following details.", "", "Required:"]
    for f in form["fields"]:
        if f["required"] and f.get("client", True):
            extra = f" (choose one: {', '.join(map(str, f['choices']))})" if f.get("choices") else ""
            lines.append(f"  - {f['label']}{extra}")
    opt = [f for f in form["fields"] if not f["required"] and f.get("client", True)]
    if opt:
        lines += ["", "If available:"]
        for f in opt:
            extra = f" (choose one: {', '.join(map(str, f['choices']))})" if f.get("choices") else ""
            lines.append(f"  - {f['label']}{extra}")
    lines += ["", "Drawings, specifications or photographs, if you have them, will help.", "", "Regards,", "Mars Engineering Solutions"]
    return "\n".join(lines)


def new_skill_needed(jobs) -> list[dict[str, Any]]:
    """Requests that matched no skill: the list to bring to the engineer-builder.

    A job counts when it is waiting for information and the orchestrator selected no skill and planned no work.
    """
    out = []
    for j in jobs:
        d = j if isinstance(j, dict) else j.to_dict()
        orch = d.get("orchestration") or {}
        if str(d.get("status")) not in ("awaiting_information", "JobStatus.AWAITING_INFORMATION"):
            continue
        if orch.get("selected_skill_id") or orch.get("work_items"):
            continue
        out.append({
            "job_id": d.get("job_id"),
            "request": orch.get("normalized_request") or "",
            "source": d.get("source"),
            "created_at": d.get("created_at"),
            "project": (d.get("project_context") or {}).get("project"),
            "client": (d.get("project_context") or {}).get("client"),
        })
    return out
