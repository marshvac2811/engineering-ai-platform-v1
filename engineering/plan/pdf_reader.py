"""Vector PDF plan reader (CAD-exported PDFs). Scale comes from the drawing text or the caller; it is never guessed."""
from __future__ import annotations

import io
import re
from typing import List, Optional, Tuple

from engineering.plan.geometry import assign_labels, rooms_from_walls, to_plan_rooms
from engineering.plan.model import PlanModel, PlanReadResult

PT_TO_MM = 25.4 / 72.0
MAX_SEGMENTS = 150000
_SCALE_RE = re.compile(r"(?:scale\s*[:=-]?\s*)?\b1\s*[:/]\s*(\d{1,4})\b", re.I)


def _find_scale(words: List[str]) -> Optional[int]:
    text = " ".join(words)
    cands = [int(m.group(1)) for m in _SCALE_RE.finditer(text) if 5 <= int(m.group(1)) <= 2000]
    if not cands:
        return None
    # the most frequent plausible scale in the sheet text
    return max(set(cands), key=cands.count)


def read_pdf_plan(filename: str, data: bytes, *, scale: Optional[float]) -> PlanReadResult:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if not pdf.pages:
            return PlanReadResult("failed", None, ["The PDF has no pages."])
        best = None
        for page in pdf.pages[:10]:
            n = len(page.lines) + len(page.rects) + len(page.curves)
            if best is None or n > best[0]:
                best = (n, page)
        count, page = best
        words = page.extract_words() or []
        if count < 20:
            return PlanReadResult("unsupported", None, [
                "This PDF has almost no vector line work, so it is probably a scan or a photo of a drawing.",
                "Scanned drawings need an image-reading service that is not enabled yet. Please send a PDF exported directly from CAD, or the DXF."])
        height = float(page.height)
        segs_pt: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

        def add(a, b):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) > 1.5:      # drop specks shorter than ~0.5 mm
                segs_pt.append(((a[0], height - a[1]), (b[0], height - b[1])))

        for ln in page.lines:
            pts = ln.get("pts") or [(ln["x0"], ln["top"]), (ln["x1"], ln["bottom"])]
            for a, b in zip(pts, pts[1:]):
                add(a, b)
        for r in page.rects:
            x0, x1, t, b = r["x0"], r["x1"], r["top"], r["bottom"]
            for a, c in (((x0, t), (x1, t)), ((x1, t), (x1, b)), ((x1, b), (x0, b)), ((x0, b), (x0, t))):
                add(a, c)
        for cv in page.curves:
            pts = cv.get("pts") or []
            for a, b in zip(pts, pts[1:]):
                add(a, b)
        texts = [(w["text"], ((w["x0"] + w["x1"]) / 2, height - (w["top"] + w["bottom"]) / 2)) for w in words]
        found = _find_scale([w["text"] for w in words])
    warns: List[str] = []
    use_scale = float(scale) if scale else (float(found) if found else None)
    if use_scale is None:
        return PlanReadResult("needs_scale", None, [
            "I could not find a drawing scale (like 1:100) on this PDF. Please tell me the scale, or one known dimension, and I will read it again.",
            "I will not guess a scale because every area and size would be wrong."])
    if not scale and found:
        warns.append(f"Scale 1:{int(found)} was read from the drawing text. Please confirm it.")
    if len(segs_pt) > MAX_SEGMENTS:
        return PlanReadResult("failed", None, ["The PDF has too much line detail to read reliably; export just the plan layers to DXF or PDF."])
    k = PT_TO_MM * use_scale / 1000.0      # PDF point -> metres at drawing scale

    def m(p):
        return (p[0] * k, p[1] * k)

    walls = [(m(a), m(b)) for a, b in segs_pt]
    polys = rooms_from_walls(walls)
    if not polys:
        return PlanReadResult("failed", None, ["No closed rooms could be found in the PDF line work."])
    names = assign_labels(polys, [(t, m(p)) for t, p in texts])
    model = PlanModel(source_file=filename, file_type="pdf (vector)", walls=walls, units_note=f"metres, from PDF points at 1:{int(use_scale)}",
                      scale_note=f"1:{int(use_scale)}" + (" (stated by user)" if scale else " (read from drawing)"),
                      method="rooms detected from vector line work (door gaps up to ~1.1 m bridged)")
    model.rooms = to_plan_rooms(polys, names, confidence="medium")
    model.warnings = warns + ["Rooms were detected from line work, not from drawn room outlines. Please check the count and areas."]
    bx = [p[0] for r in model.rooms for p in r.polygon]
    by = [p[1] for r in model.rooms for p in r.polygon]
    model.bounds = (min(bx), min(by), max(bx), max(by))
    return PlanReadResult("partial", model, list(model.warnings))
