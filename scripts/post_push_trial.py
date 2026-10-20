"""Trial run after every push: sends the standard requests through the real pipeline and fails loudly.

Usage: python scripts/post_push_trial.py
Each case: request text -> routing -> job -> approval -> PDF + Excel. Checks the right skill was chosen,
the job reached review, and the documents contain no calculation-basis words.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jobs.service import JobService
from jobs.store import InMemoryJobStore
from orchestrator.intake import build_plan
from reports.artifacts import build_approved_pdf, build_evidence_xlsx
from reports.service import ReportService
from reports.store import InMemoryReportStore

CASES = [
    ("hvac_design_package", """HVAC design package, room by room load, airflow, duct sizing and equipment schedule for an office building in New Delhi.
Design conditions: outdoor 43 C DB / 23 C WB summer, indoor 24 C and 50% RH.
Rooms:
Reception, 60 sqm, 10 people
Open office, 250 sqm, 60 people
Server room, 30 sqm, 2 people
Select chiller or VRF with standby, chilled water pump head, duct sizes and AHU/FCU schedule."""),
    ("mep_building_package", """Generate MEP BOQ and layout for a 5 floor office building in Delhi.
Floor: Typical floor x5
Open office | 250 sqm | 60 people
Conference room | 40 sqm | 20 people
Pantry | 30 sqm | 10 people"""),
]
from trial_prompts import P as _PACK
_EXPECTED = ["hvac_design_package", "hvac_design_package", "preliminary_load_estimation", "cooling_coil_load", "ventilation_rate", "chiller_selection_advisor", "cooling_tower", "duct_sizing", "pump_head", "expansion_tank_sizing", "energy_payback", "vfd_energy_savings", "hvac_decarbonisation", "energy_optimisation_study", "retrofit_study", "transformer_sizing", "generator_sizing", "cable_voltage_drop", "vfd_derating", "harmonic_screening", "fire_water_storage", "sprinkler_demand", "fire_water_storage", "fire_water_storage", "sprinkler_demand", "domestic_water_tank_sizing", "plumbing_water_demand", "hot_water_heater_sizing", "rainwater_drainage", "domestic_water_tank_sizing", "bms_controller_sizing", "bms_alarm_evaluation", "bms_points_generation", "bms_cost_estimation", "bms_controller_sizing", "boq_takeoff", "boq_takeoff", "deviation_statement", "hvac_boq", "boq_takeoff", "mep_building_package", "mep_building_package", "mep_building_package", "mep_building_package", "mep_building_package", "cleanroom_ach", "vrf_sizing", "refrigerant_pipe_sizing", "facade_u_factor", "insulation_condensation"]
CASES += [(e, t) for e, t in zip(_EXPECTED, [t for ps in _PACK.values() for t in ps])]
LEAK = re.compile(r"recipe|unvalidated default|sqm_per|persons_per|starter norm|consumption per unit|rule.of.thumb|benchmark|wastage|diversity|cfm per|calculation step|how the result was calculated|ai_boundary|orchestrat|internal-governed|deterministic", re.I)


def run(expected: str, text: str) -> list[str]:
    problems = []
    plan = build_plan(text)
    got = [w.skill_id for w in plan.work_items]
    if got != [expected]:
        return [f"routed to {got}, expected [{expected}]"]
    if plan.status != "ready_for_execution":
        return [f"plan status {plan.status}, missing {plan.missing_inputs}"]
    svc = JobService(InMemoryJobStore(), tenant_id="t1", report_service=ReportService(InMemoryReportStore(), tenant_id="t1"))
    job = svc.create_from_plan(plan)
    if job.status.value != "human_review":
        return [f"job ended in {job.status.value}"]
    job = svc.approve(job.job_id, "trial", "ok")
    bundle = job.result["evidence_bundle"]
    pdf = build_approved_pdf(job=job, evidence_bundle=bundle)
    xlsx = build_evidence_xlsx(job=job, evidence_bundle=bundle)
    if len(pdf) < 5000 or len(xlsx) < 5000:
        problems.append("PDF or Excel is suspiciously small")
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx))
    for ws in wb:
        if ws.title in ("Workflow", "Request", "Result", "Tasks", "QA", "Governance", "Review"):
            problems.append(f"internal sheet {ws.title} is in the client workbook")
            continue
        for row in ws.iter_rows(values_only=True):
            t = " ".join(str(c) for c in row if c is not None)
            if LEAK.search(t):
                problems.append(f"calculation-basis wording in sheet {ws.title}: {t[:80]}")
                break
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf") as fh:
        fh.write(pdf); fh.flush()
        text = subprocess.run(["pdftotext", "-layout", fh.name, "-"], capture_output=True, text=True).stdout
    for line in text.splitlines():
        if LEAK.search(line):
            problems.append(f"calculation-basis wording in PDF: {line.strip()[:80]}")
            break
    return problems


def forms_check() -> int:
    from intake_forms import all_forms, render_text
    bad = 0
    forms = all_forms()
    for f in forms:
        body = render_text(f).split("Required:", 1)[1].split("Drawings,", 1)[0]
        if LEAK.search(body) or re.search(r"[a-z]+_[a-z]+|\?C", body):
            print("FAIL form", f["skill_id"]); bad += 1
    print(("PASS " if not bad and len(forms) >= 50 else "FAIL ") + f"client forms ({len(forms)})")
    return int(bool(bad) or len(forms) < 50)


def main() -> int:
    failed = forms_check()
    for expected, text in CASES:
        try:
            problems = run(expected, text)
        except Exception as exc:  # noqa: BLE001 - a trial must report any failure
            problems = [f"{type(exc).__name__}: {exc}"]
        print(("PASS " if not problems else "FAIL ") + expected)
        for p in problems:
            print("   -", p)
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
