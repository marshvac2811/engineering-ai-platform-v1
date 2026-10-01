"""Provider-neutral natural-language intake and engineering skill routing.

This module deliberately keeps language understanding lightweight and auditable:
- a pluggable IntentProvider interface can later be backed by Tasklet/OpenAI/etc.
- the default provider is deterministic keyword routing + unit-aware extraction;
- missing engineering inputs are discovered from the registered deterministic skill
  itself, so this layer does not duplicate calculation rules.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
import unicodedata
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from orchestrator.engine import SKILLS
from skill_framework.registry import load_skill_registry
from skill_framework.input_resolver import resolve_input_requirements
from governance.engine import build_governance_context
from knowledge.retrieval import build_ai_project_context
from knowledge.governed_retrieval import retrieve_governed_knowledge
from knowledge.reasoning_context import build_reasoning_context


@dataclass
class IntentCandidate:
    skill_id: str
    score: int
    rationale: List[str] = field(default_factory=list)


@dataclass
class OrchestrationPlan:
    status: str
    normalized_request: str
    selected_skill_id: Optional[str]
    confidence: float
    candidates: List[IntentCandidate]
    extracted_inputs: Dict[str, Any]
    missing_inputs: List[str]
    questions: List[str]
    assumptions_context: Dict[str, Any] = field(default_factory=dict)
    standards_context: Dict[str, Any] = field(default_factory=dict)
    project_context: Dict[str, Any] = field(default_factory=dict)
    rationale: List[str] = field(default_factory=list)
    provider: str = "rule_based"
    work_items: List["OrchestrationWorkItem"] = field(default_factory=list)
    unsupported_scope: List[str] = field(default_factory=list)
    scope_analysis: Dict[str, Any] = field(default_factory=dict)
    request_understanding: Dict[str, Any] = field(default_factory=dict)
    engineering_plan: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["candidates"] = [asdict(c) for c in self.candidates]
        data["work_items"] = [item.to_dict() for item in self.work_items]
        return data


@dataclass
class OrchestrationWorkItem:
    skill_id: str
    normalized_request: str
    extracted_inputs: Dict[str, Any]
    missing_inputs: List[str]
    questions: List[str]
    status: str = "ready_for_execution"
    report_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IntentProvider(Protocol):
    name: str

    def route(self, text: str, requested_skill_id: Optional[str] = None) -> Tuple[Optional[str], List[IntentCandidate], float]:
        ...


# The routing vocabulary is intentionally explicit so the first production
# implementation can be audited. An LLM provider can replace this without
# changing the job or skill interfaces.
ROUTING_RULES: Dict[str, Sequence[str]] = {
    "facade_u_factor": ("facade u value", "facade u-factor", "facade u factor", "u value of facade", "u-factor of facade", "glass u value", "glass u-factor", "glass u factor", "u value of this facade", "curtain wall u value", "fenestration u factor", "thermal transmittance of facade"),
    "duct_sizing": ("duct", "duct size", "duct sizing", "cfm duct", "air velocity", "equal friction"),
    "pump_head": ("pump head", "tdh", "total dynamic head", "pump sizing", "pump duty", "pipe head"),
    "preliminary_load_estimation": ("cooling load", "hvac load", "tonnage", "tons of ac", "sq ft per ton", "air conditioning load"),
    "hvac_fault_diagnosis": ("troubleshoot", "fault", "trip", "diagnose", "cavitation", "refrigerant shortage", "high pressure trip"),
    "cooling_tower": ("cooling tower", "wet bulb", "approach", "blowdown", "makeup water"),
    "refrigerant_pipe_sizing": ("refrigerant pipe", "suction line", "liquid line", "r410a", "r32", "r22", "r134a"),
    "vrf_sizing": ("vrf", "vrv", "indoor unit", "outdoor unit", "combination ratio"),
    "cleanroom_ach": ("cleanroom", "ach", "air changes", "isolation room", "operating room", "icu"),
    "duct_leakage": ("duct leakage", "leakage class", "leakage test", "smacna leakage"),
    "chiller_selection_advisor": ("chiller selection", "select chiller", "chiller type", "air cooled chiller", "water cooled chiller", "chiller efficiency"),
    "bms_points_generation": ("bms points", "points list", "ai ao di do", "ddc points", "controller sizing"),
    "bms_controller_sizing": ("bms controller", "ddc controller", "controller panel"),
    "bms_cost_estimation": ("bms cost", "bms estimate", "bms budget", "bms pricing"),
    "bms_alarm_evaluation": ("bms alarm", "alarm threshold", "point alarm", "sensor alarm"),
    "vfd_energy_savings": ("vfd energy", "vfd savings", "speed reduction", "affinity law", "vfd saving"),
    "vfd_derating": ("vfd derating", "vfd altitude", "vfd temperature", "drive sizing"),
    "harmonic_screening": ("harmonics", "harmonic screening", "ieee 519", "vfd harmonic"),
    "hvac_decarbonisation": ("decarbon", "decarbonisation", "carbon saving", "hvac retrofit", "asset life extension"),
    "energy_payback": ("payback", "energy savings", "energy cost saving", "roi", "retrofit payback"),
    "hvac_boq": ("boq", "bill of quantities", "quantity estimate", "hvac estimate", "tender estimate"),
    "deviation_statement": ("deviation statement", "compliance statement", "technical compliance", "tender compliance"),
}

FIELD_QUESTIONS = {
    "components": "Provide facade/fenestration components as JSON with name, area_m2 and u_factor for each component.",
    "airflow": "What is the airflow in CFM?",
    "method": "Which duct sizing method should be used: velocity or equal friction?",
    "duct_type": "Should the duct be round or rectangular?",
    "target_velocity_ms": "What target duct velocity should I use in m/s?",
    "target_friction_pa_per_m": "What target friction rate should I use in Pa/m?",
    "width_mm": "What rectangular duct width should be checked, in mm?",
    "height_mm": "What rectangular duct height should be checked, in mm?",
    "material": "What duct material should be used (for example gss, pu_panel, fabric or flexible)?",
    "flow_m3hr": "What design water flow is required, in mÂ³/hr?",
        "roughness_mm": [r"roughness\s*[:=]?\s*([\d,.]+)\s*mm", r"([\d,.]+)\s*mm\s*(?:roughness|roughness\s*value)\b"],
    "diameter_mm": "What pipe internal diameter should be checked, in mm?",
    "roughness_mm": "What pipe roughness should be used, in mm?",
    "straight_length_m": "What is the straight pipe length, in metres?",
    "static_head_m": "What is the static/elevation head, in metres?",
    "margin_pct": "What design margin should be applied, in percent?",
    "building_type": "What building type is this (office, retail, residential, hospital, etc.)?",
    "area_sqft": "What floor area should be estimated, in square feet?",
    "climate_zone": "Which climate zone should be used (hot_dry, warm_humid, composite, moderate or cold)?",
    "occupancy": "What is the actual occupancy, if known?",
    "rule_id": "Which diagnostic rule or fault condition should be evaluated?",
    "values": "Please provide the measured fault-condition values for the selected diagnostic rule.",
    "load_method": "For cooling tower sizing, should the load come from chiller data or a direct heat load?",
    "range_c": "What cooling-tower range should be used, in Â°C?",
    "wet_bulb_c": "What is the site design wet-bulb temperature, in Â°C?",
    "approach_c": "What cooling-tower approach should be used, in Â°C?",
    "coc": "What cycles of concentration (COC) should be used?",
    "drift_pct": "What drift loss should be used, as percent of water flow?",
    "chiller_tr": "What chiller capacity should be used, in TR?",
    "chiller_cop": "What chiller COP should be used?",
    "direct_load_kw": "What direct heat-rejection load should be used, in kW?",
    "refrigerant": "Which refrigerant should be used (R410A, R32, R22 or R134a)?",
    "capacity_kw": "What cooling capacity should be used, in kW?",
    "suction_velocity": "What target suction-line velocity should be used, in m/s?",
    "liquid_velocity": "What target liquid-line velocity should be used, in m/s?",
    "suction_length": "What is the suction-line equivalent length, in metres?",
    "liquid_length": "What is the liquid-line equivalent length, in metres?",
    "zones": "Please provide the VRF zones with area and load factor for each zone.",
    "combination_ratio": "What VRF indoor/outdoor combination ratio should be used, in percent?",
    "total_pipe_length_m": "What is the total VRF piping length, in metres?",
    "farthest_branch_length_m": "What is the farthest VRF branch length, in metres?",
    "odu_idu_height_diff_m": "What is the ODU-to-IDU height difference, in metres?",
    "idu_idu_height_diff_m": "What is the maximum IDU-to-IDU height difference, in metres?",
    "sections": "Please provide the duct sections (rectangular or round) and their lengths so total surface area can be calculated.",
    "test_pressure_pa": "What duct leakage test pressure should be used, in Pa?",
    "measured_leakage_ls": "What measured leakage should be used, in L/s?",
    "target_class": "What leakage class is specified (for example 3, 6, 12 or 24)?",
    "total_load_tr": "What total chiller cooling load should be used, in TR?",
    "water_available": "Is a suitable condenser-water source available?",
    "space_available": "Is there ample space for the cooling tower/plant room?",
    "efficiency_priority": "Is lowest kW/TR a high priority or standard priority?",
    "efficiency_kw_per_tr": "What chiller efficiency should be used, in kW/TR?",
    "annual_hours": "What are the annual operating hours?",
    "load_factor_pct": "What average load factor should be used, in percent?",
    "tariff_per_kwh": "What electricity tariff should be used, in â‚¹/kWh?",
    "duty_modules": "How many duty chiller modules are required?",
    "redundancy_level": "What redundancy is required: N, N+1 or N+2?",
    "equipment_counts": "Please provide the BMS equipment counts by equipment type.",
    "points_per_controller": "How many BMS points should each controller support?",
    "controllers_per_panel": "How many controllers should each BMS panel contain?",
    "total_points": "What total BMS I/O point count should be used?",
    "ahu_count": "How many AHUs are included?",
    "chiller_count": "How many chillers are included?",
    "pump_count": "How many pumps are included?",
    "vfd_count": "How many VFDs are included?",
    "misc_points": "How many miscellaneous BMS points are included?",
    "cost_per_point": "What cost per BMS point should be used?",
    "cost_per_controller": "What cost per controller should be used?",
    "cost_per_panel": "What cost per panel should be used?",
    "bms_software_cost": "What BMS software cost should be used?",
    "engineering_pct": "What BMS engineering percentage should be used?",
    "point_type": "Is the BMS point analog or digital?",
    "point_id": "What BMS point ID should be evaluated?",
    "value": "What is the current point value/state?",
    "motor_kw": "What motor power should be used, in kW?",
    "speed_reduction_pct": "What speed reduction should be used, in percent?",
    "static_head_fraction": "What fraction of head is static, in percent?",
    "ambient_temp_c": "What ambient temperature should be used, in Â°C?",
    "altitude_m": "What site altitude should be used, in metres?",
    "total_vfd_kva": "What is the total VFD load, in kVA?",
    "transformer_kva": "What is the transformer capacity, in kVA?",
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


def _normalize_intake_text(text: str) -> str:
    """Normalize common engineering-unit Unicode variants before extraction."""
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    normalized = normalized.replace("³", "3").replace("²", "2")
    normalized = normalized.replace("°", " deg ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_facts(text: str) -> Dict[str, Any]:
    """Extract unambiguous engineering facts from natural-language prose."""
    t = _normalize_intake_text(text)
    out: Dict[str, Any] = {}

    if re.search(r"\bcfm\b", t, re.IGNORECASE):
        out["airflow_unit"] = "cfm"
    elif re.search(r"m3\s*/?\s*h(?:r)?|m³\s*/?\s*h(?:r)?", t, re.IGNORECASE):
        out["airflow_unit"] = "m3/hr"

    mappings = {
        "airflow": [r"([\d,.]+)\s*(?:cfm|cubic\s*feet\s*(?:per\s*minute|/min))"],
        "area_sqft": [r"([\d,.]+)\s*(?:sq\.?\s*ft|sqft|square\s*feet)"],
        "capacity_kw": [r"([\d,.]+)\s*kw\b"],
        "capacity_old": [r"old\s*(?:capacity\s*)?([\d,.]+)\s*(?:tr|ton)"],
        "capacity_new": [r"new\s*(?:capacity\s*)?([\d,.]+)\s*(?:tr|ton)"],
        "total_load_tr": [r"([\d,.]+)\s*(?:tr|tons?)\b"],
        "chiller_tr": [r"([\d,.]+)\s*(?:tr|tons?)\b"],
        "flow_m3hr": [r"(?:design\s+water\s+)?flow(?:\s+rate)?\s*(?:is|of|=|:)?\s*([\d,.]+)\s*m3\s*/?\s*h(?:r)?\b", r"([\d,.]+)\s*m3\s*/?\s*h(?:r)?\b"],
        "diameter_mm": [r"(?:pipe\s+internal\s+)?diameter\s*(?:is|of|=|:)?\s*([\d,.]+)\s*mm\b", r"(?:pipe|dia(?:meter)?)\s*(?:is|of|=|:)?\s*([\d,.]+)\s*mm\b", r"([\d,.]+)\s*mm\s*(?:pipe|dia(?:meter)?)\b"],
        "roughness_mm": [r"roughness\s*(?:is|of|=|:)?\s*([\d,.]+)\s*mm\b", r"([\d,.]+)\s*mm\s*(?:roughness|roughness\s*value)\b"],
        "width_mm": [r"(?:width|w)\s*(?:is|of|=|:)?\s*([\d,.]+)\s*mm\b"],
        "height_mm": [r"(?:height|(?<![a-z])h)\s*(?:is|of|=|:)\s*([\d,.]+)\s*mm\b"],
        "target_velocity_ms": [r"(?:target\s*)?velocity\s*(?:is|of|=|:)?\s*([\d,.]+)\s*m/s", r"(?:at\s+)?([\d,.]+)\s*m/s(?:\s+velocity)?\b"],
        "target_friction_pa_per_m": [r"(?:friction|friction\s*rate)\s*(?:is|of|=|:)?\s*([\d,.]+)\s*pa\s*/?\s*m\b"],
        "straight_length_m": [r"(?:total\s+)?straight\s+pipe\s+length\s*(?:is|of|=|:)?\s*([\d,.]+)\s*m\b", r"(?:pipe\s+length)\s*(?:is|of|=|:)?\s*([\d,.]+)\s*m\b", r"([\d,.]+)\s*m\s*(?:straight\s+pipe\s+length|pipe\s+length)\b"],
        "static_head_m": [r"(?:static\s*(?:/|or\s+)?\s*elevation|elevation)\s*(?:head|lift)\s*(?:is|of|=|:)?\s*([\d,.]+)\s*m\b", r"static\s+head\s*(?:is|of|=|:)?\s*([\d,.]+)\s*m\b", r"([\d,.]+)\s*m\s*(?:static|elevation)\s*(?:head|lift)\b"],
        "margin_pct": [r"(?:design\s+)?(?:margin|allowance)\s*(?:is|of|=|:)?\s*([\d,.]+)\s*(?:%|percent)\b", r"([\d,.]+)\s*(?:%|percent)\s*(?:design\s+)?(?:margin|allowance)\b"],
        "wet_bulb_c": [r"wet\s*bulb\s*[:=]?\s*([\d,.]+)\s*(?:Â°?c|deg c)"],
        "approach_c": [r"approach\s*[:=]?\s*([\d,.]+)\s*(?:Â°?c|deg c)"],
        "range_c": [r"(?:range|delta\s*t|Î”t)\s*[:=]?\s*([\d,.]+)\s*(?:Â°?c|deg c)"],
        "coc": [r"(?:coc|cycles?\s*of\s*concentration)\s*[:=]?\s*([\d,.]+)"],
        "drift_pct": [r"drift\s*(?:loss)?\s*[:=]?\s*([\d,.]+)\s*%"],
        "annual_hours": [r"([\d,.]+)\s*(?:annual\s*hours|hours\s*/\s*year|hr\s*/\s*yr)"],
        "tariff_per_kwh": [r"(?:tariff|electricity\s*tariff)\s*[:=]?\s*(?:â‚¹|rs\.?\s*)?([\d,.]+)\s*/?\s*kwh"],
        "load_factor_pct": [r"(?:load\s*factor)\s*[:=]?\s*([\d,.]+)\s*%"],
        "speed_reduction_pct": [r"(?:speed\s*reduction)\s*[:=]?\s*([\d,.]+)\s*%"],
        "static_head_fraction": [r"(?:static\s*head\s*fraction|static\s*head)\s*[:=]?\s*([\d,.]+)\s*%"],
        "ambient_temp_c": [r"(?:ambient|temperature)\s*[:=]?\s*([\d,.]+)\s*(?:Â°?c|deg c)"],
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

    material_patterns = [
        (r"\b(?:gi|g\.i\.|galvanized\s*iron|galvanised\s*iron)\b(?:\s+pipe)?", "gi"),
        (r"\b(?:ms|m\.s\.|mild\s*steel|carbon\s*steel)\b(?:\s+pipe)?", "ms_cs"),
        (r"\b(?:copper|cu)\b(?:\s+pipe)?", "copper"),
        (r"\b(?:upvc|u\.p\.v\.c\.|u-pvc|u\s+pvc|pvc)\b(?:\s+pipe)?", "upvc_pvc"),
        (r"\b(?:hdpe|h\.d\.p\.e\.|high\s+density\s+polyethylene)\b(?:\s+pipe)?", "hdpe"),
    ]
    for pattern, material in material_patterns:
        if re.search(pattern, t, re.IGNORECASE):
            out["material"] = material
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


class RuleBasedIntentProvider:
    name = "rule_based"

    def route(self, text: str, requested_skill_id: Optional[str] = None) -> Tuple[Optional[str], List[IntentCandidate], float]:
        if requested_skill_id:
            if requested_skill_id not in SKILLS:
                return None, [], 0.0
            return requested_skill_id, [IntentCandidate(requested_skill_id, 999, ["Explicit skill_id supplied by caller."])], 1.0

        t = text.lower()
        candidates: List[IntentCandidate] = []
        for skill_id, terms in ROUTING_RULES.items():
            matched = [term for term in terms if term in t]
            if matched:
                score = sum(2 if " " in term else 1 for term in matched)
                candidates.append(IntentCandidate(skill_id, score, [f"Matched phrase: {m}" for m in matched]))
        candidates.sort(key=lambda c: (-c.score, c.skill_id))
        if not candidates:
            return None, [], 0.0
        top = candidates[0]
        second = candidates[1].score if len(candidates) > 1 else 0
        confidence = min(0.99, 0.55 + 0.1 * top.score + (0.1 if top.score > second else 0))
        if len(candidates) > 1 and top.score == second:
            return None, candidates[:5], 0.45
        return top.skill_id, candidates[:5], confidence


def _report_type_for_skill(skill_id: Optional[str]) -> str:
    if not skill_id:
        return ""
    try:
        from skill_registry.capabilities import get_capability
        capability = get_capability(skill_id)
        return capability.report_type if capability else ""
    except Exception:
        return ""


def build_plan(
    text: str,
    *,
    requested_skill_id: Optional[str] = None,
    provided_inputs: Optional[Dict[str, Any]] = None,
    project_context: Optional[Dict[str, Any]] = None,
    standards_context: Optional[Dict[str, Any]] = None,
    assumptions_context: Optional[Dict[str, Any]] = None,
    provider: Optional[IntentProvider] = None,
    _compound: bool = True,
) -> OrchestrationPlan:
    provider = provider or RuleBasedIntentProvider()
    if _compound and not hasattr(provider, "classify_and_extract"):
        clauses = [part.strip(" ;") for part in re.split(r";\s*|\s+also\s+", text.strip(), flags=re.IGNORECASE) if part.strip()]
        expanded: List[str] = []
        for clause in clauses:
            pieces = re.split(r"\s+and\s+(?=(?:size|calculate|select|generate|estimate|evaluate|check|design)\b)", clause, flags=re.IGNORECASE)
            expanded.extend(p.strip() for p in pieces if p.strip())
        if len(expanded) > 1:
            supported: List[OrchestrationWorkItem] = []
            unsupported: List[str] = []
            first_plan: Optional[OrchestrationPlan] = None
            for clause in expanded:
                child = build_plan(clause, requested_skill_id=requested_skill_id, provided_inputs=provided_inputs, project_context=project_context, standards_context=standards_context, assumptions_context=assumptions_context, provider=provider, _compound=False)
                if first_plan is None:
                    first_plan = child
                if child.selected_skill_id:
                    supported.append(OrchestrationWorkItem(skill_id=child.selected_skill_id, normalized_request=child.normalized_request, extracted_inputs=child.extracted_inputs, missing_inputs=child.missing_inputs, questions=child.questions, status=child.status, report_type=_report_type_for_skill(child.selected_skill_id)))
                else:
                    unsupported.append(re.sub(r"^also\s+", "", clause, flags=re.IGNORECASE))
            if supported:
                return OrchestrationPlan(
                    status="awaiting_information" if any(x.missing_inputs for x in supported) else "ready_for_execution",
                    normalized_request=text.strip(),
                    selected_skill_id=supported[0].skill_id,
                    confidence=min((first_plan.confidence if first_plan else 0.0), 0.99),
                    candidates=first_plan.candidates if first_plan else [],
                    extracted_inputs=supported[0].extracted_inputs,
                    missing_inputs=sorted({item for x in supported for item in x.missing_inputs}),
                    questions=[q for x in supported for q in x.questions],
                    assumptions_context=assumptions_context,
                    standards_context=standards_context,
                    project_context=project_context,
                    rationale=["Compound request split into independently routed engineering work items."],
                    provider=getattr(provider, "name", "rule_based"),
                    work_items=supported,
                    unsupported_scope=unsupported,
                )
    project_context = build_ai_project_context(text, project_context or {})
    standards_context = standards_context or {}
    assumptions_context = assumptions_context or {}
    provided_inputs = dict(provided_inputs or {})

    provider_extracted: Dict[str, Any] = {}
    provider_rationale: List[str] = []
    request_understanding: Dict[str, Any] = {}
    governed_knowledge = retrieve_governed_knowledge(query=text, project_context=project_context, jurisdiction=project_context.get("jurisdiction") or standards_context.get("jurisdiction"), skill_id=requested_skill_id, standards_context=standards_context)
    reasoning_context = build_reasoning_context(governed_knowledge)
    if requested_skill_id:
        skill_id, candidates, confidence = provider.route(text, requested_skill_id)
    elif hasattr(provider, "classify_and_extract"):
        decision = provider.classify_and_extract(
            text,
            {
                "provided_inputs": provided_inputs,
                "project_context": {
                    **project_context,
                    "documents": [
                        {k: d.get(k) for k in ("attachment_id", "filename", "mime_type", "source_type", "sha256", "extraction_status", "metadata", "warnings")}
                        for d in project_context.get("documents", []) if isinstance(d, dict)
                    ],
                },
                "standards_context": standards_context,
                "assumptions_context": assumptions_context,
                "governed_knowledge": governed_knowledge,
                "reasoning_context": reasoning_context,
            },
        )
        skill_id = decision.get("skill_id")
        confidence = float(decision.get("confidence", 0.0))
        provider_extracted = dict(decision.get("extracted_inputs") or {})
        provider_rationale = [str(x) for x in decision.get("rationale") or []]
        request_understanding = {
            "objective": decision.get("objective", ""),
            "disciplines": list(decision.get("disciplines") or []),
            "requested_outputs": list(decision.get("requested_outputs") or []),
            "methodology": dict(decision.get("methodology") or {}),
            "governance": dict(decision.get("governance") or {}),
            "entities": list(decision.get("entities") or []),
            "constraints": list(decision.get("constraints") or []),
            "tasks": list(decision.get("tasks") or []),
            "reasoning": dict(decision.get("reasoning") or {}),
            "evidence_usage": list(decision.get("evidence_usage") or []),
            "missing_evidence": list(decision.get("missing_evidence") or []),
            "compliance_claims": list(decision.get("compliance_claims") or []),
            "confidence": confidence,
            "source": provider.name,
        }
        candidates = (
            [IntentCandidate(skill_id, int(round(confidence * 1000)), provider_rationale)]
            if skill_id
            else []
        )
    else:
        skill_id, candidates, confidence = provider.route(text, requested_skill_id)

    extracted = extract_facts(text)
    merged = {**provider_extracted, **extracted, **provided_inputs}
    # Scope is an AI interpretation concern, not a recipe/library lookup.
    # Keep the field for API compatibility, but do not derive engineering work
    # from a quantity catalog.
    scope_analysis = {"status": "ai_interpretation_pending", "verticals": [], "capabilities": [], "unsupported_scope": []}

    if skill_id is None:
        status = "awaiting_information"
        question = ("I understand this is an engineering request, but I cannot safely map it to a registered execution capability yet. "
                    "Please describe the engineering objective and provide any project drawings, specifications, measurements, or other data you have. "
                    "I will determine the discipline, methodology and governing requirements rather than asking you to select a skill.")
        return OrchestrationPlan(
            status=status,
            normalized_request=text.strip(),
            selected_skill_id=None,
            confidence=confidence,
            candidates=candidates,
            extracted_inputs=merged,
            missing_inputs=[],
            questions=[question],
            assumptions_context=assumptions_context,
            standards_context=build_governance_context(skill_id=None, project_context=project_context, standards_context=standards_context),
            project_context=project_context,
            rationale=["AI could not establish a safe executable capability from the registered capability set."],
            provider=provider.name,
            work_items=[],
            unsupported_scope=[],
            scope_analysis=scope_analysis,
            request_understanding=request_understanding,
            engineering_plan={"status": "capability_required", "tasks": [], "execution_order": [], "human_review_required": True},
        )

    registry_path = Path(__file__).resolve().parents[1] / "skill_registry" / "registry.yaml"
    registry = load_skill_registry(registry_path)
    definition = registry.get(skill_id)

    registry_resolution = resolve_input_requirements(definition, merged)

    missing = registry_resolution.missing_inputs
    questions = registry_resolution.questions
    rationale_source = "registry-defined input contract"

    status = "awaiting_information" if missing else "ready_for_execution"
    rationale = [f"Selected {skill_id} using {provider.name} intent routing."]
    rationale.extend(provider_rationale)
    rationale.append(
        f"Input requirements resolved using {rationale_source}."
    )

    if registry_resolution.invalid_inputs:
        rationale.append(
            "Registry input validation warnings: "
            + "; ".join(registry_resolution.invalid_inputs)
        )

    governance_input = dict(standards_context or {})
    governance_input["disciplines"] = list(request_understanding.get("disciplines") or governance_input.get("disciplines") or [])
    governance_input["objective"] = request_understanding.get("objective") or governance_input.get("objective") or text.strip()
    governance = build_governance_context(
        skill_id=skill_id,
        project_context=project_context,
        standards_context=governance_input,
        methodology=request_understanding.get("methodology"),
    )
    governed_knowledge = retrieve_governed_knowledge(
        query=text,
        project_context=project_context,
        jurisdiction=project_context.get("jurisdiction") or governance_input.get("jurisdiction"),
        skill_id=skill_id,
        disciplines=request_understanding.get("disciplines") or [],
        objective=request_understanding.get("objective") or text.strip(),
        standards_context=governance_input,
    )
    reasoning_context = build_reasoning_context(governed_knowledge)
    governance["governed_knowledge"] = governed_knowledge
    governance["reasoning_context"] = reasoning_context
    from orchestrator.planner import build_engineering_plan
    understanding_for_planner = dict(request_understanding)
    understanding_for_planner["capability_id"] = skill_id
    ai_tasks = list(request_understanding.get("tasks") or [])
    planned_items = []
    if ai_tasks:
        for task in ai_tasks:
            if not isinstance(task, dict):
                continue
            planned_items.append({
                "capability_id": task.get("capability_id") or task.get("skill_id"),
                "objective": task.get("objective") or text.strip(),
            })
    if not planned_items:
        planned_items = [{"capability_id": skill_id, "objective": request_understanding.get("objective") or text.strip()}]
    engineering_plan = build_engineering_plan(
        understanding=understanding_for_planner,
        registry=registry,
        inputs=merged,
        work_items=planned_items,
        governance=governance,
    )
    if engineering_plan.get("status") == "capability_required":
        status = "awaiting_information"
        questions = list(questions) + ["Part of this request requires an engineering capability that is not currently registered. No calculation has been performed for that part."]
    elif engineering_plan.get("status") == "awaiting_information":
        status = "awaiting_information"
    return OrchestrationPlan(
        status,
        text.strip(),
        skill_id,
        confidence,
        candidates,
        merged,
        missing,
        questions,
        assumptions_context,
        governance,
        project_context,
        rationale,
        provider.name,
        work_items=[OrchestrationWorkItem(skill_id=skill_id, normalized_request=text.strip(), extracted_inputs=merged, missing_inputs=missing, questions=questions, status=status, report_type=_report_type_for_skill(skill_id))],
        unsupported_scope=scope_analysis.get("unsupported_scope", []),
        scope_analysis=scope_analysis,
        request_understanding=request_understanding,
        engineering_plan=engineering_plan,
    )

