"""Sample client answers for every form, used by the trial script and tests to prove each form can be completed."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intake_forms import all_forms
from intake_forms.answers import assemble
from jobs.service import JobService
from jobs.store import InMemoryJobStore
from orchestrator.intake import build_plan
from reports.service import ReportService
from reports.store import InMemoryReportStore

VALID = {"climate_zone": "composite", "building_type": "office", "material": "gss", "power_factor": "0.85", "voltage_v": "415",
         "load_factor_pct": "70", "efficiency_pct": "90", "space_type": "office", "hazard_class": "ordinary_1", "duct_type": "round",
         "leaving_db_c": "14", "leaving_rh_pct": "90", "entering_db_c": "35", "entering_rh_pct": "50", "max_temp_c": "80",
         "min_temp_c": "10", "fluid_temp_c": "7", "hot_water_c": "55", "cold_water_c": "25", "fill_pressure_bar_g": "1.5",
         "max_pressure_bar_g": "4"}


def sample(form: dict) -> dict:
    a = {}
    for x in form["fields"]:
        if not x.get("client", True):
            continue
        if x.get("structured"):
            a[x["key"]] = x["hint"].split("\n(")[0]
        elif x.get("choices"):
            a[x["key"]] = x["choices"][0]
        elif x["key"] in VALID:
            a[x["key"]] = VALID[x["key"]]
        elif x["type"] == "number":
            a[x["key"]] = "40"
        else:
            a[x["key"]] = "office"
    return a


def run_all() -> list[tuple[str, str]]:
    """Returns (skill_id, outcome) for every form that has a client form; outcome 'ok' or the reason."""
    out = []
    for f in all_forms():
        if not f.get("client_form", True):
            continue
        sk = f["skill_id"]
        svc = JobService(InMemoryJobStore(), tenant_id="t", report_service=ReportService(InMemoryReportStore(), tenant_id="t"))
        job = svc.create_from_plan(build_plan("Please help with this " + sk.replace("_", " "), requested_skill_id=sk))
        if job.status.value != "awaiting_information":
            out.append((sk, f"job started as {job.status.value}"))
            continue
        scalars, text, problems = assemble(sk, sample(f))
        if problems:
            out.append((sk, "; ".join(problems)))
            continue
        job = svc.provide_client_answers(job.job_id, scalars, text)
        out.append((sk, "ok" if job.status.value == "human_review" else f"{job.status.value}: {job.errors[:1]}"))
    return out
