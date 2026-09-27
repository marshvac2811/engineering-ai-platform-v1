from reports.decision import report_profile, report_profiles
from skill_registry.capabilities import executable_skill_ids


def test_every_executable_skill_has_explicit_report_profile():
    profiles = report_profiles()
    assert set(profiles) == set(executable_skill_ids())
    assert all(profile.report_type for profile in profiles.values())


def test_unknown_profile_is_safe_generic_record():
    profile = report_profile("internal_unknown")
    assert profile.report_type == "engineering_workflow_record"
    assert profile.deliverables == ()
