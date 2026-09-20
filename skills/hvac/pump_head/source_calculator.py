"""Deterministic transcription of the audited pump-head calculator source."""
from __future__ import annotations
import math

SOURCE_VISCOSITY_M2_S = 1.0e-6
G = 9.81
M_TO_KPA = 9.81
M_TO_FT = 3.28084
KPA_TO_BAR = 1.0 / 100.0
KPA_TO_PSI = 0.145038

PIPE_MATERIALS = {
    "gi": {"label": "GI (galvanised steel)", "roughness_mm": 0.15},
    "ms_cs": {"label": "MS / CS (black steel)", "roughness_mm": 0.05},
    "copper": {"label": "Copper", "roughness_mm": 0.0015},
    "upvc_pvc": {"label": "uPVC / PVC", "roughness_mm": 0.0015},
    "hdpe": {"label": "HDPE", "roughness_mm": 0.007},
}

FITTING_DEFAULTS = [
    ("90° standard elbow", 30),
    ("90° long radius elbow", 20),
    ("45° elbow", 16),
    ("Tee — through flow", 20),
    ("Tee — branch flow", 60),
    ("Gate valve (full open)", 8),
    ("Butterfly valve", 45),
    ("Check valve (swing)", 135),
    ("Y-strainer", 250),
]


def calculate(flow_m3hr: float, diameter_mm: float, roughness_mm: float,
              straight_length_m: float, fittings: list[dict] | None,
              static_head_m: float, equipment_losses_m: list[dict] | None,
              margin_pct: float, viscosity_m2_s: float = SOURCE_VISCOSITY_M2_S,
              gravity: float = G) -> dict:
    if flow_m3hr < 0 or diameter_mm <= 0 or roughness_mm < 0:
        raise ValueError("Flow must be non-negative, and diameter/roughness must be valid")
    if straight_length_m < 0 or static_head_m < 0 or margin_pct < 0:
        raise ValueError("Length, static head, and margin must be non-negative")

    d = diameter_mm / 1000.0
    eps = roughness_mm / 1000.0
    q = flow_m3hr / 3600.0
    area = math.pi / 4 * d * d
    v = q / area if area > 0 else 0.0
    re = v * d / viscosity_m2_s if viscosity_m2_s > 0 else 0.0

    f = 0.0
    if re > 0:
        term = eps / (3.7 * d) + 5.74 / (re ** 0.9)
        if term > 0:
            f = 0.25 / (math.log10(term) ** 2)

    fitting_rows: list[dict] = []
    fittings_total = 0.0
    for row in fittings or []:
        name = str(row.get("name", "Fitting"))
        ld = float(row.get("ld_ratio", 0))
        qty = float(row.get("quantity", 0))
        if ld < 0 or qty < 0:
            raise ValueError(f"Negative fitting L/D or quantity: {name}")
        eq_len = ld * d * qty
        fittings_total += eq_len
        fitting_rows.append({"name": name, "ld_ratio": ld, "quantity": qty, "equivalent_length_m": round(eq_len, 6)})

    total_len = straight_length_m + fittings_total
    friction_head = f * (total_len / d) * (v * v) / (2 * gravity) if d > 0 else 0.0

    equip_total = 0.0
    equip_rows: list[dict] = []
    for row in equipment_losses_m or []:
        name = str(row.get("name", "Component"))
        loss = float(row.get("loss_m", 0))
        if loss < 0:
            raise ValueError(f"Negative equipment loss: {name}")
        equip_total += loss
        equip_rows.append({"name": name, "loss_m": loss})

    subtotal = friction_head + static_head_m + equip_total
    margin_value = subtotal * margin_pct / 100.0
    tdh = subtotal + margin_value
    kpa = tdh * gravity

    return {
        "flow_m3hr": flow_m3hr,
        "diameter_mm": diameter_mm,
        "roughness_mm": roughness_mm,
        "straight_length_m": straight_length_m,
        "velocity_ms": round(v, 6),
        "reynolds_number": round(re),
        "friction_factor": round(f, 8),
        "fittings": fitting_rows,
        "fittings_equivalent_length_m": round(fittings_total, 6),
        "total_equivalent_length_m": round(total_len, 6),
        "friction_head_m": round(friction_head, 6),
        "static_head_m": round(static_head_m, 6),
        "equipment_losses": equip_rows,
        "equipment_losses_m": round(equip_total, 6),
        "subtotal_head_m": round(subtotal, 6),
        "margin_pct": margin_pct,
        "margin_head_m": round(margin_value, 6),
        "total_dynamic_head_m": round(tdh, 6),
        "total_dynamic_head_kpa": round(kpa, 6),
        "total_dynamic_head_bar": round(kpa * KPA_TO_BAR, 6),
        "total_dynamic_head_ft": round(tdh * M_TO_FT, 6),
        "total_dynamic_head_psi": round(kpa * KPA_TO_PSI, 6),
    }
