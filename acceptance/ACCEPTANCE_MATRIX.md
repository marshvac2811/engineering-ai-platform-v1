# Engineering AI Platform V1 — 42-Trial Acceptance Matrix

Acceptance scope: 23 registered engineering skill IDs; 22 currently integrated/executable; 1 source-audit-pending (chiller_efficiency).

Release rule: every accepted trial must prove the governed lifecycle: natural-language intake → skill selection → missing-input handling → validation → deterministic execution → engineering result → evidence → human review → approval → controlled artifact generation → SHA-256 integrity → register/history → dispatch where approved.

## Mandatory gates for every engineering trial
1. Correct skill selected and recorded.
2. Required inputs identified; missing inputs are requested rather than guessed.
3. Invalid or unsupported inputs are rejected or governed.
4. Calculation is deterministic and traceable.
5. Result includes units, assumptions and applicable limitations.
6. Skill version and source revision are preserved.
7. Human review is required before dispatch.
8. Evidence bundle is created with SHA-256 integrity.
9. Approved output produces watermarked PDF and Excel evidence where applicable.
10. Report register, Evidence Register and Revision History remain consistent.
11. No unauthorized dispatch occurs.
12. Rework preserves the prior report and creates explicit revision lineage.

## Baseline skill trials — 23

| ID | Skill | Trial objective | Minimum evidence | Status |
|---|---|---|---|---|
| AT-01 | preliminary_load_estimation | Preliminary HVAC load request through governed calculation | Job, assumptions, load result, evidence, artifacts | PLANNED |
| AT-02 | duct_sizing | Size duct from airflow and design inputs | Dimensions, velocity/pressure basis, evidence, artifacts | PLANNED |
| AT-03 | pump_head | Calculate pump head from flow/system inputs | TDH components, units, evidence, artifacts | PLANNED |
| AT-04 | hvac_fault_diagnosis | Diagnose HVAC symptoms within diagnostic-support boundary | Findings, reasoning, limitations, review evidence | PLANNED |
| AT-05 | cooling_tower | Preliminary cooling-tower estimate with vendor boundary | Result, assumptions, vendor-verification limitation | PLANNED |
| AT-06 | refrigerant_pipe_sizing | Preliminary refrigerant piping selection | Pipe result, assumptions, manufacturer limitation | PLANNED |
| AT-07 | vrf_sizing | Preliminary VRF sizing with manufacturer boundary | Result basis, limitations, evidence | PLANNED |
| AT-08 | cleanroom_ach | Calculate/check cleanroom ACH | ACH result, room inputs, compliance-support limitation | PLANNED |
| AT-09 | duct_leakage | Duct leakage compliance-support calculation/check | Leakage result, standard basis, evidence | PLANNED |
| AT-10 | chiller_selection_advisor | Advisory chiller selection | Options/basis, assumptions, advisory limitation | PLANNED |
| AT-11 | chiller_efficiency | Source-audit-pending efficiency calculation/trial | Source audit, calculation trace, explicit release gate | BLOCKED UNTIL SOURCE AUDIT |
| AT-12 | bms_points_generation | Generate BMS points from system scope | Point list, tags, evidence/export | PLANNED |
| AT-13 | bms_controller_sizing | Preliminary BMS controller sizing | I/O basis, recommendation, assumptions | PLANNED |
| AT-14 | bms_cost_estimation | Budgetary BMS cost estimate | Itemized cost basis, assumptions, evidence | PLANNED |
| AT-15 | bms_alarm_evaluation | Evaluate BMS alarms | Findings, severity/basis, limitations | PLANNED |
| AT-16 | vfd_energy_savings | Estimate VFD energy savings | Baseline/optimized values, savings, assumptions | PLANNED |
| AT-17 | vfd_derating | Manufacturer-dependent VFD derating check | Derating result, conditions, limitation | PLANNED |
| AT-18 | harmonic_screening | Harmonic screening only | Screening result, inputs, limitation | PLANNED |
| AT-19 | hvac_decarbonisation | HVAC decarbonisation scenario model | Baseline/scenarios, impact, assumptions/evidence | PLANNED |
| AT-20 | energy_payback | Energy retrofit payback estimate | Investment/savings/payback, limitation | PLANNED |
| AT-21 | hvac_boq | Commercial HVAC BOQ | Itemized BOQ, quantities/basis, evidence | PLANNED |
| AT-22 | deviation_statement | Governed commercial deviation statement | Deviation basis, traceability, review evidence | PLANNED |
| AT-23 | facade_u_factor | Preliminary facade U-factor / ECBC-supported calculation | Area-weighted result, ECBC basis, limitations, artifacts | PLANNED |

## Additional cross-skill and governance trials — 19

| ID | Trial | What it proves | Minimum evidence | Status |
|---|---|---|---|---|
| AT-24 | Missing required input | Platform asks only for genuinely missing information | Awaiting-information state and targeted question | PLANNED |
| AT-25 | Invalid input | Invalid value/unit is rejected without unsafe calculation | Validation error and preserved job trace | PLANNED |
| AT-26 | Ambiguous request | Natural-language ambiguity is resolved before execution | Clarification or governed interpretation | PLANNED |
| AT-27 | Conditional input | Skill asks for an input only when required by method | Conditional information path and trace | PLANNED |
| AT-28 | Multi-input engineering request | One request follows a governed multi-step plan | Plan, task outputs, consolidated evidence | PLANNED |
| AT-29 | Evidence integrity | Input/evidence/artifact SHA-256 values remain consistent | Hashes in evidence bundle/register | PLANNED |
| AT-30 | Human review gate | Result cannot dispatch before approval | Blocked dispatch plus review state | PLANNED |
| AT-31 | Approve and dispatch | Approved result generates controlled dispatch artifacts | Approval, watermarked PDF, Excel, dispatch record | PLANNED |
| AT-32 | Rework before dispatch | Reviewer can request controlled rework | Rework event, resubmission, preserved state | PLANNED |
| AT-33 | Rework after approval | Approved-but-undispatched report can be revised safely | Approval invalidation, parent revision, new revision | PLANNED |
| AT-34 | Revision lineage | Revised report supersedes prior revision without mutation | V1/V2 lineage in report/evidence/register | PLANNED |
| AT-35 | Evidence Register | Evidence tab exposes integrity artifacts accurately | Register rows match artifacts | PLANNED |
| AT-36 | Revision History Register | Revision tab exposes lineage/status accurately | History rows match report lineage | PLANNED |
| AT-37 | PDF/Excel parity | Controlled PDF and Excel carry consistent metadata | Matching result/version/source/limitations | PLANNED |
| AT-38 | Unsupported/compliance boundary | Platform does not imply certification where unsupported | Explicit limitation and no false claim | PLANNED |
| AT-39 | Skill metadata traceability | Version/source revision survives all layers | Matching metadata execution→evidence→report | PLANNED |
| AT-40 | Attachment/data ingestion | Uploaded engineering evidence reaches intended job safely | Input hash, ingestion record, calculation trace | PLANNED |
| AT-41 | End-to-end external intake | External normalized request follows governed lifecycle | Ingress→job→calculation→review→evidence | PLANNED |
| AT-42 | Full release-gate regression | Representative approved job proves lifecycle integrity | Complete evidence package, zero unexplained failures | PLANNED |

## Release gates

### Gate A — Registry integrity
- 23 skill IDs are accounted for.
- 22 are integrated/executable.
- chiller_efficiency is explicitly isolated as source-audit pending.
- Duplicate skill IDs must not silently change the acceptance count.

### Gate B — Engineering execution
- AT-01 through AT-23 are executed.
- Every executable skill has at least one successful full-lifecycle trial.
- Unsupported calculations are not accepted merely because they return a number.

### Gate C — Governance
- AT-24 through AT-40 pass.
- Missing, invalid and ambiguous input handling is demonstrated.
- Review, approval, rework and revision lineage are demonstrated.
- Evidence, hashes, PDF/Excel and registers agree.

### Gate D — External workflow
- AT-41 passes with a real or approved normalized external event.
- Provider credentials remain outside source control.

### Gate E — Final regression
- AT-42 passes.
- No unexplained failure remains.
- All accepted trials have durable evidence.
- All approved trials have controlled artifacts.
- No unauthorized dispatch exists.

## Final acceptance rule

Release candidate status is ACCEPTED only when all applicable gates pass and every exception is explicitly documented.

A blocked provider integration does not invalidate the engineering core, but it must remain visibly blocked rather than represented as passed.

chiller_efficiency cannot be represented as a released engineering capability until its source audit is complete and its acceptance trial passes.

## Trial record fields

Each executed trial should capture: Trial ID; date/time; environment; job ID; project/client; natural-language request; selected skill; skill version; source revision; input/evidence references; missing-input questions; final inputs; result; assumptions; limitations; reviewer; approval timestamp; rework/revision information; evidence SHA-256; PDF SHA-256; Excel SHA-256; dispatch status; final PASS/FAIL/BLOCKED/WAIVED decision; exception notes; evidence/report references.

## Scope correction

The current registry contains 23 skill IDs. The correct operational statement is 22 integrated/executable plus 1 source-audit-pending.