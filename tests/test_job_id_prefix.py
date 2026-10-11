import pytest
from jobs.service import JobService
from jobs.store import InMemoryJobStore


def _svc():
    return JobService(InMemoryJobStore(), tenant_id="t1") if "tenant_id" in JobService.__init__.__code__.co_varnames else JobService(InMemoryJobStore())


def test_invalid_id_is_friendly_error():
    svc = _svc()
    with pytest.raises(ValueError):
        svc._resolve_job_id("bad id!")


def test_unknown_prefix_is_keyerror():
    with pytest.raises(KeyError):
        _svc()._resolve_job_id("fff31e1d")
