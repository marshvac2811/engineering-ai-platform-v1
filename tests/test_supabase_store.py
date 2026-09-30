from jobs.models import Job, JobStatus
from jobs.supabase_store import SupabaseJobStore


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self._filters = {}

    def upsert(self, rows, on_conflict=None):
        self._pending_upsert = rows if isinstance(rows, list) else [rows]
        return self

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def limit(self, _n):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        if hasattr(self, "_pending_upsert"):
            for row in self._pending_upsert:
                key = "job_id" if self.name == "automation_jobs" else "event_key"
                existing = next((x for x in self.client.data[self.name] if x.get(key) == row.get(key)), None)
                if existing:
                    existing.update(row)
                else:
                    self.client.data[self.name].append(dict(row))
            return FakeResponse(self._pending_upsert)

        rows = list(self.client.data[self.name])
        for key, value in self._filters.items():
            rows = [x for x in rows if x.get(key) == value]
        return FakeResponse(rows)


class FakeRPC:
    def __init__(self, client, name, args):
        self.client = client
        self.name = name
        self.args = args

    def execute(self):
        if self.name == "claim_next_automation_job":
            rows = [
                row for row in self.client.data["automation_jobs"]
                if row.get("status") == "queued"
            ]
            if not rows:
                return FakeResponse([])
            row = rows[0]
            row["locked_by"] = self.args["p_worker_id"]
            return FakeResponse([row])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.data = {"automation_jobs": [], "automation_job_events": []}

    def table(self, name):
        return FakeTable(self, name)

    def rpc(self, name, args):
        return FakeRPC(self, name, args)


def test_supabase_store_save_and_get_round_trip():
    client = FakeClient()
    store = SupabaseJobStore(client)
    job = Job.create(tenant_id="test-tenant", source="test", inputs={"flow_m3hr": 100}, requested_skill_id="duct_sizing")
    job.transition(JobStatus.QUEUED, "queued")

    store.save(job)
    restored = store.get(job.job_id)

    assert restored is not None
    assert restored.job_id == job.job_id
    assert restored.status == JobStatus.QUEUED
    assert restored.inputs["flow_m3hr"] == 100
    assert restored.orchestration == {}
    assert len(restored.events) == 1



def test_supabase_store_event_persistence_is_idempotent_across_round_trips():
    client = FakeClient()
    store = SupabaseJobStore(client)
    job = Job.create(
        tenant_id="test-tenant",
        source="test",
        inputs={"flow_m3hr": 100},
        requested_skill_id="duct_sizing",
    )
    job.transition(JobStatus.QUEUED, "queued")

    store.save(job)
    restored_1 = store.get(job.job_id)
    assert restored_1 is not None
    assert len(restored_1.events) == 1

    store.save(restored_1)
    restored_2 = store.get(job.job_id)
    assert restored_2 is not None
    assert len(restored_2.events) == 1

    store.save(restored_2)
    restored_3 = store.get(job.job_id)
    assert restored_3 is not None
    assert len(restored_3.events) == 1

    persisted_events = client.data["automation_job_events"]
    assert len(persisted_events) == 1
    assert persisted_events[0]["event_key"] == f"{job.job_id}:0"

def test_supabase_store_claim_next_uses_worker_id():
    client = FakeClient()
    store = SupabaseJobStore(client)
    job = Job.create(tenant_id="test-tenant", source="test", inputs={}, requested_skill_id="pump_head")
    job.transition(JobStatus.QUEUED, "queued")
    store.save(job)

    claimed = store.claim_next("worker-a")
    assert claimed is not None
    assert claimed.job_id == job.job_id



def test_supabase_store_persists_current_orchestration_state():
    client = FakeClient()
    store = SupabaseJobStore(client)
    job = Job.create(
        tenant_id="test-tenant", source="test", inputs={"flow_m3hr": 100},
        requested_skill_id="pump_head",
        orchestration={"status": "awaiting_information", "missing_inputs": ["roughness_mm", "material"]},
    )
    store.save(job)
    restored = store.get(job.job_id)
    assert restored.orchestration["missing_inputs"] == ["roughness_mm", "material"]
