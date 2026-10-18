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
_AREA = {"sqft": 1.0, "sft": 1.0, "sq.ft": 1.0, "sqm": SQFT_PER_SQM, "m2": SQFT_PER_SQM, "sq.m": SQFT_PER_SQM,
         "sqmt": SQFT_PER_SQM, "sq.mt": SQFT_PER_SQM, "sqmtr": SQFT_PER_SQM, "sqmtrs": SQFT_PER_SQM, "sqmeter": SQFT_PER_SQM, "sqmetre": SQFT_PER_SQM, "sq.mtr": SQFT_PER_SQM}
_LEN = {"rft": 1.0, "rm_ft": 1.0, "m": FT_PER_M, "rm": FT_PER_M, "mtr": FT_PER_M, "meter": FT_PER_M, "metre": FT_PER_M,
        "rmt": FT_PER_M, "rmtr": FT_PER_M, "mtrs": FT_PER_M, "meters": FT_PER_M, "metres": FT_PER_M, "mt": FT_PER_M, "rmtrs": FT_PER_M}
_COUNT = {"nos": 1.0, "no": 1.0, "each": 1.0, "ea": 1.0, "unit": 1.0, "units": 1.0, "set": 1.0, "sets": 1.0, "nos.": 1.0, "pcs": 1.0, "pc": 1.0}


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


_STOP = {"and", "or", "of", "the", "with", "for", "in", "to", "a", "an", "work", "works", "type", "board", "boards"}


def _tokens(text: str) -> List[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in _STOP:
            continue
        out.append(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


def _match(line: Dict[str, Any], recipes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    rid = line.get("recipe_id")
    if rid:
        return next((r for r in recipes if r["id"] == rid), None)
    desc = str(line.get("description", ""))
    text = _norm(desc)
    have = set(_tokens(desc))
    best, best_key = None, (0, 0)
    for r in recipes:
        for alias in [r.get("name", "")] + list(r.get("aliases", [])):
            a = _norm(alias)
            if not a:
                continue
            toks = _tokens(alias)
            # exact phrase, or every key word of the alias present (any order, "gypsum board false ceiling" = "gypsum false ceiling")
            if a in text or (toks and all(t in have for t in toks)):
                key = (len(toks), len(a))
                if key > best_key:
                    best, best_key = r, key
    return best


def _draft_error(exc: Exception) -> str:
    t = str(exc).lower()
    if "insufficient_quota" in t or "credit" in t or "billing" in t:
        return "AI drafting unavailable: no credit on the OpenAI account"
    if "401" in t or "invalid_api_key" in t or "incorrect api key" in t:
        return "AI drafting unavailable: the OpenAI key was rejected"
    if "429" in t or "rate" in t:
        return "AI drafting busy: rate limit, try again shortly"
    return "AI drafting failed; the line was not guessed"


def _is_equipment(unit: str) -> bool:
    return _unit_key(unit) in {*_COUNT, "lot", "lots", "ls", "lumpsum", "job"}


def _clean_draft(d: Dict[str, Any], desc: str, unit: str) -> Optional[Dict[str, Any]]:
    mats = []
    for m in d.get("materials", []):
        try:
            cons = float(m.get("consumption_per_unit", 0))
            waste = min(max(float(m.get("wastage_percent", 0)), 0.0), 30.0)
        except (TypeError, ValueError):
            continue
        if cons > 0 and m.get("name") and m.get("unit"):
            mats.append({"name": str(m["name"]), "unit": str(m["unit"]), "consumption_per_unit": cons, "wastage_percent": waste})
    if not mats:
        return None
    return {"id": "ai_" + re.sub(r"[^a-z0-9]+", "_", _norm(desc))[:40], "name": desc[:80],
            "base_unit": unit or str(d.get("base_unit") or "nos"), "materials": mats,
            "validated": False, "source": "ai_draft", "assumptions": list(d.get("assumptions", []))}


_TRADE_NAMES = {"hvac": "HVAC", "electrical": "Electrical", "plumbing": "Plumbing", "firefighting": "Fire fighting", "interiors": "Interiors / Finishing",
                "civil": "Civil", "bms": "BMS / Controls"}


def takeoff(lines: List[Dict[str, Any]], custom_recipes: Optional[List[Dict[str, Any]]] = None,
            draft_fn: Optional[Any] = None) -> Dict[str, Any]:
    """draft_fn(description, unit) -> recipe dict, used only for lines no stored recipe matches.

    Drafted recipes are always marked `source: ai_draft` and `validated: False`.
    """
    if not lines:
        raise ValueError("BOQ must contain at least one line")
    recipes = _recipes(custom_recipes)
    results, unmatched, totals, flat = [], [], {}, []
    used_unvalidated = set()
    drafted, draft_cache, procure = [], {}, []
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
        if recipe is None and _is_equipment(str(line.get("unit") or "")):
            procure.append({"item_no": item, "description": str(line.get("description", ""))[:160],
                            "unit": str(line.get("unit") or ""), "quantity": qty})
            continue
        if recipe is None and draft_fn is not None:
            desc, unit = str(line.get("description", "")), str(line.get("unit") or "")
            key = (_norm(desc), _unit_key(unit))
            try:
                if key not in draft_cache:
                    d = draft_fn(desc, unit)
                    draft_cache[key] = _clean_draft(d, desc, unit) if d else None
                recipe = draft_cache[key]
            except Exception as exc:  # provider down, bad JSON: report, do not invent
                unmatched.append({"item_no": item, "description": desc, "reason": _draft_error(exc)})
                continue
            if recipe is not None:
                drafted.append(item)
        if recipe is None:
            unmatched.append({"item_no": item, "description": line.get("description", ""), "reason": "no recipe matches this description"})
            continue
        base_qty = _convert(qty, str(line.get("unit") or recipe["base_unit"]), recipe["base_unit"])
        if base_qty is None and _is_equipment(str(line.get("unit") or "")):
            procure.append({"item_no": item, "description": str(line.get("description", ""))[:160],
                            "unit": str(line.get("unit") or ""), "quantity": qty})
            continue
        if base_qty is None:
            unmatched.append({"item_no": item, "description": line.get("description", ""),
                              "reason": f"cannot convert BOQ unit '{line.get('unit')}' to recipe unit '{recipe['base_unit']}'"})
            continue
        if recipe.get("validated") is False:
            used_unvalidated.add(recipe["name"])
        src = recipe.get("source", "catalogue")
        mats = []
        spec = str(line.get("spec") or line.get("description", ""))[:90]
        spec = re.sub(r"^[A-Za-z]{1,4}[\s-]*\d+(?:\.\d+)?\s*(?:\([A-Za-z]\)\s*)?", "", spec).strip() or spec
        group = _TRADE_NAMES.get((recipe.get("verticals") or ["general"])[0], "General")
        for mi, m in enumerate(recipe.get("materials", [])):
            mname = str(m["name"]).replace("{spec}", spec)
            cons, waste = float(m.get("consumption_per_unit", 0)), float(m.get("wastage_percent", 0))
            q = base_qty * cons * (1 + waste / 100.0)
            mats.append({"material_name": mname, "unit": m["unit"], "quantity": round(q, 3),
                         "basis": f"{base_qty:g} {recipe['base_unit']} x {cons:g} {m['unit']}/{recipe['base_unit']} + {waste:g}% wastage"})
            key = (mname.strip().lower(), m["unit"].strip().lower())
            cur = totals.setdefault(key, {"material_name": mname, "unit": m["unit"], "quantity": 0.0, "source_items": "",
                                          "trade": group, "type": "Main material" if mi == 0 else "Supporting material"})
            if mi == 0:
                cur["type"] = "Main material"
            cur["quantity"] = round(cur["quantity"] + q, 3)
            cur["source_items"] = (cur["source_items"] + ", " + item) if cur["source_items"] else item
        flat.extend({"item_no": item, "recipe_name": recipe["name"], **mm} for mm in mats)
        results.append({"item_no": item, "description": str(line.get("description", "")), "boq_quantity": qty,
                        "boq_unit": str(line.get("unit") or recipe["base_unit"]), "recipe_id": recipe["id"],
                        "recipe_name": recipe["name"], "recipe_source": src, "recipe_quantity": round(base_qty, 3), "recipe_unit": recipe["base_unit"],
                        "materials": mats})
    return {
        "line_count": len(lines), "matched_line_count": len(results), "unmatched_line_count": len(unmatched),
        "line_takeoff": [{k: v for k, v in r.items() if k != "materials"} for r in results], "line_materials": flat, "boq_breakdown": results, "material_totals": sorted(totals.values(), key=lambda r: (r["trade"], r["type"] != "Main material", r["material_name"].lower())),
        "unmatched_lines": unmatched, "unvalidated_recipes_used": sorted(used_unvalidated),
        **({"ai_drafted_items": drafted} if drafted else {}),
        "procure_as_specified_count": len(procure),
        "procure_as_specified": procure,
    }
