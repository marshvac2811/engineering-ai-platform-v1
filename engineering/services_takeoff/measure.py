"""Measure pipe / duct / conduit runs, count fittings and devices in a services DXF.

Everything reported is measured from the drawing's own geometry. Nothing is invented: runs with no size label are
reported as "unsized", and layers that are not recognised as a service are listed so a person can map them.
"""
from __future__ import annotations

import math
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

Pt = Tuple[float, float]

# (category, layer regex). First match wins. Device layers are listed separately.
CATEGORY_LAYERS: List[Tuple[str, re.Pattern]] = [
    ("fire_pipe", re.compile(r"(fire|f-pipe|f-main|f-riser|f-branch|sprink|hydrant|fhc|ff-|fpipe)", re.I)),
    ("hvac_duct", re.compile(r"(duct|m-duct|hvac-d|sad|rad|exh|supply-air|return-air|fresh-air)", re.I)),
    ("hvac_pipe", re.compile(r"(chw|chilled|cdw|cooling|refrig|m-pipe|condens|hvac-p|ac-drain|vrf)", re.I)),
    ("cable_tray", re.compile(r"(tray|trunking|e-tray)", re.I)),
    ("conduit", re.compile(r"(conduit|e-cond|e-wir|wiring|e-pow|e-light|elec|e-line|cable)", re.I)),
    ("plumbing_drain", re.compile(r"(drain|soil|waste|swr|sewer|sanit|vent|rain|storm)", re.I)),
    ("plumbing_supply", re.compile(r"(plumb|p-pipe|p-wat|water|dcw|dhw|domestic|cpvc|ppr|pipe|supply|p-cw|p-hw|cold|hot)", re.I)),
]
DEVICE_LAYERS: List[Tuple[str, re.Pattern]] = [
    ("sprinkler_head", re.compile(r"(spkl|sprinkler|f-head)", re.I)),
    ("diffuser", re.compile(r"(diff|grille|m-air|m-terminal)", re.I)),
    ("light_point", re.compile(r"(e-lite|e-light|light-fix|lighting-fix|e-lgt)", re.I)),
    ("pipe_riser", re.compile(r"(p-riser|riser)", re.I)),
]
DEVICE_BLOCKS: List[Tuple[str, re.Pattern]] = [
    ("water_closet", re.compile(r"(wc|water.?closet|ewc|iwc|commode)", re.I)),
    ("wash_basin", re.compile(r"(wash.?basin|wb\b|lavatory|lav\b|basin)", re.I)),
    ("urinal", re.compile(r"urinal", re.I)),
    ("sink", re.compile(r"(sink|pantry)", re.I)),
    ("shower", re.compile(r"shower", re.I)),
    ("floor_drain", re.compile(r"(floor.?drain|fd\b|gully|trap)", re.I)),
    ("tap", re.compile(r"(tap|bib.?cock|faucet|cp.?fitting)", re.I)),
    ("sprinkler_head", re.compile(r"(sprinkler|spkl)", re.I)),
    ("smoke_detector", re.compile(r"(smoke|detector|heat.?det)", re.I)),
    ("diffuser", re.compile(r"(diffuser|grille|louver|louvre)", re.I)),
    ("fire_damper", re.compile(r"(damper|vcd|fd-)", re.I)),
    ("switch", re.compile(r"(switch|sw\b)", re.I)),
    ("socket", re.compile(r"(socket|outlet|plug)", re.I)),
    ("light_point", re.compile(r"(light|lamp|luminaire|downlight|panel.?light)", re.I)),
    ("distribution_board", re.compile(r"(\bdb\b|distribution|panel|mdb|smdb)", re.I)),
    ("fan_point", re.compile(r"(fan)", re.I)),
]
_UNITS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "in": 0.0254, "ft": 0.3048}
_INCH_TO_DN = {0.5: 15, 0.75: 20, 1: 25, 1.25: 32, 1.5: 40, 2: 50, 2.5: 65, 3: 80, 4: 100, 5: 125, 6: 150, 8: 200}
SNAP = 0.02            # metres: endpoints closer than this are the same node
LABEL_RADIUS = 1.0     # metres: a size label this close to a run labels that run
_FAMILY = {"m": {"hvac_duct", "hvac_pipe"}, "h": {"hvac_duct", "hvac_pipe"}, "f": {"fire_pipe"}, "p": {"plumbing_supply", "plumbing_drain"}, "e": {"conduit", "cable_tray"}}


def _label_allowed(label_layer: str, category: str) -> bool:
    """A label on a layer such as M-TAG only labels HVAC runs, F-TAG fire runs, and so on; other layers label anything."""
    lc = _classify(label_layer)
    if lc is not None:
        return lc == category
    mt = re.match(r"^([a-z])[-_]", str(label_layer).strip(), re.I)
    if mt and mt.group(1).lower() in _FAMILY:
        return category in _FAMILY[mt.group(1).lower()]
    return True


def _dist_point_segment(p: Pt, a: Pt, b: Pt) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def parse_size(text: str) -> Optional[str]:
    """'DN50', '50 mm dia', '2" CPVC', '300x200', '450 dia' -> '50', '50', '50', '300x200', '450'. None if no size."""
    t = str(text or "")
    m = re.search(r"(\d{2,4})\s*[xX*×]\s*(\d{2,4})", t)
    if m:
        return f"{int(m.group(1))}x{int(m.group(2))}"
    m = re.search(r"DN\s*(\d{2,4})", t, re.I)
    if m:
        return str(int(m.group(1)))
    m = re.search(r"(\d{2,4})\s*(?:mm)?\s*(?:dia\b|nb\b|ø|φ|⌀)", t, re.I)
    if m:
        return str(int(m.group(1)))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:\"|”|inch|in\b)", t, re.I)
    if m and float(m.group(1)) in _INCH_TO_DN:
        return str(_INCH_TO_DN[float(m.group(1))])
    m = re.search(r"(?<![\d.])(\d{2,3})\s*mm\b", t, re.I)
    if m:
        return str(int(m.group(1)))
    return None


def size_width_mm(size: str) -> Optional[Tuple[float, float]]:
    """('300x200') -> (300, 200) rectangular; ('450') -> (450, 0) round."""
    if not size or size == "unsized":
        return None
    if "x" in size:
        a, b = size.split("x")
        return float(a), float(b)
    return float(size), 0.0


@dataclass
class Run:
    a: Pt
    b: Pt
    layer: str
    category: str
    size: str = "unsized"
    arc: bool = False

    @property
    def length(self) -> float:
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])


@dataclass
class Measurement:
    source_file: str
    units_note: str
    lengths: Dict[Tuple[str, str], float] = field(default_factory=dict)          # (category, size) -> metres
    fittings: Dict[Tuple[str, str, str], int] = field(default_factory=dict)      # (category, size, fitting) -> count
    devices: Dict[str, int] = field(default_factory=dict)
    layers_used: Dict[str, str] = field(default_factory=dict)                    # layer -> category
    layers_ignored: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    device_points: Dict[str, List[Pt]] = field(default_factory=dict)             # device -> positions in metres
    autosized_m: float = 0.0                                                      # duct length sized from diffuser airflow

    def repeated(self, n: float) -> "Measurement":
        """Scale the measurement for n identical floors / typical blocks drawn once."""
        self.lengths = {k: v * n for k, v in self.lengths.items()}
        self.fittings = {k: int(round(v * n)) for k, v in self.fittings.items()}
        self.devices = {k: int(round(v * n)) for k, v in self.devices.items()}
        return self

    def categories(self) -> List[str]:
        return sorted({c for c, _s in self.lengths})

    def length(self, category: str, size: Optional[str] = None) -> float:
        return sum(v for (c, s), v in self.lengths.items() if c == category and (size is None or s == size))

    def fitting_counts(self, category: str, size: Optional[str] = None) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for (c, s, f), n in self.fittings.items():
            if c == category and (size is None or s == size):
                out[f] = out.get(f, 0) + n
        return out

    def sizes(self, category: str) -> List[str]:
        return sorted({s for (c, s) in self.lengths if c == category})

    def rows(self) -> List[Dict[str, Any]]:
        rows = []
        for (c, s), L in sorted(self.lengths.items()):
            f = {k[2]: n for k, n in self.fittings.items() if k[0] == c and k[1] == s}
            rows.append({"service": c.replace("_", " "), "size_mm": s, "length_m": round(L, 2), "elbows_90": f.get("elbow_90", 0), "elbows_45": f.get("elbow_45", 0),
                         "tees": f.get("tee", 0), "crosses": f.get("cross", 0), "reducers": f.get("reducer", 0), "end_points": f.get("end", 0)})
        return rows


def _classify(layer: str) -> Optional[str]:
    for cat, rx in CATEGORY_LAYERS:
        if rx.search(layer):
            return cat
    return None


def _device_layer(layer: str) -> Optional[str]:
    for cat, rx in DEVICE_LAYERS:
        if rx.search(layer):
            return cat
    return None


def measure_dxf(filename: str, data: bytes, *, units: Optional[str] = None, duct_cmh_per_diffuser: Optional[float] = None) -> Measurement:
    import ezdxf
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as fh:
        fh.write(data)
        path = fh.name
    try:
        doc = ezdxf.readfile(path)
    finally:
        os.unlink(path)
    msp = doc.modelspace()
    from engineering.plan.readers import _units_factor
    # raw collection (drawing units)
    raw_runs: List[Tuple[Pt, Pt, str, bool]] = []
    labels: List[Tuple[str, Pt, str]] = []
    inserts: List[Tuple[str, str, Pt]] = []
    dev_circles: Dict[str, int] = {}
    dev_circle_pts: Dict[str, List[Pt]] = {}
    xs: List[float] = []
    ys: List[float] = []
    ignored: Dict[str, int] = {}
    skipped_splines = 0

    for e in msp:
        t = e.dxftype()
        layer = str(getattr(e.dxf, "layer", "0"))
        if t == "LINE":
            a, b = (e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)
            raw_runs.append((a, b, layer, False)); xs += [a[0], b[0]]; ys += [a[1], b[1]]
        elif t in ("LWPOLYLINE", "POLYLINE"):
            pts = [(p[0], p[1]) for p in e.get_points("xy")] if t == "LWPOLYLINE" else [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            closed = bool(getattr(e, "is_closed", False) or getattr(e, "closed", False))
            ring = pts + ([pts[0]] if closed and pts else [])
            for a, b in zip(ring, ring[1:]):
                raw_runs.append((a, b, layer, False)); xs += [a[0], b[0]]; ys += [a[1], b[1]]
        elif t == "ARC":
            n = 8
            sa, ea = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
            if ea < sa:
                ea += 2 * math.pi
            c, r = e.dxf.center, e.dxf.radius
            pts = [(c.x + r * math.cos(sa + (ea - sa) * i / n), c.y + r * math.sin(sa + (ea - sa) * i / n)) for i in range(n + 1)]
            for a, b in zip(pts, pts[1:]):
                raw_runs.append((a, b, layer, True)); xs += [a[0], b[0]]; ys += [a[1], b[1]]
        elif t == "CIRCLE":
            dl = _device_layer(layer)
            if dl:
                dev_circles[dl] = dev_circles.get(dl, 0) + 1
                dev_circle_pts.setdefault(dl, []).append((e.dxf.center.x, e.dxf.center.y))
        elif t in ("TEXT", "MTEXT"):
            txt = e.dxf.text if t == "TEXT" else re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", e.text).replace("\\P", " ")
            labels.append((str(txt), (e.dxf.insert.x, e.dxf.insert.y), layer))
        elif t == "INSERT":
            inserts.append((str(e.dxf.name), layer, (e.dxf.insert.x, e.dxf.insert.y)))
        elif t == "SPLINE":
            skipped_splines += 1

    extent = max((max(xs) - min(xs)) if xs else 0, (max(ys) - min(ys)) if ys else 0)
    factor, unit_note, warns = _units_factor(doc, units, extent)
    m = Measurement(source_file=filename, units_note=unit_note, warnings=list(warns))
    alltext = " ".join(t for t, _p, _l in labels).lower()
    if re.search(r"(not to scale|schematic|concept)", alltext):
        m.warnings.append("The drawing says it is schematic / not to scale or a concept. Lengths measured from it are indicative only and must not be used as site quantities until measured from a scaled, coordinated drawing.")
    if skipped_splines:
        m.warnings.append(f"{skipped_splines} spline(s) were not measured; redraw them as polylines or arcs if they are pipes or ducts.")

    runs: List[Run] = []
    for a, b, layer, arc in raw_runs:
        cat = _classify(layer)
        if cat is None:
            ignored[layer] = ignored.get(layer, 0) + 1
            continue
        A, B = (a[0] * factor, a[1] * factor), (b[0] * factor, b[1] * factor)
        if math.hypot(B[0] - A[0], B[1] - A[1]) < 1e-6:
            continue
        r = Run(A, B, layer, cat, arc=arc)
        s = parse_size(layer)
        if s:
            r.size = s
        runs.append(r)
        m.layers_used[layer] = cat
    m.layers_ignored = sorted(l for l in ignored if not re.search(r"(wall|a-|g-|dim|text|anno|hatch|tag|note|title|room|sched|defpoints|grid|door|window|furn|tile|^0$)", l, re.I))

    # --- devices
    for name, layer, ip in inserts:
        for kind, rx in DEVICE_BLOCKS:
            if rx.search(name):
                m.devices[kind] = m.devices.get(kind, 0) + 1
                m.device_points.setdefault(kind, []).append((ip[0] * factor, ip[1] * factor))
                break
    for kind, n in dev_circles.items():
        m.devices[kind] = m.devices.get(kind, 0) + n
        m.device_points.setdefault(kind, []).extend((x * factor, y * factor) for x, y in dev_circle_pts.get(kind, []))

    if not runs:
        m.warnings.append("No pipe, duct or conduit lines were found on recognisable service layers (looked for names such as PLUMB, PIPE, DUCT, CONDUIT, FIRE, TRAY).")
        return m

    # --- size labels: nearest parsable label within LABEL_RADIUS of the run's midpoint
    lab = [(parse_size(t), (p[0] * factor, p[1] * factor), l) for t, p, l in labels]
    lab = [(s, p, l) for s, p, l in lab if s]
    # each label belongs to the single nearest run it is allowed to label (within LABEL_RADIUS)
    for sz, p, l in lab:
        best, bd = None, LABEL_RADIUS
        for r in runs:
            if not _label_allowed(l, r.category):
                continue
            d = _dist_point_segment(p, r.a, r.b)
            if d < bd:
                best, bd = r, d
        if best is not None and best.size == "unsized":     # a label closest to an already-labelled run belongs to that run
            best.size = sz

    by_cat: Dict[str, List[Run]] = {}
    for r in runs:
        by_cat.setdefault(r.category, []).append(r)
    for cat, rs in by_cat.items():
        _topology(cat, rs, m, LineString, Point, STRtree, duct_cmh_per_diffuser if cat == "hvac_duct" else None)
    unsized = sum(v for (c, s), v in m.lengths.items() if s == "unsized")
    if unsized > 0:
        m.warnings.append(f"{unsized:.1f} m of run has no size label or size in its layer name, so it is listed as 'unsized'. Label the sizes (for example DN50 or 300x200) to get size-wise quantities.")
    return m


def _topology(cat: str, runs: List[Run], m: Measurement, LineString, Point, STRtree, cmh_per_diffuser: Optional[float] = None) -> None:
    # 1. split runs where another run's endpoint touches them mid-way (T-junctions drawn as separate lines)
    lines = [LineString([r.a, r.b]) for r in runs]
    tree = STRtree(lines)
    splits: Dict[int, List[Pt]] = {}
    for i, r in enumerate(runs):
        for p in (r.a, r.b):
            for j in tree.query(Point(p).buffer(SNAP)):
                j = int(j)
                if j == i:
                    continue
                ln = lines[j]
                if ln.distance(Point(p)) <= SNAP:
                    da, db = math.hypot(p[0] - runs[j].a[0], p[1] - runs[j].a[1]), math.hypot(p[0] - runs[j].b[0], p[1] - runs[j].b[1])
                    if da > SNAP and db > SNAP:
                        splits.setdefault(j, []).append(p)
    segs: List[Run] = []
    for i, r in enumerate(runs):
        pts = [r.a] + sorted(set(splits.get(i, [])), key=lambda p: math.hypot(p[0] - r.a[0], p[1] - r.a[1])) + [r.b]
        for a, b in zip(pts, pts[1:]):
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
                segs.append(Run(a, b, r.layer, r.category, r.size, r.arc))
    # 2. snap endpoints to nodes
    nodes: List[Pt] = []
    grid: Dict[Tuple[int, int], List[int]] = {}

    def node_of(p: Pt) -> int:
        cx, cy = int(p[0] // SNAP), int(p[1] // SNAP)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((cx + dx, cy + dy), []):
                    if math.hypot(nodes[k][0] - p[0], nodes[k][1] - p[1]) <= SNAP:
                        return k
        nodes.append(p)
        grid.setdefault((cx, cy), []).append(len(nodes) - 1)
        return len(nodes) - 1

    inc: Dict[int, List[Tuple[Pt, Run]]] = {}
    ends: List[Tuple[int, int]] = []
    for s in segs:
        ia, ib = node_of(s.a), node_of(s.b)
        ends.append((ia, ib))
        if ia == ib:
            continue
        inc.setdefault(ia, []).append((nodes[ib], s))
        inc.setdefault(ib, []).append((nodes[ia], s))
    # 3. propagate sizes into unsized runs, but only along a continuing line (two runs meeting at a bend or straight joint).
    #    A branch off a tee is never given the main's size: it stays "unsized" until it is labelled.
    def _straight(p0: Pt, o1: Pt, o2: Pt) -> bool:
        v1, v2 = (o1[0] - p0[0], o1[1] - p0[1]), (o2[0] - p0[0], o2[1] - p0[1])
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 == 0 or n2 == 0:
            return False
        c = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
        return c <= -0.966     # within about 15 degrees of a straight continuation

    for _ in range(50):
        changed = False
        for k, lst in inc.items():
            pairs = []
            if len(lst) == 2:
                pairs.append((lst[0][1], lst[1][1]))       # one pipe turning a corner
            elif len(lst) >= 3:
                for i in range(len(lst)):
                    for j in range(i + 1, len(lst)):
                        if _straight(nodes[k], lst[i][0], lst[j][0]):
                            pairs.append((lst[i][1], lst[j][1]))
            for s1, s2 in pairs:
                if s1.size == "unsized" and s2.size != "unsized":
                    s1.size = s2.size
                    changed = True
                elif s2.size == "unsized" and s1.size != "unsized":
                    s2.size = s1.size
                    changed = True
        if not changed:
            break
    if cmh_per_diffuser and cat == "hvac_duct":
        from engineering.services_takeoff.autosize import autosize_unsized_ducts
        autosize_unsized_ducts(segs, m, float(cmh_per_diffuser))
    # 4. lengths
    for s in segs:
        key = (cat, s.size)
        m.lengths[key] = m.lengths.get(key, 0.0) + s.length
    # 5. fittings at nodes
    def area_key(sz: str) -> float:
        w = size_width_mm(sz)
        return 0.0 if w is None else (w[0] * (w[1] or w[0]))
    for k, lst in inc.items():
        p = nodes[k]
        sizes = [s.size for _o, s in lst]
        big = max(sizes, key=area_key)
        deg = len(lst)
        fit = None
        if deg == 1:
            fit = "end"
        elif deg == 2:
            v = [(o[0] - p[0], o[1] - p[1]) for o, _s in lst]
            n0, n1 = math.hypot(*v[0]), math.hypot(*v[1])
            cosang = max(-1.0, min(1.0, (v[0][0] * v[1][0] + v[0][1] * v[1][1]) / (n0 * n1)))
            deviation = 180.0 - math.degrees(math.acos(cosang))
            if deviation >= 67:
                fit = "elbow_90"
            elif deviation >= 15:
                fit = "elbow_45"
            elif sizes[0] != sizes[1] and "unsized" not in sizes:
                fit = "reducer"
        elif deg == 3:
            fit = "tee"
        else:
            fit = "cross"
        if fit:
            key = (cat, big, fit)
            m.fittings[key] = m.fittings.get(key, 0) + 1
