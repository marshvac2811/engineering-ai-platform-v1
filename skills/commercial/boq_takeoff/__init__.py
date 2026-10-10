"""BOQ takeoff (SiteTrack-style): for each itemised BOQ line, work out the materials needed.

Deterministic: description -> recipe match (alias text or explicit recipe_id), unit conversion,
quantity x consumption x (1 + wastage). Recipes are data (scope_engine/catalog.yaml, or supplied per
request in `recipes`); recipes marked `validated: false` are flagged because their consumption and
wastage factors are defaults that the company must confirm. Unmatched lines are reported, never guessed.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional

from scope_engine.analyzer import _catalog, _norm

SQFT_PER_SQM = 10.7639104
FT_PER_M = 3.280839895
_AREA = {"sqft": 1.0, "sft": 1.0, "sq.ft": 1.0, "sqm": SQFT_PER_SQM, "m2": SQFT_PER_SQM, "sq.m": SQFT_PER_SQM}
_LEN = {"rft": 1.0, "rm_ft": 1.0, "m": FT_PER_M, "rm": FT_PER_M, "mtr": FT_PER_M, "meter": FT_PER_M, "metre": FT_PER_M}
_COUNT = {"nos": 1.0, "no": 1.0, "each": 1.0, "ea": 1.0, "unit": 1.0, "units": 1.0, "set": 1.0, "sets": 1.0}


def _unit_key(u: str) -> str:
    return re.sub(r"\s+", "", _norm(u)).replace("²", "2")


def _convert(qty: float, from_unit: str, to_unit: str) -> Optional[float]:
    f, t = _unit_key(from_unit), _unit_key(to_unit)
    if f == t:
        return qty
    for table in (_AREA, _LEN, _COUNT):
        if f in table and t in table:
            return qty * table[f] / table[t]
    return None


def parse_boq_csv(text: str) -> List[Dict[str, Any]]:
    """Header row required; accepts item_no/item, description, unit, quantity/qty columns."""
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    out = []
    for n, row in enumerate(rows, 1):
        low = {str(k).strip().lower(): v for k, v in row.items() if k}
        out.append({"item_no": low.get("item_no") or low.get("item") or low.get("sr no") or str(n),
                    "description": low.get("description") or low.get("desc") or "",
                    "unit": low.get("unit") or low.get("uom") or "",
                    "quantity": low.get("quantity") or low.get("qty") or ""})
    return out


def parse_recipes_csv(text: str) -> List[Dict[str, Any]]:
    """SiteTrack work library export: one row per material.

    Columns: work_type, work_unit, material_name, unit, consumption_per_unit, wastage_percent
    (see HANDOFF for the Supabase query that produces it). Recipes built this way are company-validated.
    """
    recipes: Dict[str, Dict[str, Any]] = {}
    for n, row in enumerate(csv.DictReader(io.StringIO(text.strip())), 2):
        low = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k}
        name, unit = low.get("work_type") or low.get("name"), low.get("work_unit") or low.get("base_unit")
        if not name or not unit or not low.get("material_name"):
            raise ValueError(f"Recipe CSV row {n}: work_type, work_unit and material_name are required")
        try:
            cons = float(low.get("consumption_per_unit") or 0)
            waste = float(low.get("wastage_percent") or 0)
        except ValueError:
            raise ValueError(f"Recipe CSV row {n}: consumption_per_unit and wastage_percent must be numeric")
        rid = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        rec = recipes.setdefault(rid, {"id": rid, "name": name, "base_unit": unit, "aliases": [], "materials": []})
        rec["materials"].append({"name": low["material_name"], "unit": low.get("unit") or "nos",
                                 "consumption_per_unit": cons, "wastage_percent": waste})
    return list(recipes.values())


def _recipes(custom: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    base = list(_catalog().get("recipes", []))
    ids = {r["id"] for r in (custom or [])}
    return [r for r in base if r["id"] not in ids] + list(custom or [])


def _match(line: Dict[str, Any], recipes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    rid = line.get("recipe_id")
    if rid:
        return next((r for r in recipes if r["id"] == rid), None)
    text = _norm(str(line.get("description", "")))
    best, best_len = None, 0
    for r in recipes:
        for alias in [r.get("name", "")] + list(r.get("aliases", [])):
            a = _norm(alias)
            if a and a in text and len(a) > best_len:
                best, best_len = r, len(a)
    return best


def takeoff(lines: List[Dict[str, Any]], custom_recipes: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if not lines:
        raise ValueError("BOQ must contain at least one line")
    recipes = _recipes(custom_recipes)
    results, unmatched, totals, flat = [], [], {}, []
    used_unvalidated = set()
    for n, line in enumerate(lines, 1):
        item = str(line.get("item_no") or n)
        try:
            qty = float(str(line.get("quantity", "")).replace(",", ""))
        except ValueError:
            unmatched.append({"item_no": item, "description": line.get("description", ""), "reason": "quantity is not a number"})
            continue
        if qty <= 0:
            unmatched.append({"item_no": item, "description": line.get("description", ""), "reason": "quantity must be greater than zero"})
            continue
        recipe = _match(line, recipes)
        if recipe is None:
            unmatched.append({"item_no": item, "description": line.get("description", ""), "reason": "no recipe matches this description"})
            continue
        base_qty = _convert(qty, str(line.get("unit") or recipe["base_unit"]), recipe["base_unit"])
        if base_qty is None:
            unmatched.append({"item_no": item, "description": line.get("description", ""),
                              "reason": f"cannot convert BOQ unit '{line.get('unit')}' to recipe unit '{recipe['base_unit']}'"})
            continue
        if recipe.get("validated") is False:
            used_unvalidated.add(recipe["name"])
        mats = []
        for m in recipe.get("materials", []):
            cons, waste = float(m.get("consumption_per_unit", 0)), float(m.get("wastage_percent", 0))
            q = base_qty * cons * (1 + waste / 100.0)
            mats.append({"material_name": m["name"], "unit": m["unit"], "quantity": round(q, 3),
                         "basis": f"{base_qty:g} {recipe['base_unit']} x {cons:g} {m['unit']}/{recipe['base_unit']} + {waste:g}% wastage"})
            key = (m["name"].strip().lower(), m["unit"].strip().lower())
            cur = totals.setdefault(key, {"material_name": m["name"], "unit": m["unit"], "quantity": 0.0, "source_items": ""})
            cur["quantity"] = round(cur["quantity"] + q, 3)
            cur["source_items"] = (cur["source_items"] + ", " + item) if cur["source_items"] else item
        flat.extend({"item_no": item, "recipe_name": recipe["name"], **mm} for mm in mats)
        results.append({"item_no": item, "description": str(line.get("description", "")), "boq_quantity": qty,
                        "boq_unit": str(line.get("unit") or recipe["base_unit"]), "recipe_id": recipe["id"],
                        "recipe_name": recipe["name"], "recipe_quantity": round(base_qty, 3), "recipe_unit": recipe["base_unit"],
                        "materials": mats})
    return {
        "line_count": len(lines), "matched_line_count": len(results), "unmatched_line_count": len(unmatched),
        "line_takeoff": [{k: v for k, v in r.items() if k != "materials"} for r in results], "line_materials": flat, "material_totals": sorted(totals.values(), key=lambda r: r["material_name"].lower()),
        "unmatched_lines": unmatched, "unvalidated_recipes_used": sorted(used_unvalidated),
    }
