"""Preliminary duct sizes for runs the drawing leaves unsized, from the number of diffusers each run feeds.

PRELIMINARY. Only runs with no size label (and none carried from a labelled continuation) are sized. Each diffuser is
assumed to pass the same airflow (given by the user). Ducts are sized as round, at the velocity limit used in the
concept layout sizer. The air handler / fan position is not on a services drawing, so it is ASSUMED to be the end of the
unsized network that is farthest from the diffusers; if that is wrong, the sizes are wrong. Fittings, balancing and
pressure drop are not checked. A designer must confirm every size.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from engineering.layout.sizing import size_ducts

MAX_FEED_DISTANCE_M = 2.0


def _key(p) -> Tuple[float, float]:
    return (round(p[0], 3), round(p[1], 3))


def _dist_pt_seg(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def autosize_unsized_ducts(segs, m, cmh_per_diffuser: float) -> None:
    """Set .size on unsized duct segments (in place) and record the assumption on the measurement."""
    unsized = [s for s in segs if s.size == "unsized"]
    diffusers = m.device_points.get("diffuser") or []
    if not unsized or cmh_per_diffuser <= 0:
        return
    if not diffusers:
        m.warnings.append("Duct sizes were requested from diffuser airflow, but no diffusers were found on the drawing, so the unsized ducts stay unsized.")
        return
    labelled = [s for s in segs if s.size != "unsized"]
    loads = []
    for p in diffusers:
        du = min(_dist_pt_seg(p, s.a, s.b) for s in unsized)
        dl = min((_dist_pt_seg(p, s.a, s.b) for s in labelled), default=1e9)
        if du <= MAX_FEED_DISTANCE_M and du <= dl:
            loads.append((p, float(cmh_per_diffuser)))
    if not loads:
        m.warnings.append(f"No diffuser lies within {MAX_FEED_DISTANCE_M:g} m of an unsized duct, so the unsized ducts stay unsized.")
        return
    pairs = [(s.a, s.b) for s in unsized]
    deg: Dict[Tuple[float, float], int] = {}
    for a, b in pairs:
        for p in (_key(a), _key(b)):
            deg[p] = deg.get(p, 0) + 1
    leaves = [p for p, d in deg.items() if d == 1] or list(deg)
    cx = sum(p[0] for p, _q in loads) / len(loads)
    cy = sum(p[1] for p, _q in loads) / len(loads)
    plant = max(sorted(leaves), key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
    res = size_ducts(pairs, plant, loads)
    sized = {frozenset((_key(r["a"]), _key(r["b"]))): r["diameter_mm"] for r in res["runs"]}
    done = 0.0
    for s in unsized:
        d = sized.get(frozenset((_key(s.a), _key(s.b))))
        if d:
            s.size = str(d)
            done += s.length
    if done:
        m.autosized_m += done
        m.warnings.append(
            f"PRELIMINARY: {done:.1f} m of duct had no size on the drawing. It was sized as round duct from {len(loads)} diffuser(s) at "
            f"{cmh_per_diffuser:g} m3/h each (6 m/s limit), assuming the air handler is at the far end of the unsized network at "
            f"({plant[0]:.1f}, {plant[1]:.1f}) m. These sizes are not from the drawing and must be confirmed by the designer before ordering.")
