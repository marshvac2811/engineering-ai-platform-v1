"""
Controlled snapshot of the user's GitHub duct-sizing-calculator source.
Source revision: 1410b71e16a4fe4b1c6b04f023291d7b0f458d68

This file intentionally preserves the source calculation logic. Changes to
engineering formulas should happen in the source repository and then be
reviewed before updating this snapshot.
"""
import math

AIR_DENSITY = 1.2
AIR_VISCOSITY = 1.81e-5

DUCT_MATERIALS = {
    "gss": {"label": "Galvanized Steel Sheet (GSS)", "roughness_mm": 0.09},
    "pu_panel": {"label": "PU Panel Duct", "roughness_mm": 0.03},
    "fabric": {"label": "Fabric Duct", "roughness_mm": 1.5},
    "flexible": {"label": "Flexible Duct (extended)", "roughness_mm": 2.5},
}

STANDARD_DUCT_SIZES_MM = [100, 125, 150, 200, 250, 300, 350, 400, 450, 500,
                          550, 600, 650, 700, 750, 800, 900, 1000, 1200]

FITTING_LD_RATIOS = {
    "elbow_90": {"label": "90° Elbow", "ld_ratio": 15},
    "elbow_45": {"label": "45° Elbow", "ld_ratio": 7},
    "tee_branch": {"label": "Tee (branch flow)", "ld_ratio": 30},
    "damper": {"label": "Volume Control Damper", "ld_ratio": 5},
    "take_off": {"label": "Duct Take-off", "ld_ratio": 20},
}

VELOCITY_HEALTHY_MIN = 4.0
VELOCITY_HEALTHY_MAX = 10.0


def friction_factor(velocity_ms: float, diameter_m: float, roughness_mm: float,
                    air_density: float = AIR_DENSITY, air_viscosity: float = AIR_VISCOSITY) -> float:
    if velocity_ms <= 0 or diameter_m <= 0:
        return 0.02
    epsilon_m = roughness_mm / 1000.0
    reynolds = air_density * velocity_ms * diameter_m / air_viscosity
    if reynolds < 1:
        return 0.02
    term = epsilon_m / (3.7 * diameter_m) + 5.74 / (reynolds ** 0.9)
    return 0.25 / (math.log10(term) ** 2)


def pressure_loss_per_m(velocity_ms: float, diameter_m: float, roughness_mm: float,
                        air_density: float = AIR_DENSITY, air_viscosity: float = AIR_VISCOSITY) -> float:
    f = friction_factor(velocity_ms, diameter_m, roughness_mm, air_density, air_viscosity)
    return f * (air_density * velocity_ms ** 2) / (2 * diameter_m)


def _velocity_note(v):
    if v < VELOCITY_HEALTHY_MIN:
        return "Below typical range — duct may be oversized"
    elif v <= VELOCITY_HEALTHY_MAX:
        return "Within typical healthy range"
    else:
        return "Above typical range — risk of noise/erosion, consider a larger duct"


def size_duct_velocity_method(flow_m3hr: float, target_velocity_ms: float, roughness_mm: float,
                              air_density: float = AIR_DENSITY, air_viscosity: float = AIR_VISCOSITY) -> dict:
    if flow_m3hr <= 0:
        raise ValueError("Flow rate must be greater than zero")
    if target_velocity_ms <= 0:
        raise ValueError("Target velocity must be greater than zero")

    q_m3s = flow_m3hr / 3600.0
    required_diameter_m = math.sqrt(4 * q_m3s / (math.pi * target_velocity_ms))
    required_diameter_mm = required_diameter_m * 1000

    recommended_mm = _round_up_to_standard(required_diameter_mm)
    recommended_m = recommended_mm / 1000.0

    actual_area_m2 = math.pi * (recommended_m / 2) ** 2
    actual_velocity = q_m3s / actual_area_m2
    actual_friction = pressure_loss_per_m(actual_velocity, recommended_m, roughness_mm, air_density, air_viscosity)

    return {
        "method": "Velocity Method",
        "flow_m3hr": flow_m3hr,
        "target_velocity_ms": target_velocity_ms,
        "required_diameter_mm": round(required_diameter_mm, 1),
        "recommended_diameter_mm": recommended_mm,
        "actual_velocity_ms": round(actual_velocity, 2),
        "actual_friction_pa_per_m": round(actual_friction, 3),
        "velocity_note": _velocity_note(actual_velocity),
    }


def size_duct_equal_friction_method(flow_m3hr: float, target_friction_pa_per_m: float,
                                     roughness_mm: float, air_density: float = AIR_DENSITY,
                                     air_viscosity: float = AIR_VISCOSITY) -> dict:
    if flow_m3hr <= 0:
        raise ValueError("Flow rate must be greater than zero")
    if target_friction_pa_per_m <= 0:
        raise ValueError("Target friction rate must be greater than zero")

    q_m3s = flow_m3hr / 3600.0

    def loss_at_diameter(d_m):
        area = math.pi * (d_m / 2) ** 2
        v = q_m3s / area
        return pressure_loss_per_m(v, d_m, roughness_mm, air_density, air_viscosity) - target_friction_pa_per_m

    lo, hi = 0.02, 3.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if loss_at_diameter(lo) > 0 and loss_at_diameter(mid) > 0:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 1e-6:
            break

    required_diameter_m = (lo + hi) / 2
    required_diameter_mm = required_diameter_m * 1000

    recommended_mm = _round_up_to_standard(required_diameter_mm)
    recommended_m = recommended_mm / 1000.0

    actual_area_m2 = math.pi * (recommended_m / 2) ** 2
    actual_velocity = q_m3s / actual_area_m2
    actual_friction = pressure_loss_per_m(actual_velocity, recommended_m, roughness_mm, air_density, air_viscosity)

    return {
        "method": "Equal Friction Method",
        "flow_m3hr": flow_m3hr,
        "target_friction_pa_per_m": target_friction_pa_per_m,
        "required_diameter_mm": round(required_diameter_mm, 1),
        "recommended_diameter_mm": recommended_mm,
        "actual_velocity_ms": round(actual_velocity, 2),
        "actual_friction_pa_per_m": round(actual_friction, 3),
        "velocity_note": _velocity_note(actual_velocity),
    }


def _round_up_to_standard(diameter_mm: float) -> int:
    for size in STANDARD_DUCT_SIZES_MM:
        if size >= diameter_mm:
            return size
    return STANDARD_DUCT_SIZES_MM[-1]


def calculate_fittings_loss(diameter_mm: float, straight_length_m: float,
                             friction_pa_per_m: float, fitting_counts: dict) -> dict:
    if diameter_mm <= 0 or straight_length_m < 0 or friction_pa_per_m < 0:
        raise ValueError("Diameter, length, and friction rate must be valid positive numbers")

    diameter_m = diameter_mm / 1000.0
    fitting_breakdown = []
    total_fitting_eq_length_m = 0.0

    for key, count in fitting_counts.items():
        if count and count > 0:
            ld_ratio = FITTING_LD_RATIOS[key]["ld_ratio"]
            eq_length = ld_ratio * diameter_m * count
            total_fitting_eq_length_m += eq_length
            fitting_breakdown.append({
                "label": FITTING_LD_RATIOS[key]["label"],
                "count": count,
                "ld_ratio": ld_ratio,
                "equivalent_length_m": round(eq_length, 2),
            })

    total_equivalent_length_m = straight_length_m + total_fitting_eq_length_m
    total_pressure_loss_pa = total_equivalent_length_m * friction_pa_per_m

    return {
        "straight_length_m": straight_length_m,
        "fitting_breakdown": fitting_breakdown,
        "total_fitting_eq_length_m": round(total_fitting_eq_length_m, 2),
        "total_equivalent_length_m": round(total_equivalent_length_m, 2),
        "total_pressure_loss_pa": round(total_pressure_loss_pa, 1),
        "total_pressure_loss_mmwg": round(total_pressure_loss_pa / 9.80665, 2),
        "total_pressure_loss_inwg": round(total_pressure_loss_pa / 249.089, 3),
    }


def calculate_rectangular_equivalent(width_mm: float, height_mm: float, flow_m3hr: float) -> dict:
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("Width and height must be greater than zero")
    if flow_m3hr <= 0:
        raise ValueError("Flow rate must be greater than zero")

    a, b = width_mm, height_mm
    d_eq_mm = 1.30 * ((a * b) ** 0.625) / ((a + b) ** 0.25)

    q_m3s = flow_m3hr / 3600.0
    area_m2 = (width_mm / 1000.0) * (height_mm / 1000.0)
    velocity_ms = q_m3s / area_m2

    aspect_ratio = max(a, b) / min(a, b)
    if aspect_ratio > 4:
        aspect_note = f"Aspect ratio {aspect_ratio:.1f}:1 exceeds typical 4:1 guideline — consider a less flat profile"
    else:
        aspect_note = f"Aspect ratio {aspect_ratio:.1f}:1 — within typical guideline"

    return {
        "width_mm": width_mm,
        "height_mm": height_mm,
        "equivalent_diameter_mm": round(d_eq_mm, 1),
        "actual_velocity_ms": round(velocity_ms, 2),
        "aspect_ratio": round(aspect_ratio, 2),
        "aspect_note": aspect_note,
        "velocity_note": _velocity_note(velocity_ms),
    }
