"""Governed interpretation of generic pump fitting descriptions.

These mappings are preliminary source-calculator interpretations, not client facts.
They are used only when the request gives a generic fitting label and no more
specific fitting type. Every interpretation is disclosed and recommended for
client confirmation before design release.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

FITTING_INTERPRETATIONS: Dict[str, Dict[str, Any]] = {
    "90° elbow": {
        "name": "90° standard elbow",
        "ld_ratio": 30,
        "source": "source_calculator_fitting_default",
        "note": "Generic 90° elbow interpreted as standard elbow; long-radius elbow would differ.",
    },
    "tee": {
        "name": "Tee — through flow",
        "ld_ratio": 20,
        "source": "source_calculator_fitting_default",
        "note": "Generic tee interpreted as through-flow tee; branch-flow tee has a different source default.",
    },
    "isolation valve": {
        "name": "Gate valve (full open)",
        "ld_ratio": 8,
        "source": "source_calculator_fitting_default",
        "note": "Generic isolation valve interpreted as fully open gate valve; butterfly-valve loss would differ.",
    },
    "check valve": {
        "name": "Check valve (swing)",
        "ld_ratio": 135,
        "source": "source_calculator_fitting_default",
        "note": "Generic check valve interpreted as swing check valve because that is the registered source default.",
    },
}

def governed_fitting_interpretation(kind: str, quantity: float) -> Optional[Dict[str, Any]]:
    item = FITTING_INTERPRETATIONS.get(kind)
    if not item:
        return None
    return {
        "name": item["name"],
        "ld_ratio": item["ld_ratio"],
        "quantity": quantity,
        "status": "GOVERNED_PRELIMINARY_INTERPRETATION",
        "source": item["source"],
        "client_confirmation": "recommended",
        "input_text": kind,
        "note": item["note"],
    }
