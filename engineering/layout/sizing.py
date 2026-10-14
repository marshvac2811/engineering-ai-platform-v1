"""Preliminary sizing of the concept duct trunk and sprinkler main along the routed tree.

RULE-BASED AND PRELIMINARY. The routed centre lines are split at junctions, loads are accumulated from the terminals
back to the plant, and each run is sized from the load it carries:
  * Ducts: round, smallest standard diameter whose velocity is within the stated limit; friction from Darcy-Weisbach
    (same formula as the governed duct_pressure_drop calculator). Fittings, grilles, coils and filters are NOT included.
  * Sprinkler mains: NFPA 13 style light-hazard pipe-schedule head counts per nominal size. Above the schedule limit the
    run is flagged for a hydraulic calculation. Hazard class, supply and hydraulics must be confirmed by a fire engineer.
Deterministic. Every assumption is returned with the result.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any, Dict, List, Sequence, Tuple

from skills.calculators.formulas import duct_pressure_drop

Pt = Tuple[float, float]
DUCT_STD_MM = (100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600)
# NFPA 13 light-hazard pipe schedule (steel): maximum sprinkler heads per nominal size
SPRINKLER_SCHEDULE = ((2, "DN25"), (3, "DN32"), (5, "DN40"), (10, "DN50"), (20, "DN65"), (40, "DN80"), (65, "DN90"), (100, "DN100"))


def _key(p: Pt) -> Pt:
    return (round(p[0], 3), round(p[1], 3))


def _on_segment(p: Pt, a: Pt, b: Pt, tol: float = 1e-3) -> bool:
    if abs(a[0] - b[0]) < tol and abs(p[0] - a[0]) < tol:
        return min(a[1], b[1]) + tol < p[1] < max(a[1], b[1]) - tol
    if abs(a[1] - b[1]) < tol and abs(p[1] - a[1]) < tol:
        return min(a[0], b[0]) + tol < p[0] < max(a[0], b[0]) - tol
    return False


def split_at_junctions(segs: Sequence[Tuple[Pt, Pt]]) -> List[Tuple[Pt, Pt]]:
    """A branch joins the middle of an earlier straight run; split that run there so the tree has real nodes."""
    segs = [(_key(a), _key(b)) for a, b in segs if _key(a) != _key(b)]
    nodes = {p for s in segs for p in s}
    out: List[Tuple[Pt, Pt]] = []
    for a, b in segs:
        cuts = [p for p in nodes if _on_segment(p, a, b)]
        cuts.sort(key=lambda p: (p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2)
        pts = [a] + cuts + [b]
        out += list(zip(pts, pts[1:]))
    return out


def _tree(segs: List[Tuple[Pt, Pt]], plant: Pt, loads: Sequence[Tuple[Pt, float]]):
    adj: Dict[Pt, set] = {}
    for a, b in segs:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    nodes = sorted(adj)
    dist = lambda p, q: (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
    parent: Dict[Pt, Pt] = {}
    order: List[Pt] = []
    seen: set = set()
    while len(seen) < len(nodes):
        root = min((n for n in nodes if n not in seen), key=lambda n: (dist(n, plant), n))
        seen.add(root)
        dq = deque([root])
        while dq:
            cur = dq.popleft()
            order.append(cur)
            for nb in sorted(adj[cur]):
                if nb not in seen:
                    seen.add(nb)
                    parent[nb] = cur
                    dq.append(nb)
    acc: Dict[Pt, float] = {n: 0.0 for n in nodes}
    for pt, q in loads:
        acc[min(nodes, key=lambda n: (dist(n, pt), n))] += q
    for n in reversed(order):
        if n in parent:
            acc[parent[n]] += acc[n]
    return parent, acc, order


def _depth_loss(parent: Dict[Pt, Pt], loss: Dict[Pt, float], order: List[Pt]) -> Dict[Pt, float]:
    cum: Dict[Pt, float] = {}
    for n in order:
        cum[n] = cum.get(parent[n], 0.0) + loss.get(n, 0.0) if n in parent else 0.0
    return cum


def size_ducts(segs, plant: Pt, loads_m3h: Sequence[Tuple[Pt, float]], *, max_velocity_ms: float = 6.0) -> Dict[str, Any]:
    segs = split_at_junctions(segs)
    if not segs or not loads_m3h:
        return {"runs": [], "by_size": [], "critical_loss_pa": 0.0}
    parent, acc, order = _tree(segs, plant, loads_m3h)
    runs, loss = [], {}
    for child, par in parent.items():
        q = acc[child]
        length = abs(child[0] - par[0]) + abs(child[1] - par[1])
        if q <= 0 or length <= 0:
            continue
        ideal = math.sqrt(4 * (q / 3600) / (math.pi * max_velocity_ms)) * 1000
        d = next((x for x in DUCT_STD_MM if x >= ideal), None)
        note = ""
        if d is None:
            d, note = DUCT_STD_MM[-1], "Exceeds the largest round size; use rectangular or split the run"
        res = duct_pressure_drop({"airflow_m3h": q, "length_m": length, "diameter_mm": d})[0]
        loss[child] = res["straight_duct_loss_pa"]
        runs.append({"a": par, "b": child, "length_m": round(length, 2), "airflow_m3h": round(q), "size": f"{d} dia", "diameter_mm": d,
                     "velocity_ms": res["velocity_ms"], "friction_pa_per_m": res["friction_pa_per_m"], "straight_loss_pa": res["straight_duct_loss_pa"], "note": note})
    cum = _depth_loss(parent, loss, order)
    crit = max(cum.values()) if cum else 0.0
    return {"runs": runs, "by_size": _by_size(runs, "length_m"), "critical_loss_pa": round(crit, 1)}


def size_sprinkler_mains(segs, plant: Pt, heads: Sequence[Tuple[Pt, float]]) -> Dict[str, Any]:
    segs = split_at_junctions(segs)
    if not segs or not heads:
        return {"runs": [], "by_size": []}
    parent, acc, _ = _tree(segs, plant, heads)
    runs = []
    for child, par in parent.items():
        n = acc[child]
        length = abs(child[0] - par[0]) + abs(child[1] - par[1])
        if n <= 0 or length <= 0:
            continue
        size = next((s for lim, s in SPRINKLER_SCHEDULE if n <= lim), None)
        note = ""
        if size is None:
            size, note = "DN100", "Above pipe-schedule limit: hydraulic calculation required, size shown is a minimum"
        runs.append({"a": par, "b": child, "length_m": round(length, 2), "heads": int(round(n)), "size": size, "note": note})
    return {"runs": runs, "by_size": _by_size(runs, "length_m")}


def _by_size(runs: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    tot: Dict[str, float] = {}
    for r in runs:
        tot[r["size"]] = tot.get(r["size"], 0.0) + r[key]
    def sk(s: str) -> int:
        return int("".join(c for c in s.split()[0] if c.isdigit()) or 0)
    return [{"size": s, "length_m": round(v, 1)} for s, v in sorted(tot.items(), key=lambda kv: sk(kv[0]))]
