"""Floors and rooms from text, and (optionally) from a plan or sketch image read by an AI vision model.

Text format, one block per floor type:
    Floor: Typical floor x5
    Reception | 60 sqm | 10 people
Image reading is a DRAFT only: every room it returns is flagged unconfirmed and an engineer must check it.
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Dict, List

from engineering.building.schedule import extract_room_schedule

_FLOOR = re.compile(r"(?im)^\s*(?:floor|level)\s*[:\-]\s*(.+?)\s*(?:[x×]\s*(\d{1,3}))?\s*$")


def floors_from_text(text: str, floor_count: int | None = None) -> List[Dict[str, Any]]:
    text = text or ""
    marks = list(_FLOOR.finditer(text))
    blocks = []
    if marks:
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            blocks.append((m.group(1).strip(), int(m.group(2) or 1), text[m.end():end]))
    else:
        blocks.append(("Typical floor", int(floor_count or 1), text))
    floors = []
    for name, count, body in blocks:
        rooms = extract_room_schedule(body)["rooms"]
        if rooms:
            floors.append({"name": name, "count": count, "rooms": [
                {"room_id": f"R{n}", "name": r["name"], "area_m2": r["area_m2"], **({"occupancy": r["occupancy"]} if r.get("occupancy") is not None else {})}
                for n, r in enumerate(rooms, 1)]})
    return floors


PROMPT = """You are reading a client's architectural floor plan or hand sketch for an MEP estimate.
Return JSON only: {"floors": [{"name": str, "count": int, "rooms": [{"name": str, "area_m2": number, "occupancy": number|null,
"area_source": "dimensions"|"scale"|"estimated"}]}], "floor_height_m": number|null, "issues": [str]}.
Rules: use printed dimensions or the drawn scale to compute each room area. If you can only estimate an area, set area_source to "estimated" and
say so in issues. Do not invent rooms that are not drawn. If several floors are identical, give one floor with count. Put anything unclear in issues."""


class PlanReadError(RuntimeError):
    pass


def read_plan_image(data: bytes, mime: str = "image/png", *, client: Any = None, model: str | None = None) -> Dict[str, Any]:
    if client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise PlanReadError("Reading a plan image needs the AI vision service (OPENAI_API_KEY with credit). Send the room list as text instead.")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise PlanReadError("The openai package is not installed") from exc
        client = OpenAI(api_key=key)
    url = f"data:{mime};base64," + base64.b64encode(data).decode()
    try:
        resp = client.responses.create(model=model or os.getenv("ENGINEERING_AI_VISION_MODEL") or os.getenv("ENGINEERING_AI_MODEL") or "gpt-5-mini",
                                       input=[{"role": "user", "content": [{"type": "input_text", "text": PROMPT}, {"type": "input_image", "image_url": url}]}])
        payload = json.loads(resp.output_text)
    except Exception as exc:
        msg = str(exc).lower()
        if "insufficient_quota" in msg or "billing" in msg or "credit" in msg:
            raise PlanReadError("Plan reading unavailable: no credit on the OpenAI account")
        raise PlanReadError("Plan reading failed; nothing was guessed. Send the room list as text instead.")
    floors = []
    for f in payload.get("floors") or []:
        rooms = []
        for n, r in enumerate(f.get("rooms") or [], 1):
            try:
                area = float(r["area_m2"])
            except (KeyError, TypeError, ValueError):
                continue
            if area <= 0:
                continue
            room = {"room_id": f"R{n}", "name": str(r.get("name") or f"Room {n}"), "area_m2": round(area, 2), "area_source": str(r.get("area_source") or "estimated")}
            if r.get("occupancy") not in (None, ""):
                room["occupancy"] = int(float(r["occupancy"]))
            rooms.append(room)
        if rooms:
            floors.append({"name": str(f.get("name") or "Floor"), "count": max(1, int(f.get("count") or 1)), "rooms": rooms})
    if not floors:
        raise PlanReadError("No rooms with areas could be read from the plan")
    return {"floors": floors, "floor_height_m": payload.get("floor_height_m"), "issues": [str(i) for i in payload.get("issues") or []]}
