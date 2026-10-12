"""Wall-aware centre-line routing for the concept layout.

Plan free space is rasterised into a grid; wall lines (slightly thickened) are blocked, door openings stay open. Each
target is joined to the growing tree by the cheapest path, so duct trunks and pipe mains share one run instead of
fanning out as separate lines. Deterministic (stable tie-breaks). If a target cannot be reached (for example a plan
without door openings) the route falls back to a straight Manhattan run and is reported as 'crosses walls'.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

Pt = Tuple[float, float]
Cell = Tuple[int, int]
TURN_PENALTY = 3.0


@dataclass
class Grid:
    minx: float
    miny: float
    cell: float
    nx: int
    ny: int
    blocked: Set[Cell] = field(default_factory=set)

    def to_cell(self, p: Pt) -> Cell:
        return (int(round((p[0] - self.minx) / self.cell)), int(round((p[1] - self.miny) / self.cell)))

    def to_xy(self, c: Cell) -> Pt:
        return (round(self.minx + c[0] * self.cell, 3), round(self.miny + c[1] * self.cell, 3))

    def inside(self, c: Cell) -> bool:
        return 0 <= c[0] < self.nx and 0 <= c[1] < self.ny


def build_grid(walls: Sequence[Tuple[Pt, Pt]], bounds: Tuple[float, float, float, float], *, margin: float = 3.0, max_cells: int = 90000) -> Grid:
    minx, miny, maxx, maxy = bounds
    minx, miny, maxx, maxy = minx - margin, miny - margin, maxx + margin, maxy + margin
    span = max(maxx - minx, maxy - miny)
    cell = min(0.4, max(0.2, span / 300.0))
    while ((maxx - minx) / cell) * ((maxy - miny) / cell) > max_cells:
        cell *= 1.25
    nx, ny = int(math.ceil((maxx - minx) / cell)) + 1, int(math.ceil((maxy - miny) / cell)) + 1
    g = Grid(minx, miny, cell, nx, ny)
    lines = [LineString(w) for w in walls if w[0] != w[1]]
    if lines:
        thick = prep(unary_union(lines).buffer(cell * 0.55, cap_style=2, join_style=2))
        for i in range(nx):
            for j in range(ny):
                if thick.contains(Point(minx + i * cell, miny + j * cell)):
                    g.blocked.add((i, j))
    return g


def nearest_free(g: Grid, p: Pt, limit: int = 12) -> Optional[Cell]:
    c0 = g.to_cell(p)
    for r in range(limit + 1):
        best = None
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if max(abs(di), abs(dj)) != r:
                    continue
                c = (c0[0] + di, c0[1] + dj)
                if g.inside(c) and c not in g.blocked:
                    d = (di * di + dj * dj, c)
                    if best is None or d < best:
                        best = d
        if best:
            return best[1]
    return None


def _path_to_tree(g: Grid, start: Cell, tree: Set[Cell]) -> Optional[List[Cell]]:
    """Cheapest 4-connected path from start to any cell of the tree (Dijkstra with a turn penalty)."""
    if start in tree:
        return [start]
    heap: List[Tuple[float, int, Cell, Tuple[int, int]]] = [(0.0, 0, start, (0, 0))]
    best: Dict[Tuple[Cell, Tuple[int, int]], float] = {(start, (0, 0)): 0.0}
    prev: Dict[Tuple[Cell, Tuple[int, int]], Tuple[Cell, Tuple[int, int]]] = {}
    tick = 0
    while heap:
        cost, _, cur, d = heapq.heappop(heap)
        if best.get((cur, d), 1e18) < cost:
            continue
        if cur in tree:
            out = [cur]
            key = (cur, d)
            while key in prev:
                key = prev[key]
                out.append(key[0])
            return out[::-1]
        for nd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cur[0] + nd[0], cur[1] + nd[1])
            if not g.inside(nxt) or nxt in g.blocked:
                continue
            c2 = cost + 1.0 + (TURN_PENALTY if d != (0, 0) and nd != d else 0.0)
            key = (nxt, nd)
            if c2 < best.get(key, 1e18):
                best[key] = c2
                prev[key] = (cur, d)
                tick += 1
                heapq.heappush(heap, (c2, tick, nxt, nd))
    return None


def _simplify(points: List[Pt]) -> List[Pt]:
    out: List[Pt] = []
    for p in points:
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if (abs(a[0] - b[0]) < 1e-9 and abs(b[0] - p[0]) < 1e-9) or (abs(a[1] - b[1]) < 1e-9 and abs(b[1] - p[1]) < 1e-9):
                out[-1] = p
                continue
        out.append(p)
    return out


@dataclass
class RouteResult:
    segments: List[Tuple[Pt, Pt]]
    crossing_targets: List[Pt]            # targets joined by a straight run because no open path existed


def route_tree(g: Grid, root: Pt, targets: Sequence[Pt]) -> RouteResult:
    """Join every target to the root (plant) by a shared tree of runs. Returns centre-line segments in metres."""
    root_c = nearest_free(g, root)
    if root_c is None:
        return RouteResult([], list(targets))
    tree: Set[Cell] = {root_c}
    segs: List[Tuple[Pt, Pt]] = []
    crossing: List[Pt] = []
    for t in targets:
        sc = nearest_free(g, t)
        path = _path_to_tree(g, sc, tree) if sc is not None else None
        if not path:
            crossing.append(t)
            mid = (t[0], root[1])
            segs += [(root, mid), (mid, t)] if (t[0] != root[0] and t[1] != root[1]) else [(root, t)]
            continue
        pts = _simplify([g.to_xy(c) for c in path])
        tt = (round(t[0], 3), round(t[1], 3))
        if pts and pts[-1] != tt and pts[0] != tt:
            pts = [tt] + pts if False else pts
        tree.update(path)
        segs += list(zip(pts, pts[1:]))
    return RouteResult(segs, crossing)
