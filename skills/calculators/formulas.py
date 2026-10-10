"""Deterministic engineering formulas used by the governed calculator catalogue.

Every function takes plain numbers and returns plain numbers/dicts. No I/O, no
randomness. Constants are named so a reviewer can audit them. Results are
preliminary design values, not certified selections.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------- constants
CP_AIR = 1.006          # kJ/kg.K dry air
CP_VAPOUR = 1.86        # kJ/kg.K water vapour
H_FG0 = 2501.0          # kJ/kg latent heat at 0 C
CP_WATER = 4.186        # kJ/kg.K
KW_PER_TR = 3.5168525   # 1 TR = 3.51685 kW
STD_PRESSURE_KPA = 101.325

STD_MOTOR_KW = (0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5, 11.0, 15.0, 18.5, 22.0,
                30.0, 37.0, 45.0, 55.0, 75.0, 90.0, 110.0, 132.0, 160.0, 200.0, 250.0)

# Schedule-40 steel pipe: nominal size (DN) -> inside diameter (mm)
PIPE_ID_MM: Tuple[Tuple[int, float], ...] = (
    (15, 15.8), (20, 20.9), (25, 26.6), (32, 35.1), (40, 40.9), (50, 52.5), (65, 62.7),
    (80, 77.9), (100, 102.3), (125, 128.2), (150, 154.1), (200, 202.7), (250, 254.5), (300, 303.2),
)

STD_CABLE_MM2 = (1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630)
STD_DRAIN_MM = (75, 100, 110, 150, 200, 225, 250, 300, 375, 450, 600)


class CalcError(ValueError):
    """Raised for invalid engineering inputs; message is shown to the reviewer."""


def num(inputs: Dict[str, Any], key: str, *, default: Optional[float] = None, minimum: Optional[float] = None,
        maximum: Optional[float] = None, exclusive_min: bool = False) -> float:
    raw = inputs.get(key)
    if raw is None or raw == "":
        if default is None:
            raise CalcError(f"Missing required input: {key}")
        return float(default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise CalcError(f"{key} must be numeric")
    if math.isnan(value) or math.isinf(value):
        raise CalcError(f"{key} must be a finite number")
    if minimum is not None and (value <= minimum if exclusive_min else value < minimum):
        raise CalcError(f"{key} must be {'greater than' if exclusive_min else 'at least'} {minimum:g}")
    if maximum is not None and value > maximum:
        raise CalcError(f"{key} must be at most {maximum:g}")
    return value


def r(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def next_standard(value: float, series: Sequence[float]) -> Optional[float]:
    for item in series:
        if item >= value - 1e-9:
            return item
    return None


# ------------------------------------------------------------- psychrometrics
def pressure_kpa(altitude_m: float) -> float:
    return STD_PRESSURE_KPA * (1 - 2.25577e-5 * altitude_m) ** 5.2559


def p_sat_kpa(t_c: float) -> float:
    """ASHRAE Fundamentals saturation pressure over liquid water, 0..200 C."""
    if t_c < 0:
        # over ice, -100..0 C
        t = t_c + 273.15
        c = (-5.6745359e3, 6.3925247, -9.677843e-3, 6.2215701e-7, 2.0747825e-9, -9.484024e-13, 4.1635019)
        return math.exp(c[0] / t + c[1] + c[2] * t + c[3] * t * t + c[4] * t ** 3 + c[5] * t ** 4 + c[6] * math.log(t)) / 1000.0
    t = t_c + 273.15
    c8, c9, c10, c11, c12, c13 = -5.8002206e3, 1.3914993, -4.8640239e-2, 4.1764768e-5, -1.4452093e-8, 6.5459673
    return math.exp(c8 / t + c9 + c10 * t + c11 * t * t + c12 * t ** 3 + c13 * math.log(t)) / 1000.0


def humidity_ratio(pw_kpa: float, p_kpa: float) -> float:
    return 0.621945 * pw_kpa / (p_kpa - pw_kpa)


def enthalpy(t_c: float, w: float) -> float:
    return CP_AIR * t_c + w * (H_FG0 + CP_VAPOUR * t_c)


def dew_point_c(pw_kpa: float) -> float:
    lo, hi = -60.0, 100.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if p_sat_kpa(mid) < pw_kpa:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def wet_bulb_c(t_c: float, w: float, p_kpa: float) -> float:
    lo, hi = -40.0, t_c
    for _ in range(80):
        tw = (lo + hi) / 2
        ws = humidity_ratio(p_sat_kpa(tw), p_kpa)
        if tw >= 0:
            w_calc = ((H_FG0 - 2.326 * tw) * ws - CP_AIR * (t_c - tw)) / (H_FG0 + CP_VAPOUR * t_c - 4.186 * tw)
        else:
            w_calc = ((2830 - 0.24 * tw) * ws - CP_AIR * (t_c - tw)) / (2830 + CP_VAPOUR * t_c - 2.1 * tw)
        if w_calc > w:
            hi = tw
        else:
            lo = tw
    return (lo + hi) / 2


def moist_air_state(db_c: float, rh_pct: float, altitude_m: float = 0.0) -> Dict[str, float]:
    p = pressure_kpa(altitude_m)
    pws = p_sat_kpa(db_c)
    pw = pws * rh_pct / 100.0
    if pw >= p:
        raise CalcError("Vapour pressure exceeds total pressure; check dry-bulb and RH")
    w = humidity_ratio(pw, p)
    v = 0.287042 * (db_c + 273.15) * (1 + 1.607858 * w) / p
    return {
        "pressure_kpa": p, "p_sat_kpa": pws, "p_vapour_kpa": pw, "humidity_ratio": w,
        "enthalpy_kj_kg": enthalpy(db_c, w), "dew_point_c": dew_point_c(pw),
        "wet_bulb_c": wet_bulb_c(db_c, w, p), "specific_volume_m3_kg": v,
        "density_kg_m3": (1 + w) / v,
    }


def psychrometrics(inputs: Dict[str, Any]):
    db = num(inputs, "dry_bulb_c", minimum=-40, maximum=80)
    rh = num(inputs, "rh_pct", minimum=0, maximum=100)
    alt = num(inputs, "altitude_m", default=0, minimum=-400, maximum=5000)
    s = moist_air_state(db, rh, alt)
    res = {k: r(v, 4) for k, v in s.items()}
    res["dry_bulb_c"] = db
    res["rh_pct"] = rh
    trace = [
        {"step": 1, "operation": "barometric_pressure", "detail": f"p = 101.325 x (1 - 2.25577e-5 x {alt:g})^5.2559 = {s['pressure_kpa']:.3f} kPa"},
        {"step": 2, "operation": "saturation_pressure", "detail": f"ASHRAE Hyland-Wexler pws({db:g} C) = {s['p_sat_kpa']:.4f} kPa; pw = RH x pws = {s['p_vapour_kpa']:.4f} kPa"},
        {"step": 3, "operation": "humidity_ratio", "detail": f"W = 0.621945 pw/(p-pw) = {s['humidity_ratio']:.5f} kg/kg"},
        {"step": 4, "operation": "enthalpy", "detail": f"h = 1.006 t + W(2501 + 1.86 t) = {s['enthalpy_kj_kg']:.2f} kJ/kg"},
        {"step": 5, "operation": "dew_point_and_wet_bulb", "detail": f"Dew point {s['dew_point_c']:.2f} C; wet-bulb {s['wet_bulb_c']:.2f} C (solved iteratively)"},
    ]
    return res, trace, [], []


# ---------------------------------------------------------------- coil load
def coil_load(inputs: Dict[str, Any]):
    flow = num(inputs, "airflow_m3h", minimum=0, exclusive_min=True)
    alt = num(inputs, "altitude_m", default=0, minimum=-400, maximum=5000)
    e = moist_air_state(num(inputs, "entering_db_c", minimum=-10, maximum=60), num(inputs, "entering_rh_pct", minimum=1, maximum=100), alt)
    ldb = num(inputs, "leaving_db_c", minimum=-10, maximum=60)
    lrh = num(inputs, "leaving_rh_pct", minimum=1, maximum=100)
    lv = moist_air_state(ldb, lrh, alt)
    edb = float(inputs["entering_db_c"])
    m_da = (flow / 3600.0) / e["specific_volume_m3_kg"]
    total = m_da * (e["enthalpy_kj_kg"] - lv["enthalpy_kj_kg"])
    sens = m_da * (CP_AIR + CP_VAPOUR * lv["humidity_ratio"]) * (edb - ldb)
    latent = total - sens
    warn = []
    if total <= 0:
        raise CalcError("Leaving air enthalpy is not lower than entering; this is not a cooling coil duty")
    if latent < -1e-6:
        warn.append("Latent component is negative (leaving humidity ratio above entering): check the leaving condition.")
    water_removed = m_da * (e["humidity_ratio"] - lv["humidity_ratio"]) * 3600.0
    res = {
        "dry_air_mass_flow_kg_s": r(m_da, 4), "total_cooling_kw": r(total, 2), "total_cooling_tr": r(total / KW_PER_TR, 2),
        "sensible_kw": r(sens, 2), "latent_kw": r(latent, 2), "sensible_heat_ratio": r(sens / total, 3),
        "condensate_kg_h": r(max(water_removed, 0), 2),
        "entering_enthalpy_kj_kg": r(e["enthalpy_kj_kg"], 2), "leaving_enthalpy_kj_kg": r(lv["enthalpy_kj_kg"], 2),
        "entering_humidity_ratio": r(e["humidity_ratio"], 5), "leaving_humidity_ratio": r(lv["humidity_ratio"], 5),
    }
    trace = [
        {"step": 1, "operation": "air_mass_flow", "detail": f"{flow:g} m3/h / 3600 / v({e['specific_volume_m3_kg']:.4f} m3/kg) = {m_da:.4f} kg/s dry air"},
        {"step": 2, "operation": "total_load", "detail": f"m x (h_in {e['enthalpy_kj_kg']:.2f} - h_out {lv['enthalpy_kj_kg']:.2f}) = {total:.2f} kW"},
        {"step": 3, "operation": "sensible_load", "detail": f"m x (1.006 + 1.86 W_out) x ({edb:g} - {ldb:g}) = {sens:.2f} kW"},
        {"step": 4, "operation": "latent_and_shr", "detail": f"Latent = total - sensible = {latent:.2f} kW; SHR = {sens / total:.3f}"},
    ]
    return res, trace, [], warn


# --------------------------------------------------------------- ventilation
VENT_RATES = {  # space type: (Rp L/s.person, Ra L/s.m2)  -- ASHRAE 62.1 Table 6-1 reference values
    "office": (2.5, 0.3), "conference": (2.5, 0.3), "lobby": (2.5, 0.3), "retail": (3.8, 0.6),
    "classroom": (5.0, 0.6), "restaurant_dining": (3.8, 0.9), "gym": (10.0, 0.3), "hospital_patient_room": (5.0, 0.6),
}


def ventilation_rate(inputs: Dict[str, Any]):
    st = str(inputs.get("space_type", "")).strip().lower()
    area = num(inputs, "floor_area_m2", minimum=0, exclusive_min=True)
    pz = num(inputs, "occupants", minimum=0)
    ez = num(inputs, "zone_air_distribution_effectiveness", default=1.0, minimum=0.5, maximum=1.5)
    assumptions = []
    if inputs.get("rp_l_s_person") not in (None, "") and inputs.get("ra_l_s_m2") not in (None, ""):
        rp, ra = num(inputs, "rp_l_s_person", minimum=0), num(inputs, "ra_l_s_m2", minimum=0)
        basis = "User-supplied rates."
    elif st in VENT_RATES:
        rp, ra = VENT_RATES[st]
        basis = f"Reference rates for '{st}': Rp {rp} L/s per person, Ra {ra} L/s per m2."
        assumptions.append({"name": "ventilation_rates", "value": f"Rp={rp}, Ra={ra}", "basis": "ASHRAE 62.1 Table 6-1 reference values; verify against the edition/NBC clause required by the project."})
    else:
        raise CalcError("Provide space_type (" + ", ".join(sorted(VENT_RATES)) + ") or both rp_l_s_person and ra_l_s_m2")
    vbz = rp * pz + ra * area
    voz = vbz / ez
    res = {"breathing_zone_outdoor_air_l_s": r(vbz, 2), "zone_outdoor_air_l_s": r(voz, 2), "zone_outdoor_air_m3h": r(voz * 3.6, 1),
           "zone_outdoor_air_cfm": r(voz * 2.11888, 1), "people_component_l_s": r(rp * pz, 2), "area_component_l_s": r(ra * area, 2),
           "rp_l_s_person": rp, "ra_l_s_m2": ra, "air_distribution_effectiveness": ez}
    trace = [
        {"step": 1, "operation": "rates", "detail": basis},
        {"step": 2, "operation": "breathing_zone_outdoor_air", "detail": f"Vbz = Rp x Pz + Ra x Az = {rp} x {pz:g} + {ra} x {area:g} = {vbz:.2f} L/s"},
        {"step": 3, "operation": "zone_outdoor_air", "detail": f"Voz = Vbz / Ez = {vbz:.2f} / {ez:g} = {voz:.2f} L/s = {voz * 3.6:.1f} m3/h"},
    ]
    return res, trace, assumptions, ["Zone-level only. System-level multiple-zone recirculation correction (Ev) is not applied."]


# ------------------------------------------------------------------ fan power
def fan_power(inputs: Dict[str, Any]):
    q = num(inputs, "airflow_m3h", minimum=0, exclusive_min=True)
    dp = num(inputs, "total_static_pressure_pa", minimum=0, exclusive_min=True)
    fe = num(inputs, "fan_efficiency_pct", default=65, minimum=10, maximum=95)
    de = num(inputs, "drive_efficiency_pct", default=95, minimum=50, maximum=100)
    me = num(inputs, "motor_efficiency_pct", default=92, minimum=50, maximum=99)
    margin = num(inputs, "motor_margin_pct", default=15, minimum=0, maximum=100)
    air_kw = q / 3600.0 * dp / 1000.0
    shaft = air_kw / (fe / 100.0)
    inp = shaft / (de / 100.0) / (me / 100.0)
    motor_req = shaft / (de / 100.0) * (1 + margin / 100.0)
    motor = next_standard(motor_req, STD_MOTOR_KW)
    sfp = inp * 1000.0 / (q / 3.6)
    res = {"air_power_kw": r(air_kw, 3), "fan_shaft_kw": r(shaft, 3), "motor_input_kw": r(inp, 3),
           "motor_required_kw": r(motor_req, 3), "standard_motor_kw": motor, "specific_fan_power_w_per_l_s": r(sfp, 3)}
    a = [{"name": n, "value": v, "basis": "Default planning value; replace with vendor data."} for n, v in
         (("fan_efficiency_pct", fe), ("drive_efficiency_pct", de), ("motor_efficiency_pct", me), ("motor_margin_pct", margin)) if inputs.get(n) in (None, "")]
    trace = [
        {"step": 1, "operation": "air_power", "detail": f"Q x dP = {q / 3600:.4f} m3/s x {dp:g} Pa = {air_kw:.3f} kW"},
        {"step": 2, "operation": "shaft_power", "detail": f"{air_kw:.3f} / {fe:g}% = {shaft:.3f} kW"},
        {"step": 3, "operation": "motor_input", "detail": f"{shaft:.3f} / {de:g}% / {me:g}% = {inp:.3f} kW"},
        {"step": 4, "operation": "motor_selection", "detail": f"Shaft/drive x (1+{margin:g}%) = {motor_req:.3f} kW -> next standard {motor} kW"},
    ]
    w = [] if motor else ["Required motor exceeds the standard list; select manually."]
    return res, trace, a, w


# -------------------------------------------------------------- water pipework
def _water_props(t_c: float) -> Tuple[float, float]:
    rho = (999.83952 + 16.945176 * t_c - 7.9870401e-3 * t_c ** 2 - 46.170461e-6 * t_c ** 3 + 105.56302e-9 * t_c ** 4
           - 280.54253e-12 * t_c ** 5) / (1 + 16.897850e-3 * t_c)
    mu = 2.414e-5 * 10 ** (247.8 / (t_c + 273.15 - 140.0))  # Pa.s
    return rho, mu


def darcy_dp_pa_per_m(flow_m3s: float, d_m: float, rough_m: float, rho: float, mu: float) -> Tuple[float, float, float]:
    area = math.pi * d_m ** 2 / 4
    v = flow_m3s / area
    re = rho * v * d_m / mu
    if re < 2300:
        f = 64 / re
    else:
        f = 0.25 / (math.log10(rough_m / (3.7 * d_m) + 5.74 / re ** 0.9)) ** 2
    return f * (1 / d_m) * rho * v * v / 2, v, re


def water_pipe_sizing(inputs: Dict[str, Any]):
    q = num(inputs, "flow_m3h", minimum=0, exclusive_min=True)
    vt = num(inputs, "target_velocity_ms", default=2.0, minimum=0.2, maximum=6)
    length = num(inputs, "length_m", default=100, minimum=0, exclusive_min=True)
    temp = num(inputs, "water_temp_c", default=20, minimum=1, maximum=95)
    rough = num(inputs, "roughness_mm", default=0.045, minimum=0, exclusive_min=True)
    rho, mu = _water_props(temp)
    qs = q / 3600.0
    ideal = math.sqrt(4 * qs / (math.pi * vt)) * 1000
    choice = None
    for dn, idm in PIPE_ID_MM:
        if idm >= ideal - 1e-9:
            choice = (dn, idm)
            break
    if choice is None:
        raise CalcError(f"Flow needs an ID of {ideal:.0f} mm, above DN300; select pipework manually")
    dn, idm = choice
    dpm, v, re = darcy_dp_pa_per_m(qs, idm / 1000, rough / 1000, rho, mu)
    res = {"ideal_inside_diameter_mm": r(ideal, 1), "selected_dn": dn, "selected_inside_diameter_mm": idm,
           "velocity_ms": r(v, 2), "reynolds_number": round(re), "friction_pa_per_m": r(dpm, 1),
           "friction_kpa_per_100m": r(dpm * 100 / 1000, 2), "straight_pipe_loss_kpa": r(dpm * length / 1000, 2),
           "straight_pipe_head_m": r(dpm * length / (rho * 9.80665), 2), "water_density_kg_m3": r(rho, 1)}
    a = [{"name": "pipe_schedule", "value": "Schedule-40 steel inside diameters", "basis": "Standard nominal-size table; confirm the project pipe class and wall thickness."}]
    trace = [
        {"step": 1, "operation": "ideal_diameter", "detail": f"d = sqrt(4Q/(pi v)) = sqrt(4 x {qs:.5f}/(pi x {vt:g})) = {ideal:.1f} mm"},
        {"step": 2, "operation": "select_size", "detail": f"Smallest size with ID >= ideal: DN{dn} (ID {idm} mm), velocity {v:.2f} m/s"},
        {"step": 3, "operation": "friction", "detail": f"Darcy-Weisbach with Swamee-Jain f, Re {re:,.0f}, roughness {rough:g} mm: {dpm:.1f} Pa/m"},
        {"step": 4, "operation": "length_loss", "detail": f"{dpm:.1f} Pa/m x {length:g} m = {dpm * length / 1000:.2f} kPa (straight pipe only, fittings excluded)"},
    ]
    w = ["Fittings, valves and equipment losses are not included; add them separately."]
    if v > 3.0:
        w.append("Velocity above 3 m/s may cause noise/erosion in occupied-building pipework.")
    return res, trace, a, w


# ------------------------------------------------------------ expansion tank
def expansion_tank(inputs: Dict[str, Any]):
    vol = num(inputs, "system_volume_l", minimum=0, exclusive_min=True)
    tmin = num(inputs, "min_temp_c", default=10, minimum=0, maximum=60)
    tmax = num(inputs, "max_temp_c", minimum=1, maximum=140)
    pf = num(inputs, "fill_pressure_bar_g", minimum=0)
    pm = num(inputs, "max_pressure_bar_g", minimum=0, exclusive_min=True)
    if tmax <= tmin:
        raise CalcError("max_temp_c must be greater than min_temp_c")
    if pm <= pf:
        raise CalcError("max_pressure_bar_g must be greater than fill_pressure_bar_g")
    rc, _ = _water_props(tmin)
    rh, _ = _water_props(tmax)
    expansion_l = vol * (rc / rh - 1)
    pa, pb = pf + 1.01325, pm + 1.01325
    accept = 1 - pa / pb
    tank = expansion_l / accept
    res = {"expansion_volume_l": r(expansion_l, 2), "expansion_percent": r((rc / rh - 1) * 100, 3),
           "acceptance_factor": r(accept, 4), "minimum_tank_volume_l": r(tank, 1), "recommended_tank_volume_l": r(tank * 1.1, 1)}
    trace = [
        {"step": 1, "operation": "water_density", "detail": f"rho({tmin:g} C) = {rc:.2f}; rho({tmax:g} C) = {rh:.2f} kg/m3 (Kell)"},
        {"step": 2, "operation": "expansion", "detail": f"Ve = V x (rho_cold/rho_hot - 1) = {vol:g} x {rc / rh - 1:.5f} = {expansion_l:.2f} L"},
        {"step": 3, "operation": "acceptance_factor", "detail": f"1 - Pfill/Pmax (absolute) = 1 - {pa:.3f}/{pb:.3f} = {accept:.4f}"},
        {"step": 4, "operation": "tank_volume", "detail": f"Vt = Ve / acceptance = {tank:.1f} L; +10% margin = {tank * 1.1:.1f} L"},
    ]
    return res, trace, [{"name": "tank_margin_pct", "value": 10, "basis": "Planning margin; confirm against vendor sizing."}], \
        ["Diaphragm-vessel precharge must equal the fill pressure; vendor selection is required."]


# -------------------------------------------------------------- hydronic flow
def hydronic_flow(inputs: Dict[str, Any]):
    unit = str(inputs.get("load_unit", "kw")).lower()
    load = num(inputs, "load", minimum=0, exclusive_min=True)
    if unit not in ("kw", "tr"):
        raise CalcError("load_unit must be 'kw' or 'tr'")
    kw = load * KW_PER_TR if unit == "tr" else load
    dt = num(inputs, "delta_t_c", default=5.5, minimum=0.5, maximum=40)
    cop = inputs.get("chiller_cop")
    heat_rej = None
    if cop not in (None, ""):
        cop = num(inputs, "chiller_cop", minimum=1, exclusive_min=True)
        heat_rej = kw * (1 + 1 / cop)
    rho = 1000.0
    m = kw / (CP_WATER * dt)
    l_s = m / rho * 1000
    res = {"load_kw": r(kw, 2), "load_tr": r(kw / KW_PER_TR, 2), "flow_l_s": r(l_s, 3), "flow_m3h": r(l_s * 3.6, 2),
           "flow_usgpm": r(l_s * 15.8503, 1), "gpm_per_tr": r(l_s * 15.8503 / (kw / KW_PER_TR), 3)}
    trace = [{"step": 1, "operation": "flow", "detail": f"m = Q/(cp x dT) = {kw:.2f}/({CP_WATER} x {dt:g}) = {m:.3f} kg/s = {l_s * 3.6:.2f} m3/h"}]
    if heat_rej is not None:
        res["condenser_heat_rejection_kw"] = r(heat_rej, 2)
        trace.append({"step": 2, "operation": "heat_rejection", "detail": f"Q x (1 + 1/COP) = {kw:.2f} x (1 + 1/{cop:g}) = {heat_rej:.2f} kW"})
    a = [{"name": "water_properties", "value": "cp 4.186 kJ/kg.K, density 1000 kg/m3", "basis": "Standard water; glycol mixtures need corrected properties."}]
    if inputs.get("delta_t_c") in (None, ""):
        a.append({"name": "delta_t_c", "value": 5.5, "basis": "Common chilled-water design range; confirm with the plant design."})
    return res, trace, a, []


# -------------------------------------------------------------- heat recovery
def heat_recovery(inputs: Dict[str, Any]):
    flow = num(inputs, "outdoor_air_m3h", minimum=0, exclusive_min=True)
    kind = str(inputs.get("recovery_type", "total")).lower()
    if kind not in ("sensible", "total"):
        raise CalcError("recovery_type must be 'sensible' or 'total'")
    eff = num(inputs, "effectiveness_pct", minimum=1, maximum=95) / 100
    alt = num(inputs, "altitude_m", default=0, minimum=-400, maximum=5000)
    oa = moist_air_state(num(inputs, "outdoor_db_c", minimum=-20, maximum=55), num(inputs, "outdoor_rh_pct", minimum=1, maximum=100), alt)
    ra = moist_air_state(num(inputs, "exhaust_db_c", minimum=10, maximum=40), num(inputs, "exhaust_rh_pct", minimum=1, maximum=100), alt)
    odb, rdb = float(inputs["outdoor_db_c"]), float(inputs["exhaust_db_c"])
    m = (flow / 3600) / oa["specific_volume_m3_kg"]
    sens = m * (CP_AIR + CP_VAPOUR * oa["humidity_ratio"]) * eff * (odb - rdb)
    tot = m * eff * (oa["enthalpy_kj_kg"] - ra["enthalpy_kj_kg"])
    rec = sens if kind == "sensible" else tot
    res = {"recovery_type": kind, "recovered_kw_at_design": r(abs(rec), 2), "recovered_tr_at_design": r(abs(rec) / KW_PER_TR, 2),
           "mode": "cooling" if rec > 0 else "heating", "sensible_kw": r(abs(sens), 2), "total_kw": r(abs(tot), 2),
           "outdoor_enthalpy_kj_kg": r(oa["enthalpy_kj_kg"], 2), "exhaust_enthalpy_kj_kg": r(ra["enthalpy_kj_kg"], 2)}
    trace = [
        {"step": 1, "operation": "mass_flow", "detail": f"{flow:g} m3/h -> {m:.4f} kg/s dry air at outdoor state"},
        {"step": 2, "operation": "recovered_energy", "detail": f"{kind}: effectiveness {eff * 100:g}% x m x (outdoor - exhaust) = {abs(rec):.2f} kW"},
    ]
    w = ["Design-condition instantaneous value only. Annual savings need a weather-binned analysis."]
    hrs, lf = inputs.get("annual_hours"), inputs.get("load_factor_pct")
    if hrs not in (None, "") and lf not in (None, ""):
        kwh = abs(rec) * num(inputs, "annual_hours", minimum=0) * num(inputs, "load_factor_pct", minimum=0, maximum=100) / 100
        res["annual_recovered_kwh"] = r(kwh, 0)
        trace.append({"step": 3, "operation": "annual_energy", "detail": f"{abs(rec):.2f} kW x {hrs} h x {lf}% = {kwh:,.0f} kWh (user-supplied hours and load factor)"})
    return res, trace, [], w


# ---------------------------------------------------------------------- IPLV
def chiller_iplv(inputs: Dict[str, Any]):
    pts = [num(inputs, k, minimum=0, exclusive_min=True) for k in ("cop_100", "cop_75", "cop_50", "cop_25")]
    a_, b_, c_, d_ = pts
    iplv = 0.01 * a_ + 0.42 * b_ + 0.45 * c_ + 0.12 * d_
    res = {"iplv_cop": r(iplv, 3), "iplv_kw_per_tr": r(KW_PER_TR / iplv, 3), "full_load_kw_per_tr": r(KW_PER_TR / a_, 3),
           "weights": {"100%": 0.01, "75%": 0.42, "50%": 0.45, "25%": 0.12}}
    trace = [{"step": 1, "operation": "iplv", "detail": f"0.01 x {a_:g} + 0.42 x {b_:g} + 0.45 x {c_:g} + 0.12 x {d_:g} = {iplv:.3f}"},
             {"step": 2, "operation": "kw_per_tr", "detail": f"3.517 / {iplv:.3f} = {KW_PER_TR / iplv:.3f} kW/TR"}]
    return res, trace, [], ["Weighted from the supplied part-load COPs. The AHRI 550/590 rating requires its prescribed rating conditions (e.g. condenser relief); the values supplied must come from those test points."]


# ------------------------------------------------------------ duct pressure drop
def duct_pressure_drop(inputs: Dict[str, Any]):
    q = num(inputs, "airflow_m3h", minimum=0, exclusive_min=True) / 3600
    length = num(inputs, "length_m", minimum=0, exclusive_min=True)
    rough = num(inputs, "roughness_mm", default=0.09, minimum=0, exclusive_min=True) / 1000
    rho, mu = 1.2, 1.81e-5
    if inputs.get("diameter_mm") not in (None, ""):
        d = num(inputs, "diameter_mm", minimum=0, exclusive_min=True) / 1000
        shape = f"round {d * 1000:g} mm"
        area = math.pi * d * d / 4
        dh = d
    else:
        wmm, hmm = num(inputs, "width_mm", minimum=0, exclusive_min=True), num(inputs, "height_mm", minimum=0, exclusive_min=True)
        a, b = wmm / 1000, hmm / 1000
        area = a * b
        dh = 4 * area / (2 * (a + b))
        shape = f"rectangular {wmm:g} x {hmm:g} mm"
    v = q / area
    re = rho * v * dh / mu
    f = 64 / re if re < 2300 else 0.25 / (math.log10(rough / (3.7 * dh) + 5.74 / re ** 0.9)) ** 2
    pdyn = rho * v * v / 2
    fric_per_m = f / dh * pdyn
    fittings = inputs.get("fittings") or []
    if not isinstance(fittings, list):
        raise CalcError("fittings must be a list of {name, k, quantity}")
    k_total, rows = 0.0, []
    for i, ft in enumerate(fittings):
        try:
            k, qty = float(ft["k"]), float(ft.get("quantity", 1))
        except (KeyError, TypeError, ValueError):
            raise CalcError(f"fittings[{i}] requires numeric k (and optional quantity)")
        if k < 0 or qty < 0:
            raise CalcError(f"fittings[{i}] k and quantity must be >= 0")
        k_total += k * qty
        rows.append({"name": str(ft.get("name", f"fitting_{i + 1}")), "k": k, "quantity": qty, "loss_pa": r(k * qty * pdyn, 2)})
    straight, local = fric_per_m * length, k_total * pdyn
    res = {"section": shape, "velocity_ms": r(v, 2), "hydraulic_diameter_mm": r(dh * 1000, 1), "reynolds_number": round(re),
           "friction_pa_per_m": r(fric_per_m, 3), "straight_duct_loss_pa": r(straight, 1), "dynamic_pressure_pa": r(pdyn, 2),
           "sum_k_factors": r(k_total, 3), "fitting_loss_pa": r(local, 1), "total_pressure_drop_pa": r(straight + local, 1), "fitting_rows": rows}
    trace = [
        {"step": 1, "operation": "velocity", "detail": f"{shape}: v = Q/A = {q:.4f}/{area:.5f} = {v:.2f} m/s; Dh = {dh * 1000:.1f} mm"},
        {"step": 2, "operation": "friction", "detail": f"Darcy-Weisbach, Swamee-Jain f = {f:.4f}, roughness {rough * 1000:g} mm: {fric_per_m:.3f} Pa/m"},
        {"step": 3, "operation": "straight_loss", "detail": f"{fric_per_m:.3f} x {length:g} m = {straight:.1f} Pa"},
        {"step": 4, "operation": "fitting_loss", "detail": f"sum K x Pdyn = {k_total:.3f} x {pdyn:.2f} = {local:.1f} Pa"},
    ]
    return res, trace, [{"name": "air_properties", "value": "density 1.2 kg/m3, viscosity 1.81e-5 Pa.s", "basis": "Standard air at about 20 C; correct for altitude/temperature if significant."}], \
        ["Fitting K-factors are user-supplied and must come from ASHRAE/SMACNA data for the actual fittings."]


# ----------------------------------------------------- insulation / condensation
def insulation_condensation(inputs: Dict[str, Any]):
    tf = num(inputs, "fluid_temp_c", minimum=-30, maximum=30)
    amb = num(inputs, "ambient_db_c", minimum=5, maximum=55)
    rh = num(inputs, "ambient_rh_pct", minimum=10, maximum=100)
    od = num(inputs, "pipe_outer_diameter_mm", minimum=0, exclusive_min=True) / 1000
    k = num(inputs, "insulation_k_w_mk", default=0.035, minimum=0, exclusive_min=True)
    h = num(inputs, "surface_coeff_w_m2k", default=8.0, minimum=1, maximum=40)
    margin = num(inputs, "dew_point_margin_c", default=1.0, minimum=0, maximum=10)
    st = moist_air_state(amb, rh)
    tdp = st["dew_point_c"]
    if tf >= tdp - 1e-9:
        res = {"dew_point_c": r(tdp, 2), "minimum_thickness_mm": 0.0, "recommended_thickness_mm": 0.0,
               "note": "Fluid temperature is above the dew point; no condensation expected."}
        return res, [{"step": 1, "operation": "dew_point", "detail": f"Dew point {tdp:.2f} C <= fluid {tf:g} C"}], [], []
    target = tdp + margin
    ri = od / 2

    def surf(th: float) -> float:
        ro = ri + th
        rtot = math.log(ro / ri) / (2 * math.pi * k) + 1 / (2 * math.pi * ro * h)
        q = (amb - tf) / rtot
        return amb - q / (2 * math.pi * ro * h)

    lo, hi = 0.0, 0.5
    if surf(hi) < target:
        raise CalcError("No practical insulation thickness (<500 mm) prevents condensation under these conditions")
    for _ in range(80):
        mid = (lo + hi) / 2
        if surf(mid) >= target:
            hi = mid
        else:
            lo = mid
    th = hi * 1000
    std = next_standard(th, (6, 9, 13, 19, 25, 32, 40, 50, 63, 75, 100))
    res = {"dew_point_c": r(tdp, 2), "target_surface_temp_c": r(target, 2), "minimum_thickness_mm": r(th, 1),
           "recommended_thickness_mm": std, "surface_temp_at_recommended_c": r(surf(std / 1000) if std else float("nan"), 2)}
    trace = [
        {"step": 1, "operation": "dew_point", "detail": f"{amb:g} C / {rh:g}% RH -> dew point {tdp:.2f} C; surface target = dew point + {margin:g} = {target:.2f} C"},
        {"step": 2, "operation": "cylindrical_conduction", "detail": f"Ts = Tamb - q/(2 pi ro h) with q = (Tamb-Tf)/[ln(ro/ri)/(2 pi k) + 1/(2 pi ro h)], k = {k:g}, h = {h:g}"},
        {"step": 3, "operation": "solve_thickness", "detail": f"Minimum thickness {th:.1f} mm -> next standard {std} mm"},
    ]
    a = [{"name": "pipe_wall_and_fluid_film", "value": "neglected", "basis": "Pipe wall and internal film resistance assumed negligible (conservative for condensation)."}]
    return res, trace, a, ["Vapour barrier continuity is essential; thickness alone does not guarantee condensation control."]


# ------------------------------------------------------------ cable voltage drop
def cable_voltage_drop(inputs: Dict[str, Any]):
    p = num(inputs, "load_kw", minimum=0, exclusive_min=True)
    v = num(inputs, "voltage_v", default=415, minimum=100, maximum=33000)
    pf = num(inputs, "power_factor", default=0.85, minimum=0.1, maximum=1)
    eff = num(inputs, "efficiency_pct", default=100, minimum=30, maximum=100) / 100
    length = num(inputs, "length_m", minimum=0, exclusive_min=True)
    mat = str(inputs.get("conductor", "copper")).lower()
    rho = {"copper": 0.0225, "aluminium": 0.036, "aluminum": 0.036}.get(mat)
    if rho is None:
        raise CalcError("conductor must be copper or aluminium")
    x = num(inputs, "reactance_ohm_km", default=0.08, minimum=0)
    limit = num(inputs, "limit_pct", default=5.0, minimum=0, exclusive_min=True)
    cores = max(1, int(num(inputs, "parallel_runs", default=1, minimum=1)))
    i = p * 1000 / (math.sqrt(3) * v * pf * eff)
    sin = math.sqrt(1 - pf * pf)

    def vd(s: float) -> float:
        rr = rho / (s * cores) * length  # ohm
        xx = x / 1000 * length / cores
        return math.sqrt(3) * i * (rr * pf + xx * sin)

    sel = None
    for s in STD_CABLE_MM2:
        if vd(s) / v * 100 <= limit:
            sel = s
            break
    res = {"full_load_current_a": r(i, 2), "voltage_drop_limit_pct": limit, "conductor": mat, "parallel_runs": cores}
    if inputs.get("cross_section_mm2") not in (None, ""):
        s = num(inputs, "cross_section_mm2", minimum=0, exclusive_min=True)
        d = vd(s)
        res.update({"checked_cross_section_mm2": s, "voltage_drop_v": r(d, 2), "voltage_drop_pct": r(d / v * 100, 2),
                    "within_limit": d / v * 100 <= limit})
    res["minimum_standard_cross_section_mm2_for_drop"] = sel
    trace = [
        {"step": 1, "operation": "current", "detail": f"I = P/(sqrt3 x V x pf x eff) = {p:g}k/(1.732 x {v:g} x {pf:g} x {eff:g}) = {i:.2f} A"},
        {"step": 2, "operation": "voltage_drop", "detail": f"dV = sqrt3 x I x (R cos + X sin) x L; rho {rho} ohm.mm2/m, X {x} ohm/km"},
        {"step": 3, "operation": "select", "detail": f"Smallest standard section within {limit:g}%: {sel} mm2 (voltage-drop criterion only)"},
    ]
    a = [{"name": n, "value": val, "basis": "Default planning value; replace with project data."} for n, val in
         (("power_factor", pf), ("voltage_v", v), ("reactance_ohm_km", x), ("limit_pct", limit)) if inputs.get(n) in (None, "")]
    a.append({"name": "conductor_resistivity", "value": f"{rho} ohm.mm2/m at operating temperature", "basis": "Typical value at ~70 C."})
    return res, trace, a, ["Voltage-drop criterion only. Current-carrying capacity, derating, short-circuit withstand and protective-device coordination are not checked."]


# ------------------------------------------------------------- sprinkler demand
HAZARD = {  # class: (density L/min/m2, design area m2, hose stream L/min, duration min)  -- NFPA 13 reference
    "light": (4.1, 139.0, 379.0, 30), "ordinary_1": (6.1, 139.0, 946.0, 60), "ordinary_2": (8.1, 139.0, 946.0, 90),
    "extra_1": (12.2, 232.0, 1893.0, 90), "extra_2": (16.3, 232.0, 1893.0, 120),
}


def sprinkler_demand(inputs: Dict[str, Any]):
    hz = str(inputs.get("hazard_class", "")).strip().lower()
    if hz not in HAZARD:
        raise CalcError("hazard_class must be one of: " + ", ".join(HAZARD))
    dens, area, hose, dur = HAZARD[hz]
    if inputs.get("design_density_l_min_m2") not in (None, ""):
        dens = num(inputs, "design_density_l_min_m2", minimum=0, exclusive_min=True)
    if inputs.get("design_area_m2") not in (None, ""):
        area = num(inputs, "design_area_m2", minimum=0, exclusive_min=True)
    if inputs.get("hose_allowance_l_min") not in (None, ""):
        hose = num(inputs, "hose_allowance_l_min", minimum=0)
    if inputs.get("duration_min") not in (None, ""):
        dur = num(inputs, "duration_min", minimum=1)
    spk = dens * area
    total = spk * 1.0 + hose
    vol_m3 = total * dur / 1000
    res = {"hazard_class": hz, "design_density_l_min_m2": dens, "design_area_m2": area, "sprinkler_demand_l_min": r(spk, 0),
           "hose_allowance_l_min": hose, "total_demand_l_min": r(total, 0), "total_demand_m3h": r(total * 0.06, 1),
           "total_demand_usgpm": r(total * 0.264172, 0), "duration_min": dur, "water_volume_m3": r(vol_m3, 1)}
    trace = [{"step": 1, "operation": "sprinkler_flow", "detail": f"density x area = {dens:g} x {area:g} = {spk:.0f} L/min"},
             {"step": 2, "operation": "total_with_hose", "detail": f"{spk:.0f} + hose {hose:g} = {total:.0f} L/min"},
             {"step": 3, "operation": "volume", "detail": f"{total:.0f} L/min x {dur:g} min = {vol_m3:.1f} m3"}]
    w = ["Reference NFPA 13 density/area curve points. Indian projects must be checked against NBC Part 4, IS 15105 and TAC/insurer requirements.",
         "Remote-area adjustments, system losses and pump head are not calculated here."]
    hb = inputs.get("pump_head_bar")
    if hb not in (None, ""):
        head = num(inputs, "pump_head_bar", minimum=0, exclusive_min=True)
        pe = num(inputs, "pump_efficiency_pct", default=65, minimum=20, maximum=90) / 100
        hyd = (total / 60000.0) * head * 100.0  # m3/s * bar*100 kPa -> kW
        res.update({"pump_head_bar": head, "pump_hydraulic_kw": r(hyd, 1), "pump_shaft_kw": r(hyd / pe, 1)})
        trace.append({"step": 4, "operation": "pump_power", "detail": f"Q x H = {total / 60000:.4f} m3/s x {head * 100:g} kPa = {hyd:.1f} kW; shaft at {pe * 100:g}% = {hyd / pe:.1f} kW"})
    return res, trace, [{"name": "hazard_parameters", "value": f"{hz}: {dens} L/min/m2 over {area} m2", "basis": "NFPA 13 reference points; confirm the governing code and occupancy classification."}], w


# ------------------------------------------------------------------ hot water
def hot_water_heater(inputs: Dict[str, Any]):
    vol = num(inputs, "storage_volume_l", minimum=0, exclusive_min=True)
    cold = num(inputs, "cold_water_c", default=25, minimum=1, maximum=50)
    hot = num(inputs, "hot_water_c", default=55, minimum=30, maximum=90)
    hrs = num(inputs, "heat_up_time_h", default=2, minimum=0.1, maximum=24)
    eff = num(inputs, "heater_efficiency_pct", default=95, minimum=20, maximum=500) / 100
    if hot <= cold:
        raise CalcError("hot_water_c must be greater than cold_water_c")
    kwh = vol * 1.0 * CP_WATER * (hot - cold) / 3600
    kw = kwh / hrs / eff
    res = {"energy_to_heat_kwh": r(kwh, 2), "heater_input_kw": r(kw, 2), "standard_heater_kw": next_standard(kw, (1, 1.5, 2, 3, 4.5, 6, 9, 12, 15, 18, 24, 30, 36, 45, 60, 90, 120)),
           "recovery_rate_l_h": r(vol / hrs, 1)}
    trace = [{"step": 1, "operation": "energy", "detail": f"E = V x cp x dT = {vol:g} x 4.186 x ({hot:g}-{cold:g})/3600 = {kwh:.2f} kWh"},
             {"step": 2, "operation": "power", "detail": f"P = E/(t x eff) = {kwh:.2f}/({hrs:g} x {eff:g}) = {kw:.2f} kW"}]
    a = [{"name": n, "value": val, "basis": "Default planning value; confirm with the design brief."} for n, val in
         (("cold_water_c", cold), ("hot_water_c", hot), ("heat_up_time_h", hrs), ("heater_efficiency_pct", eff * 100)) if inputs.get(n) in (None, "")]
    return res, trace, a, ["Standing losses, simultaneous draw-off and legionella control temperatures are not modelled."]


# ------------------------------------------------------------ rainwater drainage
def rainwater_drainage(inputs: Dict[str, Any]):
    area = num(inputs, "catchment_area_m2", minimum=0, exclusive_min=True)
    i = num(inputs, "rainfall_intensity_mm_h", minimum=0, exclusive_min=True)
    c = num(inputs, "runoff_coefficient", default=0.9, minimum=0.05, maximum=1)
    slope = num(inputs, "pipe_slope", default=0.01, minimum=0.001, maximum=0.2)
    n = num(inputs, "manning_n", default=0.013, minimum=0.005, maximum=0.05)
    q_ls = c * i * area / 3600.0
    q_m3s = q_ls / 1000
    d_req = (q_m3s * n / (0.3117 * math.sqrt(slope))) ** (3 / 8) * 1000
    std = next_standard(d_req, STD_DRAIN_MM)
    res = {"design_flow_l_s": r(q_ls, 2), "design_flow_m3h": r(q_ls * 3.6, 1), "required_full_bore_diameter_mm": r(d_req, 1), "selected_diameter_mm": std}
    if std:
        d = std / 1000
        full_v = (1 / n) * (d / 4) ** (2 / 3) * math.sqrt(slope)
        res["full_bore_velocity_ms"] = r(full_v, 2)
    trace = [{"step": 1, "operation": "rational_method", "detail": f"Q = C x i x A / 3600 = {c:g} x {i:g} x {area:g}/3600 = {q_ls:.2f} L/s"},
             {"step": 2, "operation": "manning_full_bore", "detail": f"D = (Q n / (0.3117 sqrt S))^(3/8) = {d_req:.1f} mm at S = {slope:g}, n = {n:g}"}]
    a = [{"name": n_, "value": v_, "basis": "Default planning value; confirm with local rainfall data/code."} for n_, v_ in
         (("runoff_coefficient", c), ("pipe_slope", slope), ("manning_n", n)) if inputs.get(n_) in (None, "")]
    w = ["Rainfall intensity must come from the governing local code/IMD data for the required return period.", "Gutter, outlet and horizontal-pipe capacities must be checked separately."]
    if not std:
        w.append("Required diameter exceeds the standard list; split the catchment or select manually.")
    return res, trace, a, w


# ---------------------------------------------------------------------- solar
def solar_pv_sizing(inputs: Dict[str, Any]):
    annual = num(inputs, "annual_consumption_kwh", minimum=0, exclusive_min=True)
    offset = num(inputs, "offset_pct", default=100, minimum=1, maximum=100) / 100
    yld = num(inputs, "specific_yield_kwh_kwp_yr", default=1500, minimum=500, maximum=2500)
    apk = num(inputs, "area_per_kwp_m2", default=6.0, minimum=3, maximum=15)
    kwp = annual * offset / yld
    res = {"target_annual_generation_kwh": r(annual * offset, 0), "required_capacity_kwp": r(kwp, 2), "required_roof_area_m2": r(kwp * apk, 1)}
    trace = [{"step": 1, "operation": "capacity", "detail": f"kWp = {annual:,.0f} x {offset:g} / {yld:g} = {kwp:.2f} kWp"},
             {"step": 2, "operation": "area", "detail": f"{kwp:.2f} kWp x {apk:g} m2/kWp = {kwp * apk:.1f} m2"}]
    if inputs.get("available_area_m2") not in (None, ""):
        av = num(inputs, "available_area_m2", minimum=0, exclusive_min=True)
        cap = av / apk
        res.update({"available_area_m2": av, "capacity_limited_by_area_kwp": r(min(kwp, cap), 2), "area_is_limiting": cap < kwp,
                    "achievable_offset_pct": r(min(1.0, cap * yld / annual) * 100, 1)})
        trace.append({"step": 3, "operation": "area_limit", "detail": f"Available {av:g} m2 supports {cap:.2f} kWp"})
    a = [{"name": n, "value": v, "basis": "Default planning value; replace with a site-specific yield study."} for n, v in
         (("specific_yield_kwh_kwp_yr", yld), ("area_per_kwp_m2", apk), ("offset_pct", offset * 100)) if inputs.get(n) in (None, "")]
    return res, trace, a, ["Shading, orientation, degradation, inverter sizing and net-metering limits are not assessed."]


# --------------------------------------------------------------------- carbon
def carbon_emissions(inputs: Dict[str, Any]):
    kwh = num(inputs, "annual_consumption_kwh", minimum=0)
    gf = num(inputs, "grid_factor_kg_kwh", default=0.71, minimum=0)
    scope2 = kwh * gf / 1000
    res = {"scope2_electricity_tco2e": r(scope2, 2), "grid_factor_kg_kwh": gf}
    trace = [{"step": 1, "operation": "scope2", "detail": f"{kwh:,.0f} kWh x {gf:g} kg/kWh / 1000 = {scope2:.2f} tCO2e"}]
    total = scope2
    if inputs.get("refrigerant_charge_kg") not in (None, ""):
        ch = num(inputs, "refrigerant_charge_kg", minimum=0)
        leak = num(inputs, "leak_rate_pct", minimum=0, maximum=100)
        gwp = num(inputs, "refrigerant_gwp", minimum=0)
        ref = ch * leak / 100 * gwp / 1000
        res["refrigerant_leakage_tco2e"] = r(ref, 2)
        total += ref
        trace.append({"step": 2, "operation": "refrigerant_leakage", "detail": f"{ch:g} kg x {leak:g}% x GWP {gwp:g} / 1000 = {ref:.2f} tCO2e"})
    res["total_tco2e"] = r(total, 2)
    if inputs.get("reduction_kwh") not in (None, ""):
        red = num(inputs, "reduction_kwh", minimum=0, maximum=kwh) * gf / 1000
        res["avoided_tco2e_from_reduction"] = r(red, 2)
        trace.append({"step": 3, "operation": "avoided", "detail": f"{inputs['reduction_kwh']} kWh saved x {gf:g} / 1000 = {red:.2f} tCO2e"})
    a = []
    if inputs.get("grid_factor_kg_kwh") in (None, ""):
        a.append({"name": "grid_factor_kg_kwh", "value": gf, "basis": "Indicative Indian grid average; replace with the current CEA CO2 Baseline Database value for the reporting year."})
    return res, trace, a, ["Scope 2 (location-based) and optional refrigerant leakage only; other scopes are not included."]
