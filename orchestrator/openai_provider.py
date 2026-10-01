"""OpenAI-backed intent routing/extraction provider.

This provider is deliberately limited to language understanding:
- classify the user's request against the registered skill IDs;
- extract explicit engineering inputs from the request;
- return structured JSON only.

It must never perform engineering calculations. Deterministic skill execution,
validation, governed assumptions/standards and human review remain outside the
LLM boundary.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from orchestrator.engine import SKILLS
from orchestrator.intake import IntentCandidate
from orchestrator.provider import ProviderUnavailableError


_OPENAI_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_skill_id": {"type": "string"},
        "confidence": {"type": "number"},
        "extracted_inputs_json": {"type": "string"},
        "objective": {"type": "string"},
        "disciplines_json": {"type": "string"},
        "requested_outputs_json": {"type": "string"},
        "methodology_json": {"type": "string"},
        "governance_json": {"type": "string"},
        "rationale": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["selected_skill_id", "confidence", "extracted_inputs_json", "objective",
                 "disciplines_json", "requested_outputs_json", "methodology_json",
                 "governance_json", "rationale"],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """You are the universal AI engineering interpretation layer for a commercial engineering platform.

Understand arbitrary engineering requests. You are NOT the calculation engine.

1. Identify objective, discipline(s), entities and requested outputs.
2. Select a registered execution skill only when it genuinely matches the work.
3. Extract only explicit or unambiguous inputs; never invent values.
4. Identify likely methodology and governing bodies/standards, but never invent clauses,
   limits, editions or compliance results. Mark governance verification as required unless
   a verified source is supplied in context.
5. If no registered skill can safely execute the work, leave selected_skill_id empty.
6. Never calculate engineering results or claim compliance.

The client must not need to know skill IDs, field names, or which standard applies.
Return JSON only. The *_json fields contain JSON-encoded arrays/objects.
"""


class OpenAIIntentProvider:
    name = "openai"

    def __init__(self, *, client: Any = None, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or os.getenv("ENGINEERING_AI_MODEL", "gpt-5.6")
        self._client = client
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")

    def _client_or_raise(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise ProviderUnavailableError("OPENAI_API_KEY is not configured")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise ProviderUnavailableError("The optional 'openai' package is not installed") from exc
        self._client = OpenAI(api_key=self._api_key)
        return self._client

    def classify_and_extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        client = self._client_or_raise()
        context = context or {}
        skill_list = sorted(SKILLS)
        user_payload = {
            "request": text,
            "registered_skill_ids": skill_list,
            "context": context,
        }
        try:
            response = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "engineering_intent",
                        "schema": _OPENAI_SCHEMA,
                        "strict": True,
                    }
                },
            )
        except Exception as exc:
            raise ProviderUnavailableError(f"OpenAI intent request failed: {exc}") from exc

        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise ProviderUnavailableError("OpenAI intent response did not contain output_text")
        try:
            payload = json.loads(output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError("OpenAI intent response was not valid JSON") from exc

        selected_skill_id = str(payload.get("selected_skill_id", ""))
        if selected_skill_id and selected_skill_id not in SKILLS:
            selected_skill_id = ""

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        raw_inputs = payload.get("extracted_inputs_json", "{}")
        try:
            extracted_inputs = json.loads(raw_inputs) if isinstance(raw_inputs, str) else {}
        except json.JSONDecodeError:
            extracted_inputs = {}
        if not isinstance(extracted_inputs, dict):
            extracted_inputs = {}

        def _json_value(name: str, default: Any) -> Any:
            raw = payload.get(name, default)
            try:
                return json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, json.JSONDecodeError):
                return default

        return {
            "skill_id": selected_skill_id or None,
            "confidence": confidence,
            "extracted_inputs": extracted_inputs,
            "objective": str(payload.get("objective", "")),
            "disciplines": _json_value("disciplines_json", []),
            "requested_outputs": _json_value("requested_outputs_json", []),
            "methodology": _json_value("methodology_json", {}),
            "governance": _json_value("governance_json", {}),
            "rationale": [str(x) for x in payload.get("rationale", [])],
        }

    def route(
        self,
        text: str,
        requested_skill_id: Optional[str] = None,
    ) -> Tuple[Optional[str], List[IntentCandidate], float]:
        if requested_skill_id:
            if requested_skill_id not in SKILLS:
                return None, [], 0.0
            return requested_skill_id, [IntentCandidate(requested_skill_id, 999, ["Explicit skill_id supplied by caller."])], 1.0

        decision = self.classify_and_extract(text)
        skill_id = decision["skill_id"]
        if not skill_id:
            return None, [], decision["confidence"]
        candidate = IntentCandidate(skill_id, int(round(decision["confidence"] * 1000)), decision["rationale"])
        return skill_id, [candidate], decision["confidence"]


__all__ = ["OpenAIIntentProvider"]
