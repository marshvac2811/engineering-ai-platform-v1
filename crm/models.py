from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

PIPELINE_STAGES = [
    ("budgetary", "Budgetary"),
    ("tendering", "Tendering"),
    ("quotation", "Quotation"),
    ("followup", "Follow-Up"),
    ("negotiation", "Negotiation"),
    ("won", "Closed — Won"),
    ("lost", "Closed — Lost"),
]
STAGE_KEYS = {k for k, _ in PIPELINE_STAGES}
CATEGORY_KEYS = {"Project Sales", "Retrofit Jobs", "Energy Optimization"}
STAKEHOLDERS = {"Consultant", "Builder", "Developer", "Contractor", "End Client", "Other"}


def _date(value: Any, label: str) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()[:10]
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{label} must be a date in YYYY-MM-DD form")
    return text


def _amount(value: Any, label: str) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number")
    if number < 0 or number != number:
        raise ValueError(f"{label} cannot be negative")
    return round(number, 2)


def normalize_delivery(raw: Any) -> Dict[str, Any]:
    """Validate and normalise the delivery / revision / final-submission / payment record of a deal."""
    if raw in (None, ""):
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("delivery must be an object")
    revisions, payments = raw.get("revisions") or [], raw.get("payments") or []
    if not isinstance(revisions, list) or not isinstance(payments, list):
        raise ValueError("revisions and payments must be lists")
    if len(revisions) > 50 or len(payments) > 100:
        raise ValueError("Too many revision or payment entries")
    out: Dict[str, Any] = {
        "delivered_on": _date(raw.get("delivered_on"), "Delivered on"),
        "final_submitted_on": _date(raw.get("final_submitted_on"), "Final submitted on"),
        "invoice_no": str(raw.get("invoice_no") or "").strip()[:60],
        "invoice_date": _date(raw.get("invoice_date"), "Invoice date"),
        "invoice_amount": _amount(raw.get("invoice_amount"), "Invoice amount"),
        "revisions": [], "payments": [],
    }
    for i, rev in enumerate(revisions, 1):
        if not isinstance(rev, dict):
            raise ValueError("Each revision must be an object")
        out["revisions"].append({"no": i, "date": _date(rev.get("date"), "Revision date"), "note": str(rev.get("note") or "").strip()[:500]})
    for pay in payments:
        if not isinstance(pay, dict):
            raise ValueError("Each payment must be an object")
        out["payments"].append({"date": _date(pay.get("date"), "Payment date"), "amount": _amount(pay.get("amount"), "Payment amount"), "ref": str(pay.get("ref") or "").strip()[:80]})
    paid = round(sum(p["amount"] for p in out["payments"]), 2)
    out["paid_total"] = paid
    out["outstanding"] = round(max(out["invoice_amount"] - paid, 0.0), 2)
    out["payment_status"] = ("not_invoiced" if out["invoice_amount"] <= 0 else "paid" if paid >= out["invoice_amount"] else "part_paid" if paid > 0 else "invoiced")
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CRMDeal:
    tenant_id: str
    name: str
    category: str = "Project Sales"
    stakeholder: str = "Other"
    contact: str = ""
    company: str = ""
    value: float = 0.0
    stage: str = "budgetary"
    next_follow_up: Optional[str] = None
    notes: str = ""
    engineering_job_id: Optional[str] = None
    hubspot_object_id: Optional[str] = None
    delivery: Dict[str, Any] = field(default_factory=dict)
    deal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def validate(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.name.strip():
            raise ValueError("deal name is required")
        if self.category not in CATEGORY_KEYS:
            raise ValueError(f"Unsupported deal category: {self.category}")
        if self.stakeholder not in STAKEHOLDERS:
            raise ValueError(f"Unsupported stakeholder: {self.stakeholder}")
        if self.stage not in STAGE_KEYS:
            raise ValueError(f"Unsupported pipeline stage: {self.stage}")
        if self.value < 0:
            raise ValueError("deal value cannot be negative")
        self.delivery = normalize_delivery(self.delivery)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
