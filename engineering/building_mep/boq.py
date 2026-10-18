"""Turn a building MEP quantity model into BOQ lines, then take them off into materials with the existing recipes."""
from __future__ import annotations

import math
from typing import Any, Dict, List

from skills.commercial.boq_takeoff import takeoff


def _dn(dn: Any) -> str:
    return f"DN{int(dn)}" if dn else ""


def boq_lines(d: Dict[str, Any]) -> List[Dict[str, Any]]:
    h, p, f, e = d["hvac"], d["plumbing"], d["fire"], d["electrical"]
    L: List[Dict[str, Any]] = []

    def add(trade: str, desc: str, unit: str, qty: float, recipe: str | None = None, spec: str | None = None):
        if qty and qty > 0:
            row = {"item_no": f"{trade}-{len(L) + 1}", "description": desc, "unit": unit, "quantity": round(float(qty), 2)}
            if recipe:
                row["recipe_id"] = recipe
            if spec:
                row["spec"] = spec
            L.append(row)

    # HVAC
    add("HVAC", "Supply, fabrication and installation of GI sheet metal ducting (main and branch)", "sqm", h["duct_sheet_sqm"], "gi_duct_fabrication")
    add("HVAC", "Thermal insulation to supply air ducts", "sqm", h["duct_sheet_sqm"], "duct_thermal_insulation")
    add("HVAC", f"MS chilled water pipe, header {_dn(h['chilled_water_header_dn'])}", "m", h["chw_pipe_m"], "ms_condenser_water_pipe", _dn(h["chilled_water_header_dn"]))
    for term, n in sorted((h.get("terminal_units") or {}).items()):
        add("HVAC", f"Supply, installation, testing and commissioning of {term}", "Nos", n)
    add("HVAC", f"Chilled water plant for {h['block_load_tr']} TR block load (chiller or VRF outdoor group) with standby, chilled water pumps, expansion tank and BMS interface", "Lot", 1)
    # Plumbing
    add("PLB", "Water supply pipe, risers and branches", "m", p["supply_pipe_m"], "cpvc_water_supply_pipe", "CPVC/GI as specified")
    add("PLB", "Soil and waste drain pipe, stacks and branches", "m", p["drain_pipe_m"], "upvc_drain_pipe", "uPVC as specified")
    add("PLB", "Water closets with flushing cistern, complete", "Nos", p["water_closets"])
    add("PLB", "Urinals with flush valve, complete", "Nos", p["urinals"])
    add("PLB", "Wash basins with taps, complete", "Nos", p["wash_basins"])
    add("PLB", f"Water storage tank, {p['storage_tank_litres']:,} litres (underground and overhead as designed)", "Lot", 1)
    add("PLB", "Domestic water transfer pump set with controls", "Set", 2)
    # Fire
    add("FIRE", "Fire sprinkler pipework (mains, branches and risers)", "m", f["sprinkler_pipe_m"] + f["riser_m"], "gi_sprinkler_pipe", "heavy class")
    add("FIRE", "Pendent sprinkler heads, complete with escutcheon", "Nos", f["sprinkler_heads"])
    add("FIRE", "Addressable smoke detectors with base", "Nos", f["smoke_detectors"])
    add("FIRE", "Portable fire extinguishers, ABC type", "Nos", f["extinguishers"])
    add("FIRE", "Landing valves with hose box, complete", "Nos", f["landing_valves"])
    add("FIRE", "Hose reels with first-aid hose, complete", "Nos", f["hose_reels"])
    add("FIRE", "Fire pump set (main, jockey, diesel standby) and fire water tank, sized separately", "Lot", 1)
    add("FIRE", "Fire alarm control panel, manual call points and hooters", "Lot", 1)
    # Electrical
    add("ELEC", "PVC conduit with copper wiring for lights and sockets", "m", e["wiring_m"], "pvc_conduit_wiring")
    add("ELEC", "Armoured copper cable for risers and sub-mains", "m", e["riser_cable_m"], "mv_cable_supply", "LT copper, sizes as designed")
    add("ELEC", "Cable tray, perforated, with accessories", "m", e["cable_tray_m"], "cable_tray", "perforated, with accessories")
    add("ELEC", "LED panel light fittings, complete", "Nos", e["light_fittings"])
    add("ELEC", "Power socket outlets, 6/16 A, complete", "Nos", e["socket_outlets"])
    add("ELEC", "Floor distribution boards (lighting and power)", "Nos", e["floor_distribution_boards"])
    add("ELEC", f"Main LT panel for about {e['maximum_demand_kva']:g} kVA maximum demand, with ACB, metering and earthing", "Lot", 1)
    return L


def generate_boq(design: Dict[str, Any]) -> Dict[str, Any]:
    lines = boq_lines(design)
    res = takeoff(lines)
    res["generated_boq_lines"] = lines
    return res
