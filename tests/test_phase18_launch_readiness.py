from production.readiness import evaluate
from production.trial import run_controlled_intake_trial


def test_controlled_upwork_intake_trial():
    result = run_controlled_intake_trial()
    assert result.passed is True
    assert result.status == "ENGINEERING"
    assert result.engineering_job_id == "trial-job-001"


def test_readiness_does_not_expose_secrets_and_warns_when_unconfigured():
    report = evaluate(env={}, require_upwork_config=False)
    data = report.to_dict()
    assert report.overall == "READY_WITH_WARNINGS"
    assert all("secret" not in str(v).lower() or "never print" in str(v).lower() for v in data.values())
    upwork = next(c for c in report.checks if c.name == "upwork_configuration")
    assert upwork.status == "WARN"


def test_readiness_blocks_when_upwork_configuration_is_required():
    report = evaluate(env={}, require_upwork_config=True)
    assert report.overall == "BLOCKED"
