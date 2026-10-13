"""AI-drafted recipes for BOQ lines no stored recipe covers (like SiteTrack's AI Materials button).

The model proposes consumption per ONE BOQ unit; the arithmetic stays deterministic in takeoff().
Every result is flagged ai_draft / unverified so an engineer must confirm before procurement.
Needs OPENAI_API_KEY; without it make_draft_fn() returns None and unmatched lines stay unmatched.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, Optional

_PROMPT = """You are a construction quantity surveyor in India. For ONE unit ({unit}) of this BOQ item, list the
materials needed to execute it (main material, fixings, adhesives, consumables) with realistic site consumption
and wastage percent. BOQ item: {desc}
Return only JSON: {{"base_unit": "{unit}", "materials": [{{"name": str, "unit": str,
"consumption_per_unit": number, "wastage_percent": number}}], "assumptions": [str]}}.
State thickness/specification assumptions you made. If the item is not a material-based work, return materials: []."""


def make_draft_fn(model: Optional[str] = None) -> Optional[Callable[[str, str], Dict[str, Any]]]:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        return None
    client = OpenAI(api_key=key)
    mdl = model or os.getenv("ENGINEERING_AI_MODEL") or "gpt-5-mini"

    def draft(desc: str, unit: str) -> Dict[str, Any]:
        resp = client.responses.create(model=mdl, input=_PROMPT.format(desc=desc, unit=unit or "unit"))
        return json.loads(resp.output_text)

    return draft
