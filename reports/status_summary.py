"""Platform status summary: one short, plain-text report for the owner (email + WhatsApp)."""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Tuple

_WAITING = {"human_review": "waiting for your review", "awaiting_information": "waiting for information from the client", "rework": "in rework", "failed": "FAILED"}


def _inr(n: Any) -> str:
    try:
        return "Rs " + format(int(round(float(n))), ",")
    except (TypeError, ValueError):
        return "Rs 0"


def build_status_summary(jobs: Iterable[Any], deals: Iterable[Any], *, requested_by: str = "", today: str | None = None) -> Tuple[str, str]:
    """Returns (full email text, short WhatsApp text)."""
    today = today or date.today().isoformat()
    jobs, deals = list(jobs), list(deals)
    by_status: dict = {}
    for j in jobs:
        s = str(getattr(getattr(j, "status", ""), "value", getattr(j, "status", "")))
        by_status.setdefault(s, []).append(j)
    done = len(by_status.get("dispatched", [])) + len(by_status.get("completed", []))
    attention = []
    for s, label in _WAITING.items():
        for j in by_status.get(s, []):
            ctx = getattr(j, "project_context", None) or {}
            name = ctx.get("project") or ctx.get("client") or getattr(j, "requested_skill_id", "") or "job"
            attention.append(f"- {name} ({getattr(j, 'serial_no', None) or str(j.job_id)[:8]}): {label}")
    due, unpaid, to_invoice, undelivered = [], [], [], []
    open_value = 0.0
    for d in deals:
        v = d.delivery or {}
        if d.stage not in ("won", "lost"):
            open_value += float(d.value or 0)
            if d.next_follow_up and d.next_follow_up <= today:
                due.append(f"- {d.name} ({d.company or '-'}): follow-up {d.next_follow_up}")
        if d.stage == "won" and not (v.get("delivered_on") or v.get("final_submitted_on")):
            undelivered.append(f"- {d.name} ({d.company or '-'})")
        if (v.get("delivered_on") or v.get("final_submitted_on")) and not float(v.get("invoice_amount") or 0):
            to_invoice.append(f"- {d.name} ({d.company or '-'})")
        if float(v.get("outstanding") or 0) > 0:
            unpaid.append(f"- {d.name} ({d.company or '-'}): {_inr(v.get('outstanding'))} outstanding")
    outstanding_total = sum(float((d.delivery or {}).get("outstanding") or 0) for d in deals)
    lines = [f"Mars Engineering Solutions - platform status, {today}", ""]
    lines += [f"Engineering jobs: {len(jobs)} in total, {done} delivered, {len(by_status.get('human_review', []))} waiting for your review, "
              f"{len(by_status.get('awaiting_information', []))} waiting for client information, {len(by_status.get('failed', []))} failed.",
              f"CRM: {len(deals)} deals, open pipeline value {_inr(open_value)}, payments outstanding {_inr(outstanding_total)}.", ""]
    for title, items in (("Needs your attention (jobs)", attention), ("Follow-ups due", due), ("Won, not delivered yet", undelivered),
                         ("Delivered, not invoiced", to_invoice), ("Payments outstanding", unpaid)):
        if items:
            lines += [title + ":"] + items[:15] + (["- and %d more" % (len(items) - 15)] if len(items) > 15 else []) + [""]
    if not (attention or due or undelivered or to_invoice or unpaid):
        lines += ["Nothing needs your attention right now.", ""]
    if requested_by:
        lines.append(f"Requested from the dashboard by: {requested_by}")
    full = "\n".join(lines).strip()
    short = (f"Mars status {today}: jobs {len(jobs)} ({done} delivered, {len(by_status.get('human_review', []))} to review, "
             f"{len(by_status.get('failed', []))} failed). Follow-ups due {len(due)}. Won not delivered {len(undelivered)}. "
             f"To invoice {len(to_invoice)}. Outstanding {_inr(outstanding_total)}. Full report is in your email.")
    return full, short[:1500]
