"""Room detection from wall line work (door gaps closed) and label assignment. Pure shapely, deterministic."""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from engineering.plan.model import PlanRoom

MIN_ROOM_M2 = 2.0
GAP_CLOSE_M = 1.1          # door openings up to this width are bridged when detecting rooms


def rooms_from_walls(segments: Sequence[Tuple[Tuple[float, float], Tuple[float, float]]], *, gap_m: float = GAP_CLOSE_M) -> List[Polygon]:
    """Free-space faces enclosed by wall segments. The exterior is discarded. Segments are in metres."""
    lines = [LineString(s) for s in segments if s[0] != s[1]]
    if not lines:
        return []
    walls = unary_union(lines)
    minx, miny, maxx, maxy = walls.bounds
    pad = gap_m * 3
    world = box(minx - pad, miny - pad, maxx + pad, maxy + pad)
    half = gap_m / 2.0
    thick = walls.buffer(half, join_style=2, cap_style=3)
    free = world.difference(thick)
    faces = list(free.geoms) if isinstance(free, MultiPolygon) else [free]
    rooms: List[Polygon] = []
    for f in faces:
        if f.is_empty or f.area < 1e-6:
            continue
        # exterior = the face that reaches the padded boundary of the world
        if f.buffer(1e-6).intersects(world.exterior):
            continue
        # undo the closing buffer: grow back to the wall centre line
        restored = f.buffer(half, join_style=2)
        restored = restored.intersection(world)
        for p in (list(restored.geoms) if isinstance(restored, MultiPolygon) else [restored]):
            if isinstance(p, Polygon) and p.area >= MIN_ROOM_M2:
                rooms.append(p.simplify(0.05))
    rooms.sort(key=lambda p: -p.area)
    kept = rooms
    return kept


def assign_labels(polys: Sequence[Polygon], labels: Iterable[Tuple[str, Tuple[float, float]]]) -> List[Tuple[str, str]]:
    """Return (name, source) for each polygon from text labels whose insertion point lies inside it."""
    labs = list(labels)
    out: List[Tuple[str, str]] = []
    for poly in polys:
        inside = [t for t, (x, y) in labs if t.strip() and poly.contains(Point(x, y))]
        # ignore pure dimensions / numbers / area annotations when a real name exists
        names = [t for t in inside if any(c.isalpha() for c in t) and not _is_area_text(t)]
        out.append((names[0].strip(), "label") if names else ("", "generated"))
    return out


def _is_area_text(t: str) -> bool:
    low = t.lower().replace(" ", "")
    return any(low.endswith(u) for u in ("m2", "m²", "sqm", "sqft", "sft")) or low.replace(".", "").replace(",", "").isdigit()


def to_plan_rooms(polys: Sequence[Polygon], names: Sequence[Tuple[str, str]], *, confidence: str = "medium") -> List[PlanRoom]:
    order = sorted(range(len(polys)), key=lambda i: (round(-polys[i].centroid.y, 1), polys[i].centroid.x))
    rooms: List[PlanRoom] = []
    for n, i in enumerate(order, 1):
        p, (name, src) = polys[i], names[i]
        rid = f"R{n:02d}"
        c = p.centroid
        rooms.append(PlanRoom(room_id=rid, name=name or f"Space {n}", polygon=[(round(x, 3), round(y, 3)) for x, y in p.exterior.coords[:-1]],
                              area_m2=round(p.area, 2), centroid=(round(c.x, 3), round(c.y, 3)),
                              bounds=tuple(round(v, 3) for v in p.bounds), name_source=src, confidence=confidence if src == "label" else "low" if not name else confidence))
    return rooms
