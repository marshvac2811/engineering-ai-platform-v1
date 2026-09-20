import json

from orchestrator.openai_provider import OpenAIIntentProvider
from orchestrator.intake import build_plan


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Resp", (), {"output_text": json.dumps(self.payload)})()


class FakeClient:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


def test_openai_provider_uses_structured_output_and_extracts_inputs():
    client = FakeClient({
        "selected_skill_id": "duct_sizing",
        "confidence": 0.96,
        "extracted_inputs_json": json.dumps({"airflow": 8000, "target_velocity_ms": 7, "duct_type": "round", "method": "velocity"}),
        "rationale": ["The request is explicitly about sizing a round duct."]
    })
    provider = OpenAIIntentProvider(client=client, model="test-model")
    decision = provider.classify_and_extract("Size a round duct for 8000 CFM at 7 m/s")
    assert decision["skill_id"] == "duct_sizing"
    assert decision["extracted_inputs"]["airflow"] == 8000
    assert client.responses.calls[0]["model"] == "test-model"
    assert client.responses.calls[0]["text"]["format"]["strict"] is True


def test_openai_provider_integrates_with_orchestrator_and_deterministic_validator():
    client = FakeClient({
        "selected_skill_id": "duct_sizing",
        "confidence": 0.97,
        "extracted_inputs_json": json.dumps({
            "airflow": 8000,
            "target_velocity_ms": 7,
            "duct_type": "round",
            "method": "velocity",
            "material": "gss",
        }),
        "rationale": ["Matched duct sizing request."]
    })
    provider = OpenAIIntentProvider(client=client)
    plan = build_plan("Please calculate my duct size.", provider=provider)
    assert plan.selected_skill_id == "duct_sizing"
    assert plan.status == "ready_for_execution"
    assert plan.extracted_inputs["airflow"] == 8000
    assert plan.missing_inputs == []
    assert plan.provider == "openai"
