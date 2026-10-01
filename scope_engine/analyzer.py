"""Generic scope decomposition and recipe-driven quantity takeoff.

The core deliberately separates interpretation from calculation:
- vertical/recipe matching is configuration-driven;
- unit normalization is deterministic;
- material quantities are deterministic recipe multiplication;
- unsupported work is reported instead of invented.
A future LLM provider can supply richer decomposition without changing this contract.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.yaml"


def _catalog() -> dict:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}


def _norm(text: str) -> str:
    text = (text or "").lower().replace("³", "3").replace("²", "2")
    return re.sub(r"\s+", " ", text).strip()


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def _quantity_for_recipe(text: str, recipe: dict) -> float | None:
    for pattern in recipe.get("quantity_patterns", []):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return _number(m.group(1))
    return None


def _match_score(text: str, aliases: list[str]) -> int:
    return sum(1 for alias in aliases if alias in text)


def analyze_scope(text: str) -> Dict[str, Any]:
    t = _norm(text)
    catalog = _catalog()
    verticals: List[Dict[str, Any]] = []
    for v in catalog.get("verticals", []):
        score = _match_score(t, [_norm(x) for x in v.get("keywords", [])])
        if score:
            verticals.append({"id": v["id"], "name": v["name"], "score": score, "capabilities": list(v.get("capabilities", []))})
    verticals.sort(key=lambda x: (-x["score"], x["id"]))

    work_items: List[Dict[str, Any]] = []
    materials: List[Dict[str, Any]] = []
    unsupported: List[str] = []
    matched_recipe_ids: set[str] = set()

    for recipe in catalog.get("recipes", []):
        aliases = [_norm(recipe.get("name", ""))] + [_norm(x) for x in recipe.get("aliases", [])]
        if not any(a and a in t for a in aliases):
            continue
        qty = _quantity_for_recipe(t, recipe)
        if qty is None:
            unsupported.append(f"{recipe['name']}: quantity in {recipe.get('base_unit', 'the recipe base unit')} is required")
            continue
        matched_recipe_ids.add(recipe["id"])
        item = {"recipe_id": recipe["id"], "work_description": recipe["name"], "base_unit": recipe.get("base_unit"), "quantity": qty, "basis": f"Extracted {qty:g} {recipe.get('base_unit', '')} from client request."}
        work_items.append(item)
        for material in recipe.get("materials", []):
            base = qty * float(material.get("consumption_per_unit", 0))
            wastage = base * float(material.get("wastage_percent", 0)) / 100.0
            materials.append({
                "material_name": material["name"],
                "unit": material["unit"],
                "quantity": round(base + wastage, 3),
                "basis": f"{qty:g} {recipe.get('base_unit', '')} × {material.get('consumption_per_unit', 0)} {material['unit']}/{recipe.get('base_unit', '')} + {material.get('wastage_percent', 0)}% wastage",
                "source_work_item": recipe["name"],
            })

    # Consolidate only identical material/unit pairs; keep traceable basis lines.
    consolidated: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in materials:
        key = (row["material_name"].strip().lower(), row["unit"].strip().lower())
        if key not in consolidated:
            consolidated[key] = dict(row)
        else:
            consolidated[key]["quantity"] = round(float(consolidated[key]["quantity"]) + float(row["quantity"]), 3)
            consolidated[key]["basis"] += f"; {row['basis']}"
    materials = list(consolidated.values())

    if not verticals:
        unsupported.append("The platform could not confidently identify the business/engineering vertical from this request.")

    return {
        "verticals": verticals,
        "work_items": work_items,
        "material_boq": materials,
        "unsupported_scope": unsupported,
        "recipe_count": len(matched_recipe_ids),
        "capabilities": sorted({cap for v in verticals for cap in v.get("capabilities", [])}),
        "status": "ready_for_quantity_takeoff" if work_items else ("vertical_identified" if verticals else "needs_clarification"),
    }
