"""Read a priced Excel BOQ / tender schedule into takeoff lines, keeping the heading context.

Many tender BOQs put the item name in an unpriced row ("DUCT THERMAL & ACOUSTIC INSULATION") and
leave the priced sub-lines short ("NS-43.1 19 mm"). A row with a quantity and a unit becomes a line; the
unpriced rows directly above it (and above its priced siblings) are carried into its description.
Rows are never invented: if no header row with description and quantity columns is found, we say so.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Union

MAX_CONTEXT = 500
_STEM = re.compile(r"\b([A-Za-z]{1,4})[\s-]*(\d+)(?:\.\d+)?\b")


def _stem(text: str) -> str:
    m = _STEM.search(text or "")
    return (m.group(1) + m.group(2)).lower() if m else ""


def _clean(v: Any) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def _qty(v: Any):
    try:
        q = float(str(v).replace(",", "").strip())
    except ValueError:
        return None
    return q if q > 0 else None


def parse_boq_xlsx(source: Union[str, bytes, io.BytesIO]) -> List[Dict[str, Any]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(source) if isinstance(source, bytes) else source, data_only=True)
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        head = None
        for i, r in enumerate(rows[:40]):
            low = [_clean(c).lower() for c in r]
            d = next((j for j, c in enumerate(low) if "description" in c), None)
            q = next((j for j, c in enumerate(low) if c in ("qty", "quantity", "no.of qty", "no. of qty") or "qty" in c), None)
            u = next((j for j, c in enumerate(low) if c in ("unit", "units", "uom")), None)
            if d is not None and q is not None and u is not None:
                head = (i, 0, d, q, u)
                break
        if head is None:
            continue
        hi, _, dcol, qcol, ucol = head
        lines: List[Dict[str, Any]] = []
        ctx: List[str] = []
        last_was_line = False
        for r in rows[hi + 1:]:
            desc, unit, qty = _clean(r[dcol]), _clean(r[ucol]), _qty(r[qcol])
            item = re.sub(r"\.0+$", "", _clean(r[0]))
            if qty is None or not unit:
                if not desc:
                    continue
                if last_was_line:
                    ctx = []
                ctx.append(desc[:150])
                last_was_line = False
                continue
            # context directly above always applies; for later priced siblings it applies only when the
            # item codes agree (NS-43.1 belongs under NS-43.0), so an unrelated priced line is not polluted
            use_ctx = bool(ctx) and len(desc) <= 80 and (not last_was_line or (_stem(desc) and _stem(desc) == _stem(" ".join(ctx))))
            full = " | ".join(ctx[-3:])[:MAX_CONTEXT] + " | " + desc if use_ctx else desc
            lines.append({"item_no": item, "description": full, "spec": desc[:90], "unit": unit, "quantity": qty})
            last_was_line = True
        if lines:
            return lines
    raise ValueError("No BOQ table found: need a header row with Description, Qty and Unit columns")
