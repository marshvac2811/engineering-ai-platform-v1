"""Preliminary whole-building MEP quantity model from a confirmed multi-floor room schedule.

HVAC loads and duct sizes come from the governed hvac design package. Plumbing, fire and electrical counts use
simple per-area / per-person starter norms (NORMS below). Every norm is reported back as an assumption and is
marked unvalidated: this is a budgetary quantity model for engineer review, not a coordinated design.
Run lengths are estimated from floor area (a square footprint with one central corridor); no routing is done.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from skills.hvac.design_package import design_package, KW_PER_TR
from skills.hvac.duct_sizing import source_calculator as duct

NORMS: Dict[str, Dict[str, Any]] = {
    "layout": {"circulation_factor": (1.25, "Gross floor area = room area x factor, used only to estimate run lengths"),
               "main_duct_velocity_ms": (7.0, "Floor main supply duct velocity")},
    "people": {"sqm_per_person": (10.0, "Occupancy where not given (office-type default)"),
               "water_lpcd": (45.0, "Domestic water demand, litres per person per day (office)")},
    "plumbing": {"persons_per_wc": (25.0, "Water closets: persons per fitting"),
                 "persons_per_basin": (25.0, "Wash basins: persons per fitting"),
                 "urinal_share": (0.5, "Fraction of WCs added as urinals"),
                 "supply_m_per_fixture": (6.0, "Branch water supply pipe per fitting, m"),
                 "drain_m_per_fixture": (5.0, "Branch drain pipe per fitting, m")},
    "fire": {"sqm_per_sprinkler": (12.0, "Sprinkler head coverage (ordinary hazard)"),
             "pipe_m_per_sprinkler": (3.5, "Sprinkler pipework per head, m"),
             "sqm_per_detector": (60.0, "Smoke detector coverage"),
             "sqm_per_extinguisher": (200.0, "Portable extinguisher coverage"),
             "sqm_per_hydrant_point": (1000.0, "Landing valve and hose reel per area (minimum one per floor)")},
    "electrical": {"lighting_w_m2": (10.0, "Lighting power density"),
                   "fitting_w": (36.0, "LED panel/fitting wattage"),
                   "sqm_per_socket": (8.0, "Power socket outlets per area"),
                   "wire_m_per_point": (8.0, "Final-circuit wiring per light/socket point, m"),
                   "socket_w": (150.0, "Diversified load per socket outlet, W"),
                   "demand_factor": (0.8, "Demand factor on connected load"),
                   "power_factor": (0.9, "Power factor for kVA")},
}


def _n(group: str, key: str, over: Dict[str, Any]) -> float:
    return float(over.get(key, NORMS[group][key][0]))


def _floors(floors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, f in enumerate(floors or [], 1):
        rooms = f.get("rooms") or []
        if not rooms:
            raise ValueError(f"Floor {f.get('name') or i}: rooms are required")
        rep = int(f.get("count") or 1)
        if rep < 1 or rep > 100:
            raise ValueError(f"Floor {f.get('name') or i}: count must be between 1 and 100")
        out.append({"name": str(f.get("name") or f"Floor {i}"), "count": rep, "rooms": rooms})
    if not out:
        raise ValueError("floors must contain at least one floor with rooms")
    return out


def design_building(*, building_type: str, climate_zone: str, floors: List[Dict[str, Any]], floor_height_m: float = 3.6,
                    norms: Dict[str, Any] | None = None, **hvac_kwargs: Any) -> Dict[str, Any]:
    over = norms or {}
    fl = _floors(floors)
    if floor_height_m <= 0:
        raise ValueError("floor_height_m must be greater than zero")
    circ = _n("layout", "circulation_factor", over)
    floor_results: List[Dict[str, Any]] = []
    tot = {"floors": 0, "area": 0.0, "occupants": 0, "tr": 0.0, "airflow": 0.0, "fan_kw": 0.0}
    hvac_lines = {"duct_sqm": 0.0, "chw_pipe_m": 0.0, "chw_dn": 0, "ahu_fcu": {}}
    for f in fl:
        pkg = design_package(building_type=building_type, climate_zone=climate_zone, rooms=f["rooms"], **hvac_kwargs)
        area = pkg["total_area_m2"]
        gross = area * circ
        side = math.sqrt(gross)
        roughness = duct.DUCT_MATERIALS["gss"]["roughness_mm"]
        main = duct.size_duct_velocity_method(pkg["total_supply_airflow_m3h"], _n("layout", "main_duct_velocity_ms", over), roughness)
        main_d = main["recommended_diameter_mm"] / 1000.0
        main_area = math.pi * main_d * side
        branch_area = 0.0
        terminals: Dict[str, int] = {}
        for r in pkg["room_schedule"]:
            length = side / 2.0 + math.sqrt(r["area_m2"]) / 2.0
            branch_area += math.pi * (r["duct_diameter_mm"] / 1000.0) * length
            terminals[r["terminal_equipment"]] = terminals.get(r["terminal_equipment"], 0) + 1
        occupants = 0
        given = {str(r.get("room_id") or r.get("id") or f"R{n}"): r for n, r in enumerate(f["rooms"], 1)}
        for rid, r in given.items():
            o = r.get("occupancy")
            occupants += int(o) if o not in (None, "") else round(float(r["area_m2"]) / _n("people", "sqm_per_person", over))
        fr = {"name": f["name"], "repeat": f["count"], "area_m2": round(area, 1), "gross_area_m2": round(gross, 1), "side_m": round(side, 1),
              "occupants": occupants, "cooling_load_tr": pkg["block_load_tr"], "supply_airflow_m3h": pkg["total_supply_airflow_m3h"],
              "main_duct_mm": main["recommended_diameter_mm"], "duct_sheet_sqm": round(main_area + branch_area, 1),
              "terminals": terminals, "fan_motor_kw": pkg["plant_summary"]["total_fan_motor_kw"], "hvac_package": pkg}
        floor_results.append(fr)
        k = f["count"]
        tot["floors"] += k
        tot["area"] += area * k
        tot["occupants"] += occupants * k
        tot["tr"] += pkg["block_load_tr"] * k
        tot["airflow"] += pkg["total_supply_airflow_m3h"] * k
        tot["fan_kw"] += pkg["plant_summary"]["total_fan_motor_kw"] * k
        hvac_lines["duct_sqm"] += (main_area + branch_area) * k
        for t, c in terminals.items():
            hvac_lines["ahu_fcu"][t] = hvac_lines["ahu_fcu"].get(t, 0) + c * k
    n_floors = tot["floors"]
    height = n_floors * floor_height_m
    avg_side = math.sqrt(tot["area"] / n_floors * circ)
    block_tr = tot["tr"]
    from skills.calculators import formulas as F
    chw_flow = F.hydronic_flow({"load": block_tr * KW_PER_TR, "load_unit": "kw", "delta_t_c": float(hvac_kwargs.get("chw_delta_t_c", 5.5))})[0]
    header = F.water_pipe_sizing({"flow_m3h": chw_flow["flow_m3h"]})[0]
    hvac = {"block_load_tr": round(block_tr, 1), "total_supply_airflow_m3h": round(tot["airflow"]), "chilled_water_flow_m3h": chw_flow["flow_m3h"],
            "chilled_water_header_dn": header["selected_dn"], "duct_sheet_sqm": round(hvac_lines["duct_sqm"], 1),
            "chw_pipe_m": round(2 * (height + avg_side * 2), 1), "terminal_units": hvac_lines["ahu_fcu"], "total_fan_kw": round(tot["fan_kw"], 1)}

    occ = tot["occupants"]
    wc = math.ceil(occ / _n("plumbing", "persons_per_wc", over))
    urinals = math.ceil(wc * _n("plumbing", "urinal_share", over))
    basins = math.ceil(occ / _n("plumbing", "persons_per_basin", over))
    fixtures = wc + urinals + basins
    demand_l_day = occ * _n("people", "water_lpcd", over)
    plumbing = {"occupants": occ, "water_demand_l_day": round(demand_l_day), "water_closets": wc, "urinals": urinals, "wash_basins": basins,
                "supply_pipe_m": round(fixtures * _n("plumbing", "supply_m_per_fixture", over) + 2 * height, 1),
                "drain_pipe_m": round(fixtures * _n("plumbing", "drain_m_per_fixture", over) + 2 * height, 1),
                "storage_tank_litres": round(demand_l_day * 1.0)}

    area = tot["area"]
    spk = math.ceil(area / _n("fire", "sqm_per_sprinkler", over))
    fire = {"sprinkler_heads": spk, "sprinkler_pipe_m": round(spk * _n("fire", "pipe_m_per_sprinkler", over) + height, 1),
            "smoke_detectors": math.ceil(area / _n("fire", "sqm_per_detector", over)),
            "extinguishers": math.ceil(area / _n("fire", "sqm_per_extinguisher", over)),
            "landing_valves": sum(max(1, math.ceil(fr["area_m2"] / _n("fire", "sqm_per_hydrant_point", over))) * fr["repeat"] for fr in floor_results),
            "riser_m": round(height * 2, 1)}
    fire["hose_reels"] = fire["landing_valves"]

    lights = math.ceil(area * _n("electrical", "lighting_w_m2", over) / _n("electrical", "fitting_w", over))
    sockets = math.ceil(area / _n("electrical", "sqm_per_socket", over))
    light_kw = lights * _n("electrical", "fitting_w", over) / 1000.0
    socket_kw = sockets * _n("electrical", "socket_w", over) / 1000.0
    hvac_kw = block_tr * KW_PER_TR / 3.0 + tot["fan_kw"]   # assumed plant COP 3 for electrical demand
    connected = light_kw + socket_kw + hvac_kw
    maxdem = connected * _n("electrical", "demand_factor", over)
    electrical = {"light_fittings": lights, "socket_outlets": sockets, "lighting_kw": round(light_kw, 1), "socket_kw": round(socket_kw, 1),
                  "hvac_electrical_kw": round(hvac_kw, 1), "connected_load_kw": round(connected, 1), "maximum_demand_kw": round(maxdem, 1),
                  "maximum_demand_kva": round(maxdem / _n("electrical", "power_factor", over), 1), "floor_distribution_boards": n_floors,
                  "wiring_m": round((lights + sockets) * _n("electrical", "wire_m_per_point", over), 1),
                  "riser_cable_m": round(height * 1.0 + n_floors * 15.0, 1), "cable_tray_m": round(n_floors * avg_side * 1.0 + height, 1)}
    assumptions = [{"name": f"{g}.{k}", "value": over.get(k, v[0]), "basis": v[1] + " (starter norm, unvalidated)"} for g, d in NORMS.items() for k, v in d.items()]
    assumptions.append({"name": "floor_height_m", "value": floor_height_m, "basis": "Floor-to-floor height used for riser lengths"})
    assumptions.append({"name": "hvac_electrical_basis", "value": "plant COP 3.0", "basis": "HVAC electrical demand = cooling kW / 3 plus fan motors; replace with selected plant data"})
    return {"building_type": building_type, "floors_total": n_floors, "total_area_m2": round(area, 1), "floor_height_m": floor_height_m,
            "floors": [{k: v for k, v in fr.items() if k != "hvac_package"} for fr in floor_results],
            "hvac": hvac, "plumbing": plumbing, "fire": fire, "electrical": electrical, "assumptions": assumptions,
            "limitations": ["Preliminary quantity model for budgetary BOQ and engineer review; not a coordinated MEP design.",
                            "Run lengths are estimated from floor area (square footprint, central corridor). No routing or clash check.",
                            "Plumbing, fire and electrical counts are preliminary estimates, not the full NBC / local fire authority / IS 732 design.",
                            "Fire tank, pump and hydrant system sizes are not computed here; they are listed as lump-sum items to be sized separately.",
                            "HVAC loads are benchmark-based unless wall and glass areas are given per room."]}
