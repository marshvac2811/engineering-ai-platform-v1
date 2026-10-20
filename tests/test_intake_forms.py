import re

from integrations.service import InMemoryIntegrationStore
from crm.store import InMemoryCRMStore
from jobs.store import InMemoryJobStore
from api.app import APIApp
from intake_forms import all_forms, form_for, render_text, new_skill_needed
from orchestrator.registry_loader import load_registry
from tests.test_api import call

LEAK = re.compile(r"default|margin|deterministic|governed|source-ref|engine|internal|recipe|wastage|diversity|benchmark|norm\b|\?C|[a-z]+_[a-z]+", re.I)


def _executable():
    return [s for s in load_registry()["skills"] if "required_inputs" in s]


def test_every_executable_skill_has_a_form():
    assert {f["skill_id"] for f in all_forms()} == {s["skill_id"] for s in _executable()}
    assert len(all_forms()) >= 50


def test_form_keeps_every_registry_required_input():
    for s in _executable():
        keys = {f["key"] for f in form_for(s["skill_id"])["fields"] if f["required"]}
        assert {r["name"] for r in s["required_inputs"]} <= keys, s["skill_id"]


def test_client_text_never_shows_basis_or_internal_wording():
    for f in all_forms():
        text = render_text(f, "Mr Rao")
        body = text.split("Required:", 1)[1].split("Drawings,", 1)[0]
        assert not LEAK.search(body), (f["skill_id"], LEAK.search(body).group(0))
        assert "Required:" in text


def test_engineering_settings_are_not_asked_of_client():
    text = render_text(form_for("cooling_tower"))
    assert "drift" not in text.lower() and "cycles" not in text.lower()
    assert "Design wet-bulb" in text


def test_either_or_skills_ask_for_the_client_data():
    assert "Bill of quantities" in render_text(form_for("boq_takeoff"))
    assert "Floor list" in render_text(form_for("mep_building_package"))


def test_api_forms_and_gap_list():
    app = APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore())
    st, body = call(app, "GET", "/v1/intake-forms")
    assert st.startswith("200") and body["count"] >= 50
    st, body = call(app, "GET", "/v1/intake-forms/pump_head")
    assert st.startswith("200") and "Static head" in body["reply_text"]
    st, _ = call(app, "GET", "/v1/intake-forms/nope")
    assert st.startswith("404")
    # a request no skill covers is listed as "new skill needed"; a covered one is not
    call(app, "POST", "/v1/intake", {"message": "Design a thermal energy storage ice tank for a 1200 TR district cooling plant"})
    call(app, "POST", "/v1/intake", {"message": "Calculate the ventilation rate for a 400 m2 office floor with 60 occupants, space type office"})
    st, body = call(app, "GET", "/v1/intake-gaps")
    assert st.startswith("200") and body["count"] == 1
    assert "ice tank" in body["gaps"][0]["request"]


def test_new_skill_needed_ignores_jobs_with_a_skill():
    jobs = [{"job_id": "a", "status": "awaiting_information", "orchestration": {"selected_skill_id": "duct_sizing"}},
            {"job_id": "b", "status": "awaiting_information", "orchestration": {"normalized_request": "x"}}]
    assert [g["job_id"] for g in new_skill_needed(jobs)] == ["b"]
