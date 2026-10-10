"""Multi-revision history: a reworked job must gain version 2 (not overwrite version 1), and an unchanged
report must not create a new version. The live database has the UNIQUE(job_id, version) constraint this mirrors."""
import pytest

from jobs.models import Job, JobStatus
from jobs.supabase_store import SupabaseJobStore


class Resp:
    def __init__(self, data):
        self.data = data


class Table:
    def __init__(self, client, name):
        self.c, self.name, self.f = client, name, {}
        self.desc = False
        self.n = None
        self.op = None

    def select(self, *_):
        self.op = "select"
        return self

    def eq(self, k, v):
        self.f[k] = v
        return self

    def order(self, col, desc=False):
        self.col, self.desc = col, desc
        return self

    def limit(self, n):
        self.n = n
        return self

    def insert(self, row):
        self.op, self.row = "insert", dict(row)
        return self

    def update(self, vals):
        self.op, self.vals = "update", dict(vals)
        return self

    def upsert(self, rows, on_conflict=None):
        self.op, self.rows = "upsert", rows if isinstance(rows, list) else [rows]
        return self

    def _match(self):
        return [r for r in self.c.data.setdefault(self.name, []) if all(r.get(k) == v for k, v in self.f.items())]

    def execute(self):
        rows = self.c.data.setdefault(self.name, [])
        if self.op == "insert":
            if self.name == "engineering_report_artifacts" and any(
                    r["job_id"] == self.row["job_id"] and r["version"] == self.row["version"] for r in rows):
                raise RuntimeError("duplicate key value violates unique constraint (job_id, version)")
            rows.append(self.row)
            return Resp([self.row])
        if self.op == "update":
            m = self._match()
            for r in m:
                r.update(self.vals)
            return Resp(m)
        if self.op == "upsert":
            return Resp(self.rows)
        m = self._match()
        if getattr(self, "col", None):
            m = sorted(m, key=lambda r: r.get(self.col) or 0, reverse=self.desc)
        return Resp(m[: self.n] if self.n else m)


class Client:
    def __init__(self):
        self.data = {}

    def table(self, name):
        return Table(self, name)


def _job(report_value, status):
    job = Job.create(tenant_id="t1", source="test", inputs={}, requested_skill_id="duct_sizing")
    job.skill_id = "duct_sizing"
    job.result = {"engineering_result": {"v": 1}, "report": {"value": report_value}}
    job.status = status
    return job


def test_rework_creates_version_2_and_unchanged_report_does_not():
    client = Client()
    store = SupabaseJobStore(client)
    job = _job(100, JobStatus.HUMAN_REVIEW)
    store._persist_engineering_artifacts(job)
    store._persist_engineering_artifacts(job)                      # same content: still one row
    rows = client.data["engineering_report_artifacts"]
    assert [r["version"] for r in rows] == [1] and rows[0]["status"] == "draft"

    job.status = JobStatus.APPROVED                                # approval updates version 1 in place
    store._persist_engineering_artifacts(job)
    assert [r["version"] for r in rows] == [1] and rows[0]["status"] == "approved"

    job.result = {"engineering_result": {"v": 2}, "report": {"value": 250}}   # corrected inputs -> new content
    job.status = JobStatus.HUMAN_REVIEW
    store._persist_engineering_artifacts(job)
    assert sorted(r["version"] for r in rows) == [1, 2]
    v1 = next(r for r in rows if r["version"] == 1)
    v2 = next(r for r in rows if r["version"] == 2)
    assert v1["status"] == "approved" and v2["status"] == "draft"     # old approved version is untouched
    assert v1["report_id"] != v2["report_id"] and v1["content_sha256"] != v2["content_sha256"]
