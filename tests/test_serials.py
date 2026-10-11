import re
from datetime import datetime, timezone
from jobs.serials import format_serial, local_serial
from jobs.service import JobService
from jobs.store import InMemoryJobStore
from orchestrator.intake import build_plan
from reports.register import rows_from_jobs, filter_rows


def test_serial_format_matches_requested_pattern():
    # 2026-10-10 20:10 IST == 14:40 UTC; sequence 1
    assert format_serial(datetime(2026, 10, 10, 14, 40, tzinfo=timezone.utc), 1) == "20261010201000001"
    assert re.fullmatch(r"\d{17}", local_serial())


def test_every_job_gets_unique_serial_and_can_be_found_by_it():
    st = InMemoryJobStore()
    svc = JobService(st, tenant_id="t")
    a = svc.create_from_plan(build_plan("Please size a duct for 5000 CFM"))
    b = svc.create_from_plan(build_plan("Please size a duct for 6000 CFM"))
    assert a.serial_no and b.serial_no and a.serial_no != b.serial_no
    assert svc._get(a.serial_no).job_id == a.job_id


def test_dispatched_report_lands_in_master_register_with_serial_and_is_searchable():
    st = InMemoryJobStore()
    svc = JobService(st, tenant_id="t")
    job = svc.create_from_plan(build_plan("Please size a duct for 5000 CFM"))
    svc.approve(job.job_id, reviewer="x")
    svc.dispatch(job.job_id)
    rows = rows_from_jobs(st.list(tenant_id="t"))
    hits = filter_rows(rows, view="dispatched", q=job.serial_no)
    assert [r["serial_no"] for r in hits] == [job.serial_no]
    assert filter_rows(rows, view="dispatched", q="no-such-serial") == []
