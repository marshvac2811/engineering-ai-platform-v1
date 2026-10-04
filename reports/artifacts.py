"""Final engineering artifact generation: controlled PDF and evidence workbook.

The PDF is the only client-facing dispatch artifact. The workbook is an
internal evidence/support artifact. Both are generated from the same governed
engineering evidence bundle.
"""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

from reports.formatting import (
    describe_item, flatten_rows, format_value, humanize, split_inputs_and_results, split_unit, trace_steps,
)


DEFAULT_WATERMARK = "ENGINEERING AI PLATFORM • APPROVED CONTROLLED DOCUMENT"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)


def _pdf_watermark(canvas, doc, watermark: str) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.Color(0.45, 0.45, 0.45, alpha=0.16))
    canvas.setFont("Helvetica-Bold", 22)
    canvas.translate(width / 2, height / 2)
    canvas.rotate(32)
    canvas.drawCentredString(0, 0, watermark)
    canvas.restoreState()

    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(15 * mm, 9 * mm, "Controlled engineering record • Human approval required for validity")
    canvas.drawRightString(width - 15 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


_ACCENT = colors.HexColor("#1f3a5f")
_STRIPE = colors.HexColor("#f2f5f9")
_APPROVED = {"approved", "dispatching", "dispatched", "completed"}


def _fmt_dt(value: Any) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return str(value)


def _approval(bundle: Dict[str, Any]) -> Dict[str, str]:
    for event in reversed((bundle.get("review") or {}).get("events") or []):
        if str(event.get("status")) == "approved":
            meta = event.get("metadata") or {}
            return {"by": str(meta.get("reviewer") or "-"), "comment": str(meta.get("comment") or "-"),
                    "at": _fmt_dt(event.get("created_at"))}
    return {"by": "-", "comment": "-", "at": "-"}


def _task_inputs(task: Dict[str, Any], request_inputs: Dict[str, Any]) -> Dict[str, Any]:
    inputs = task.get("inputs") or {}
    return inputs if inputs else (request_inputs or {})


def _results_rows(task: Dict[str, Any], request_inputs: Dict[str, Any]):
    inputs, results = split_inputs_and_results(_task_inputs(task, request_inputs), task.get("engineering_result") or {})
    return flatten_rows(inputs), flatten_rows(results)


def _has_money(rows) -> bool:
    return any(w in label.lower() for label, _v, _u in rows for w in ("cost", "tariff", "saving", "invest", "payback"))


def _compliance_rows(tasks) -> list:
    rows = []
    for t in tasks:
        for c in t.get("compliance") or []:
            if isinstance(c, dict):
                rows.append(c)
    return rows


def build_approved_pdf(*, job, evidence_bundle: Dict[str, Any], watermark: str = DEFAULT_WATERMARK) -> bytes:
    if str(job.status.value) not in _APPROVED:
        raise ValueError("Approved PDF can only be generated after human approval")

    out = io.BytesIO()
    base = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=base["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("Small", parent=base["BodyText"], fontSize=8, leading=10)
    cell = ParagraphStyle("Cell", parent=base["BodyText"], fontSize=8.5, leading=11)
    cell_b = ParagraphStyle("CellB", parent=cell, fontName="Helvetica-Bold")
    head_cell = ParagraphStyle("HeadCell", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
    num = ParagraphStyle("Num", parent=cell, alignment=2)
    h1 = ParagraphStyle("H1", parent=base["Title"], textColor=_ACCENT, fontSize=22, spaceAfter=2)
    sub = ParagraphStyle("Sub", parent=base["Heading3"], textColor=colors.HexColor("#2e7d32"), spaceAfter=6)
    section = ParagraphStyle("Section", parent=base["Heading2"], textColor=_ACCENT, spaceBefore=12, spaceAfter=5)
    task_h = ParagraphStyle("TaskH", parent=base["Heading3"], textColor=_ACCENT, spaceBefore=8, spaceAfter=3)
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=10, bulletIndent=0)

    doc = SimpleDocTemplate(
        out, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"Engineering Report - {job.job_id}", author="Engineering AI Platform",
    )
    manifest = evidence_bundle.get("manifest", {})
    request = evidence_bundle.get("request", {})
    tasks = evidence_bundle.get("tasks", []) or []
    governance = evidence_bundle.get("governance", {}) or {}
    orch = request.get("orchestration") or {}
    request_inputs = request.get("inputs") or {}
    approval = _approval(evidence_bundle)
    width = 180 * mm

    def P(text, style=cell):
        return Paragraph(str(text if text not in (None, "") else "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)

    def table(header, rows, widths, numeric_cols=()):
        data = [[Paragraph(h, head_cell) for h in header]]
        for r in rows:
            data.append([P(v, num if i in numeric_cols else cell) for i, v in enumerate(r)])
        t = Table(data, colWidths=widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c2cf")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), _STRIPE))
        t.setStyle(TableStyle(style))
        return t

    def kv_table(rows):
        t = Table([[P(k, cell_b), P(v)] for k, v in rows], colWidths=[48 * mm, width - 48 * mm])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c2cf")),
            ("BACKGROUND", (0, 0), (0, -1), _STRIPE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    story = [Paragraph("Engineering Report", h1), Paragraph("Approved for controlled dispatch", sub)]
    capabilities = ", ".join(humanize(t.get("capability_id")) for t in tasks if t.get("capability_id")) or humanize(job.requested_skill_id or job.skill_id)
    project_context = getattr(job, "project_context", None) or {}
    header_rows = []
    if project_context.get("project"):
        header_rows.append(("Project", project_context.get("project")))
    if project_context.get("client"):
        header_rows.append(("Client", project_context.get("client")))
    header_rows += [
        ("Report ID", job.report_id),
        ("Scope of work", capabilities),
        ("Request", orch.get("normalized_request") or (tasks[0].get("objective") if tasks else None)),
        ("Approved by", f"{approval['by']} on {approval['at']}"),
        ("Report date", _fmt_dt(datetime.now(timezone.utc).isoformat())),
        ("Report revision", str((getattr(job, "result", {}) or {}).get("report_revision") or (getattr(job, "orchestration", {}) or {}).get("report_revision") or 1)),
        ("Skill version", ", ".join(str(t.get("skill_version") or "-") for t in tasks) or "-"),
        ("Source revision", ", ".join(str(t.get("source_revision") or "-") for t in tasks) or "-"),
    ]
    story.append(kv_table(header_rows))

    # 1. Inputs
    story.append(Paragraph("1. Inputs Used", section))
    shown_inputs = False
    for index, task in enumerate(tasks, 1):
        in_rows, _ = _results_rows(task, request_inputs)
        if not in_rows:
            continue
        shown_inputs = True
        if len(tasks) > 1:
            story.append(Paragraph(f"Task {index}: {P(humanize(task.get('capability_id')), body).text}", task_h))
        story.append(table(["Parameter", "Value", "Unit"], [(l, format_value(v), u) for l, v, u in in_rows],
                           [90 * mm, 50 * mm, 40 * mm], numeric_cols=(1,)))
        story.append(Spacer(1, 4))
    if not shown_inputs:
        story.append(Paragraph("No numeric inputs were recorded for this report.", body))
    docs = manifest.get("source_evidence") or []
    if docs:
        story.append(Paragraph("Source documents supplied", task_h))
        story.append(table(["File", "Type", "Extraction"], [(d.get("filename"), d.get("mime_type"), humanize(d.get("extraction_status"))) for d in docs],
                           [90 * mm, 50 * mm, 40 * mm]))

    # 2. Results
    story.append(Paragraph("2. Results", section))
    money_note = False
    for index, task in enumerate(tasks, 1):
        _, res_rows = _results_rows(task, request_inputs)
        title = task.get("objective") or humanize(task.get("capability_id"))
        block = [Paragraph(f"Task {index}: {P(title, body).text}", task_h),
                 Paragraph(f"Method: {P(humanize(task.get('capability_id')), small).text} &nbsp;|&nbsp; Status: {P(humanize(task.get('status')), small).text}", small),
                 Spacer(1, 3)]
        story.append(KeepTogether(block))
        if res_rows:
            story.append(table(["Result", "Value", "Unit"], [(l, format_value(v), u) for l, v, u in res_rows],
                               [90 * mm, 50 * mm, 40 * mm], numeric_cols=(1,)))
            money_note = money_note or _has_money(res_rows)
        else:
            story.append(Paragraph("No numeric results were produced for this task.", body))
        steps = trace_steps(task.get("calculation_trace") or [])
        if steps:
            story.append(Paragraph("How the result was calculated", task_h))
            story.append(table(["Step", "Calculation step", "Detail"], [(x["step"], x["operation"], x["detail"]) for x in steps],
                               [15 * mm, 100 * mm, 65 * mm]))
        assumptions = task.get("assumptions") or []
        if assumptions:
            story.append(Paragraph("Assumptions", task_h))
            story.extend(Paragraph(describe_item(a).replace("&", "&amp;").replace("<", "&lt;"), bullet, bulletText="•") for a in assumptions)
        warnings = task.get("warnings") or []
        if warnings:
            story.append(Paragraph("Points to note", task_h))
            story.extend(Paragraph(describe_item(w).replace("&", "&amp;").replace("<", "&lt;"), bullet, bulletText="•") for w in warnings)
        story.append(Spacer(1, 6))
    if money_note:
        story.append(Paragraph("Monetary values are in the currency of the tariff or cost figures supplied in the inputs.", small))

    # 3. Standards and compliance
    story.append(Paragraph("3. Standards and Compliance", section))
    limitations = []
    for t in tasks:
        for item in t.get("limitations") or []:
            text = str(item)
            if text and text not in limitations:
                limitations.append(text)
    if limitations:
        story.append(Paragraph("Limitations", task_h))
        story.extend(Paragraph(str(x).replace("&", "&amp;").replace("<", "&lt;"), bullet, bulletText="•") for x in limitations)


    checks = _compliance_rows(tasks)
    if checks:
        story.append(table(["Authority", "Code / edition", "Clause", "Requirement", "Project value", "Status"],
                           [(c.get("authority"), f"{c.get('code') or c.get('code_name') or ''} {c.get('edition') or ''}".strip(), c.get("clause"),
                             c.get("requirement"), format_value(c.get("project_value")), humanize(c.get("status"))) for c in checks],
                           [25 * mm, 32 * mm, 20 * mm, 43 * mm, 30 * mm, 30 * mm]))
    else:
        allowed = (governance.get("applicability") or {}).get("compliance_claim_allowed")
        story.append(Paragraph(
            "This report presents engineering calculation results only. No compliance claim is made, because verified "
            "standards evidence and project applicability have not been established." if not allowed else
            "Compliance claims are supported by the verified evidence recorded in the evidence workbook.", body))
        cands = governance.get("candidate_sources") or []
        if cands:
            story.append(Paragraph("Reference standards that may apply (not yet verified for this project)", task_h))
            story.append(table(["Standard", "Authority", "Edition"], [(c.get("title"), c.get("authority"), c.get("edition") or "-") for c in cands],
                               [100 * mm, 40 * mm, 40 * mm]))

    # 4. Review
    story.append(Paragraph("4. Review and Approval", section))
    story.append(kv_table([("Human review", "Required, completed"), ("Approved by", approval["by"]),
                           ("Approval date", approval["at"]), ("Reviewer comment", approval["comment"])]))

    # Appendix
    story.append(Paragraph("Appendix: Traceability", section))
    story.append(Paragraph("These identifiers allow the report to be matched to the stored engineering evidence record.", small))
    story.append(Spacer(1, 3))
    story.append(kv_table([
        ("Job ID", job.job_id), ("Report ID", job.report_id),
        ("Evidence record SHA-256", manifest.get("bundle_sha256")), ("Inputs SHA-256", manifest.get("input_hash")),
        ("Evidence schema", manifest.get("schema_version")),
    ]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("This document is generated from the platform evidence record, which is authoritative for traceability. "
                           "Human approval is required for validity.", small))

    doc.build(story,
              onFirstPage=lambda c, d: _pdf_watermark(c, d, watermark),
              onLaterPages=lambda c, d: _pdf_watermark(c, d, watermark))
    return out.getvalue()


def build_evidence_xlsx(*, job, evidence_bundle: Dict[str, Any]) -> bytes:
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    header_fill = PatternFill("solid", fgColor="1F3A5F")
    header_font = Font(bold=True, color="FFFFFF")
    wrap = Alignment(wrap_text=True, vertical="top")
    manifest = evidence_bundle.get("manifest", {})
    request = evidence_bundle.get("request", {})
    tasks = evidence_bundle.get("tasks", []) or []
    governance = evidence_bundle.get("governance", {}) or {}
    request_inputs = request.get("inputs") or {}
    approval = _approval(evidence_bundle)

    def styled(sheet, header, rows, widths, number_cols=()):
        sheet.append(header)
        for c in sheet[1]:
            c.fill, c.font, c.alignment = header_fill, header_font, wrap
        for r in rows:
            sheet.append(list(r))
        for i, w in enumerate(widths):
            sheet.column_dimensions[chr(65 + i)].width = w
        for row in sheet.iter_rows(min_row=2):
            for c in row:
                c.alignment = wrap
                if c.column - 1 in number_cols and isinstance(c.value, (int, float)):
                    c.number_format = "#,##0.###"
        sheet.freeze_panes = "A2"

    # Summary (also keeps the legacy "Cover" fields)
    ws = wb.active
    ws.title = "Summary"
    project_context = getattr(job, "project_context", None) or {}
    summary_rows = []
    if project_context.get("project"):
        summary_rows.append(("Project", project_context.get("project")))
    if project_context.get("client"):
        summary_rows.append(("Client", project_context.get("client")))
    summary_rows += [
        ("Job ID", job.job_id), ("Report ID", job.report_id), ("Status", humanize(job.status.value)),
        ("Scope of work", ", ".join(humanize(t.get("capability_id")) for t in tasks if t.get("capability_id")) or humanize(job.requested_skill_id or job.skill_id)),
        ("Request", (request.get("orchestration") or {}).get("normalized_request")),
        ("Approved by", approval["by"]), ("Approval date", approval["at"]),
        ("Evidence record SHA-256", manifest.get("bundle_sha256")), ("Evidence schema", manifest.get("schema_version")),
        ("Skill version", ", ".join(str(t.get("skill_version") or "-") for t in tasks) or "-"),
        ("Source revision", ", ".join(str(t.get("source_revision") or "-") for t in tasks) or "-"),
        ("Limitations", "; ".join(str(x) for t in tasks for x in (t.get("limitations") or [])) or "-"),
        ("Generated", _fmt_dt(datetime.now(timezone.utc).isoformat())),
    ]
    styled(ws, ["Item", "Detail"], summary_rows, [30, 100])

    inputs_rows, results_rows, step_rows, note_rows, check_rows = [], [], [], [], []
    for index, t in enumerate(tasks, 1):
        label = f"Task {index}: {humanize(t.get('capability_id'))}"
        in_rows, res_rows = _results_rows(t, request_inputs)
        inputs_rows += [(label, l, v, u) for l, v, u in in_rows]
        results_rows += [(label, l, v, u) for l, v, u in res_rows]
        step_rows += [(label, x["step"], x["operation"], x["detail"]) for x in trace_steps(t.get("calculation_trace") or [])]
        note_rows += [(label, "Assumption", describe_item(a)) for a in t.get("assumptions") or []]
        note_rows += [(label, "Point to note", describe_item(w)) for w in t.get("warnings") or []]
        for c in t.get("compliance") or []:
            if isinstance(c, dict):
                check_rows.append((label, c.get("authority"), f"{c.get('code') or c.get('code_name') or ''} {c.get('edition') or ''}".strip(),
                                   c.get("clause"), c.get("requirement"), c.get("project_value"), c.get("required_value"), humanize(c.get("status"))))

    styled(wb.create_sheet("Inputs"), ["Task", "Parameter", "Value", "Unit"], inputs_rows, [30, 40, 18, 16], number_cols=(2,))
    styled(wb.create_sheet("Results"), ["Task", "Result", "Value", "Unit"], results_rows, [30, 40, 18, 16], number_cols=(2,))
    styled(wb.create_sheet("Calculation Steps"), ["Task", "Step", "Calculation step", "Detail"], step_rows, [30, 8, 50, 40])
    styled(wb.create_sheet("Assumptions & Notes"), ["Task", "Type", "Detail"], note_rows, [30, 16, 100])
    cands = [(c.get("title"), c.get("authority"), c.get("edition") or "-", "Candidate - not verified") for c in governance.get("candidate_sources") or []]
    if check_rows:
        styled(wb.create_sheet("Compliance"), ["Task", "Authority", "Code / edition", "Clause", "Requirement", "Project value", "Required value", "Status"],
               check_rows, [30, 16, 24, 14, 40, 16, 16, 18])
    else:
        styled(wb.create_sheet("Compliance"), ["Standard", "Authority", "Edition", "Status"], cands or [("No compliance claim made", "", "", "")], [50, 20, 14, 28])

    sources = manifest.get("source_evidence", []) or []
    styled(wb.create_sheet("Source Evidence"), ["Type", "Attachment ID", "Filename", "MIME", "SHA-256", "Extraction Status", "Warnings"],
           [(s.get("type"), s.get("attachment_id"), s.get("filename"), s.get("mime_type"), s.get("sha256"), s.get("extraction_status"), _text(s.get("extraction_warnings"))) for s in sources],
           [14, 30, 36, 24, 66, 18, 40])

    # Technical records kept for audit (raw form).
    def add_json_sheet(title: str, payload: Any):
        sh = wb.create_sheet(title)
        if isinstance(payload, dict):
            sh.append(["Field", "Value"])
            for k, v in payload.items():
                sh.append([str(k), _text(v)])
        elif isinstance(payload, list):
            sh.append(["Index", "Value"])
            for i, v in enumerate(payload, 1):
                sh.append([i, _text(v)])
        else:
            sh.append(["Value", _text(payload)])
        sh.column_dimensions["A"].width = 28
        sh.column_dimensions["B"].width = 100
        return sh

    add_json_sheet("Manifest", manifest)
    add_json_sheet("Request", request)
    add_json_sheet("Workflow", evidence_bundle.get("workflow", {}))
    add_json_sheet("Result", evidence_bundle.get("result", {}))
    add_json_sheet("QA", evidence_bundle.get("qa", {}))
    add_json_sheet("Governance", governance)
    add_json_sheet("Review", evidence_bundle.get("review", {}))

    sh = wb.create_sheet("Tasks")
    sh.append(["Task ID", "Capability", "Status", "Objective", "Inputs", "Engineering Result", "Calculation Trace", "Assumptions", "Warnings", "Compliance"])
    for t in tasks:
        sh.append([t.get("task_id"), t.get("capability_id"), t.get("status"), t.get("objective"), _text(t.get("inputs")), _text(t.get("engineering_result")),
                   _text(t.get("calculation_trace")), _text(t.get("assumptions")), _text(t.get("warnings")), _text(t.get("compliance"))])
    for col in range(1, 11):
        sh.column_dimensions[chr(64 + col)].width = 24

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
