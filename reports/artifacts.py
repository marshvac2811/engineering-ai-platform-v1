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


def build_approved_pdf(*, job, evidence_bundle: Dict[str, Any], watermark: str = DEFAULT_WATERMARK) -> bytes:
    if str(job.status.value) not in {"approved", "dispatching", "dispatched", "completed"}:
        raise ValueError("Approved PDF can only be generated after human approval")

    out = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], spaceBefore=10, spaceAfter=5))
    doc = SimpleDocTemplate(
        out, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"Engineering Report — {job.job_id}",
        author="Engineering AI Platform",
    )
    story = []
    manifest = evidence_bundle.get("manifest", {})
    request = evidence_bundle.get("request", {})
    tasks = evidence_bundle.get("tasks", [])
    result = evidence_bundle.get("result", {})

    story.append(Paragraph("Engineering Report", styles["Title"]))
    story.append(Paragraph("APPROVED FOR CONTROLLED DISPATCH", styles["Heading2"]))
    story.append(Spacer(1, 5))
    story.append(Table([
        ["Job ID", _text(job.job_id)],
        ["Report ID", _text(job.report_id)],
        ["Status", _text(job.status.value)],
        ["Requested capability", _text(job.requested_skill_id or job.skill_id)],
        ["Evidence schema", _text(manifest.get("schema_version"))],
        ["Evidence SHA-256", _text(manifest.get("bundle_sha256"))],
        ["Generated", datetime.now(timezone.utc).isoformat()],
    ], colWidths=[42 * mm, 135 * mm], style=TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ])))

    story.append(Paragraph("1. Engineering Request", styles["Section"]))
    story.append(Paragraph(_text(request.get("source")), styles["Small"]))
    story.append(Paragraph(_text(request.get("inputs")), styles["Small"]))
    story.append(Paragraph(_text(request.get("project_context")), styles["Small"]))

    story.append(Paragraph("2. Engineering Tasks and Results", styles["Section"]))
    for index, task in enumerate(tasks, 1):
        story.append(KeepTogether([
            Paragraph(f"Task {index}: {_text(task.get('objective') or task.get('capability_id'))}", styles["Heading3"]),
            Paragraph(f"Capability: {_text(task.get('capability_id'))} | Status: {_text(task.get('status'))}", styles["Small"]),
            Paragraph("Engineering result: " + _text(task.get("engineering_result")), styles["Small"]),
            Paragraph("Calculation trace: " + _text(task.get("calculation_trace")), styles["Small"]),
            Paragraph("Assumptions: " + _text(task.get("assumptions")), styles["Small"]),
            Paragraph("Warnings: " + _text(task.get("warnings")), styles["Small"]),
            Paragraph("Compliance: " + _text(task.get("compliance")), styles["Small"]),
        ]))
        story.append(Spacer(1, 4))

    story.append(Paragraph("3. Consolidated Result", styles["Section"]))
    story.append(Paragraph(_text(result), styles["Small"]))

    story.append(Paragraph("4. Evidence and Governance", styles["Section"]))
    story.append(Paragraph("Source evidence: " + _text(manifest.get("source_evidence")), styles["Small"]))
    story.append(Paragraph("Input hash: " + _text(manifest.get("input_hash")), styles["Small"]))
    story.append(Paragraph("Project-context hash: " + _text(manifest.get("project_context_hash")), styles["Small"]))
    story.append(Paragraph("Standards-context hash: " + _text(manifest.get("standards_context_hash")), styles["Small"]))
    story.append(Paragraph("Assumptions-context hash: " + _text(manifest.get("assumptions_context_hash")), styles["Small"]))
    story.append(Paragraph("This document is generated from the platform evidence record. The evidence record is authoritative for traceability.", styles["Small"]))

    doc.build(
        story,
        onFirstPage=lambda c, d: _pdf_watermark(c, d, watermark),
        onLaterPages=lambda c, d: _pdf_watermark(c, d, watermark),
    )
    return out.getvalue()


def build_evidence_xlsx(*, job, evidence_bundle: Dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cover"
    rows = [
        ("Job ID", job.job_id),
        ("Report ID", job.report_id),
        ("Status", job.status.value),
        ("Requested capability", job.requested_skill_id or job.skill_id),
        ("Evidence schema", evidence_bundle.get("manifest", {}).get("schema_version")),
        ("Evidence SHA-256", evidence_bundle.get("manifest", {}).get("bundle_sha256")),
        ("Generated", datetime.now(timezone.utc).isoformat()),
    ]
    for row in rows:
        ws.append(row)
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 90

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

    add_json_sheet("Manifest", evidence_bundle.get("manifest", {}))
    add_json_sheet("Request", evidence_bundle.get("request", {}))
    add_json_sheet("Workflow", evidence_bundle.get("workflow", {}))
    add_json_sheet("Result", evidence_bundle.get("result", {}))
    add_json_sheet("QA", evidence_bundle.get("qa", {}))
    add_json_sheet("Governance", evidence_bundle.get("governance", {}))
    add_json_sheet("Review", evidence_bundle.get("review", {}))

    tasks = evidence_bundle.get("tasks", [])
    sh = wb.create_sheet("Tasks")
    sh.append(["Task ID", "Capability", "Status", "Objective", "Inputs", "Engineering Result", "Calculation Trace", "Assumptions", "Warnings", "Compliance"])
    for t in tasks:
        sh.append([
            t.get("task_id"), t.get("capability_id"), t.get("status"), t.get("objective"),
            _text(t.get("inputs")), _text(t.get("engineering_result")),
            _text(t.get("calculation_trace")), _text(t.get("assumptions")),
            _text(t.get("warnings")), _text(t.get("compliance")),
        ])
    for col in range(1, 11):
        sh.column_dimensions[chr(64 + col)].width = 24

    sources = evidence_bundle.get("manifest", {}).get("source_evidence", [])
    sh = wb.create_sheet("Source Evidence")
    sh.append(["Type", "Attachment ID", "Filename", "MIME", "SHA-256", "Extraction Status", "Warnings"])
    for s in sources:
        sh.append([s.get("type"), s.get("attachment_id"), s.get("filename"), s.get("mime_type"), s.get("sha256"), s.get("extraction_status"), _text(s.get("extraction_warnings"))])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
