from skill_registry.capabilities import CAPABILITY_CATALOG
from orchestrator.intake import build_plan


def test_every_executable_skill_routes_from_a_registered_term():
    for skill_id, capability in CAPABILITY_CATALOG.items():
        term = capability.routing_terms[0]
        plan = build_plan(term)
        assert plan.selected_skill_id == skill_id, (skill_id, term, plan.to_dict())
        assert plan.work_items[0].report_type == capability.report_type
        assert plan.selected_skill_id in CAPABILITY_CATALOG


def test_tied_or_unknown_intent_does_not_select_unregistered_skill():
    plan = build_plan("engineering work")
    assert plan.selected_skill_id is None
    assert plan.status == "awaiting_information"
