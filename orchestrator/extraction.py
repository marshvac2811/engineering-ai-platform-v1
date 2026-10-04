"""Deterministic, provider-neutral fact extraction for engineering intake."""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Sequence

@dataclass(frozen=True)
class ExtractedFact:
    field_id: str
    value: Any
    source_text: str
    start: int
    end: int
    confidence: float = 1.0
    source_unit: Optional[str] = None
    provenance: str = "user_text"

@dataclass
class ExtractionResult:
    normalized_text: str
    facts: List[ExtractedFact] = field(default_factory=list)

    def __getitem__(self, key: str):
        return self.values[key]

    values: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"normalized_text": self.normalized_text, "facts": [
            {"field_id": f.field_id, "value": f.value, "source_text": f.source_text,
             "start": f.start, "end": f.end, "confidence": f.confidence,
             "source_unit": f.source_unit, "provenance": f.provenance}
            for f in self.facts], "values": dict(self.values), "warnings": list(self.warnings)}

_UNIT_BY_FIELD = {
    "airflow": "cfm", "area_sqft": "sqft", "capacity_kw": "kw", "total_load_tr": "tr",
    "chiller_tr": "tr", "flow_m3hr": "m3/hr", "diameter_mm": "mm", "roughness_mm": "mm",
    "width_mm": "mm", "height_mm": "mm", "target_velocity_ms": "m/s",
    "target_friction_pa_per_m": "pa/m", "straight_length_m": "m", "static_head_m": "m",
    "margin_pct": "%", "wet_bulb_c": "C", "approach_c": "C", "range_c": "C",
    "drift_pct": "%", "annual_hours": "h/year", "load_factor_pct": "%",
    "tariff_per_kwh": "INR/kWh", "speed_reduction_pct": "%", "static_head_fraction": "%",
    "ambient_temp_c": "C", "altitude_m": "m", "total_vfd_kva": "kVA",
    "transformer_kva": "kVA", "efficiency_kw_per_tr": "kW/TR", "combination_ratio": "%",
}

def _extract_number(text: str, patterns: Sequence[str]) -> Optional[float]:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _legacy_extract_facts(text: str) -> Dict[str, Any]:
    """Extract only unambiguous numeric/text facts from natural language."""
    t = text.lower()
    out: Dict[str, Any] = {}

    mappings = {
        "airflow": [r"([\d,.]+)\s*(?:cfm|cubic\s*feet\s*(?:per\s*minute|/min))"],
        "area_sqft": [r"([\d,.]+)\s*(?:sq\.?\s*ft|sqft|square\s*feet)"],
        "capacity_kw": [r"([\d,.]+)\s*kw\b"],
        "capacity_old": [r"old\s*(?:capacity\s*)?([\d,.]+)\s*(?:tr|ton)"],
        "capacity_new": [r"new\s*(?:capacity\s*)?([\d,.]+)\s*(?:tr|ton)"],
        "total_load_tr": [r"([\d,.]+)\s*(?:tr|tons?)\b"],
        "chiller_tr": [r"([\d,.]+)\s*(?:tr|tons?)\b"],
        "flow_m3hr": [r"([\d,.]+)\s*m3\s*/?\s*h(?:r)?", r"([\d,.]+)\s*m³\s*/?\s*h(?:r)?"],
        "diameter_mm": [r"(?:dia(?:meter)?|pipe)\s*[:=]?\s*([\d,.]+)\s*mm", r"([\d,.]+)\s*mm\s*(?:pipe|dia(?:meter)?)"],
        "roughness_mm": [r"roughness\s*[:=]?\s*([\d,.]+)\s*mm"],
        "width_mm": [r"(?:width|w)\s*[:=]?\s*([\d,.]+)\s*mm"],
        "height_mm": [r"(?:height|(?<![a-z])h)\s*[:=]?\s*([\d,.]+)\s*mm"],
        "target_velocity_ms": [r"(?:target\s*)?velocity\s*[:=]?\s*([\d,.]+)\s*m/s", r"(?:at\s+)?([\d,.]+)\s*m/s(?:\s+velocity)?\b"],
        "target_friction_pa_per_m": [r"(?:friction|friction\s*rate)\s*[:=]?\s*([\d,.]+)\s*pa\s*/?\s*m"],
        "straight_length_m": [r"(?:straight\s*(?:length|pipe)|pipe\s*length)\s*[:=]?\s*([\d,.]+)\s*m", r"([\d,.]+)\s*m\s*(?:straight\s*length|pipe\s*length)\b"],
        "static_head_m": [\n            r"(?:static\s+(?:head|elevation|lift)|elevation\s+head)\s*[:=]?\s*([\d,.]+)\s*m",\n            r"([\d,.]+)\s*m\s*(?:static\s+(?:head|elevation|lift)|elevation\s+head)\b",\n        ],
        "margin_pct": [r"(?:margin|allowance)\s*[:=]?\s*([\d,.]+)\s*%", r"([\d,.]+)\s*%\s*(?:margin|allowance)\b"],
        "wet_bulb_c": [r"wet\s*bulb\s*[:=]?\s*([\d,.]+)\s*(?:°?c|deg c)"],
        "approach_c": [r"approach\s*[:=]?\s*([\d,.]+)\s*(?:°?c|deg c)"],
        "range_c": [r"(?:range|delta\s*t|Δt)\s*[:=]?\s*([\d,.]+)\s*(?:°?c|deg c)"],
        "coc": [r"(?:coc|cycles?\s*of\s*concentration)\s*[:=]?\s*([\d,.]+)"],
        "drift_pct": [r"drift\s*(?:loss)?\s*[:=]?\s*([\d,.]+)\s*%"],
        "annual_hours": [r"([\d,.]+)\s*(?:annual\s*hours|hours\s*/\s*year|hr\s*/\s*yr)"],
        "tariff_per_kwh": [r"(?:tariff|electricity\s*tariff)\s*[:=]?\s*(?:₹|rs\.?\s*)?([\d,.]+)\s*/?\s*kwh"],
        "load_factor_pct": [r"(?:load\s*factor)\s*[:=]?\s*([\d,.]+)\s*%"],
        "speed_reduction_pct": [r"(?:speed\s*reduction)\s*[:=]?\s*([\d,.]+)\s*%"],
        "static_head_fraction": [r"(?:static\s*head\s*fraction|static\s*head)\s*[:=]?\s*([\d,.]+)\s*%"],
        "ambient_temp_c": [r"(?:ambient|temperature)\s*[:=]?\s*([\d,.]+)\s*(?:°?c|deg c)"],
        "altitude_m": [r"(?:altitude|elevation)\s*[:=]?\s*([\d,.]+)\s*m\b"],
        "total_vfd_kva": [r"(?:vfd\s*load|total\s*vfd)\s*[:=]?\s*([\d,.]+)\s*kva"],
        "transformer_kva": [r"(?:transformer|tx)\s*(?:capacity)?\s*[:=]?\s*([\d,.]+)\s*kva"],
        "efficiency_kw_per_tr": [r"(?:efficiency|kw/tr|kW/TR)\s*[:=]?\s*([\d,.]+)"],
        "combination_ratio": [r"(?:combination|comb)\s*ratio\s*[:=]?\s*([\d,.]+)\s*%?"],
        "refrigerant": [r"\b(r410a|r32|r22|r134a)\b"],
    }
    for key, patterns in mappings.items():
        value = _extract_number(t, patterns)
        if value is not None:
            out[key] = int(value) if value.is_integer() else value
        else:
            for p in patterns:
                m = re.search(p, t, re.IGNORECASE)
                if m and key == "refrigerant":
                    out[key] = m.group(1).upper()
                    break

    if "rectangular" in t:
        out["duct_type"] = "rectangular"
    elif "round duct" in t:
        out["duct_type"] = "round"
    if "equal friction" in t:
        out["method"] = "equal_friction"
    elif "velocity method" in t or "velocity" in t:
        out["method"] = "velocity"
    if "direct heat" in t:
        out["load_method"] = "direct"
    elif "chiller data" in t or "from chiller" in t:
        out["load_method"] = "chiller"
    return out
def extract_facts(text: str, skill_id: Optional[str] = None) -> ExtractionResult:
    """Extract only values explicitly present in the request."""
    normalized = " ".join(str(text or "").split())
    values = _legacy_extract_facts(normalized)
    facts: List[ExtractedFact] = []
    for field_id, value in values.items():
        match = re.search(re.escape(str(value)), normalized, re.IGNORECASE)
        if match:
            start, end, source_text = match.start(), match.end(), match.group(0)
        else:
            start = end = -1
            source_text = str(value)
        facts.append(ExtractedFact(field_id, value, source_text, start, end, 1.0, _UNIT_BY_FIELD.get(field_id)))
    return ExtractionResult(normalized, facts, values)
