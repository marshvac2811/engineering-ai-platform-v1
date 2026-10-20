"""Automatically send the client information form when an enquiry matches a skill but lacks details.

Safety rules: never reply to no-reply or automated senders, never twice to the same sender in 24 hours,
never for a request that matched no skill, and a failed send never blocks the job. Messages from the
marketplaces (Upwork, Fiverr) cannot be answered by email, so the message and link are stored for the
owner to paste into the marketplace chat.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

from intake_forms import form_for, render_text
from intake_forms.answers import attach_form, form_url

_AUTOMATED = ("noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster", "notification", "bounce")
_MARKETPLACES = ("upwork.com", "fiverr.com")


def _addr(sender: str) -> str:
    return parseaddr(sender or "")[1].lower()


def classify_sender(sender: str) -> str:
    a = _addr(sender)
    if not a or "@" not in a:
        return "invalid"
    if any(t in a.split("@")[0] for t in _AUTOMATED):
        return "automated"
    if a.split("@")[1].endswith(_MARKETPLACES):
        return "marketplace"
    return "direct"


def _recent_to(service, address: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for j in service.list_jobs():
        cf = (j.project_context or {}).get("client_form") or {}
        if cf.get("sent_to") == address and cf.get("sent_at"):
            try:
                if datetime.fromisoformat(cf["sent_at"]) > cutoff:
                    return True
            except ValueError:
                pass
    return False


def form_message(job, skill_id: str, url: str) -> str:
    form = form_for(skill_id)
    who = parseaddr(str((job.project_context or {}).get("from") or ""))[0].strip()
    first = render_text(form, who).split("\n\nRequired:", 1)[0]
    return f"{first}\n\nPlease fill in the details here (it takes a few minutes): {url}\n\nRegards,\nMars Engineering Solutions"


def maybe_send_form(service, job, plan, *, gmail_client, tenant_id: str, subject: str = "") -> dict:
    """Returns a small result dict for the sync report. Never raises."""
    try:
        if os.getenv("AUTO_SEND_FORMS", "1").strip().lower() in {"0", "false", "no", "off"}:
            return {"form": "disabled"}
        skill_id = plan.selected_skill_id or (plan.work_items[0].skill_id if plan.work_items else None)
        if job.status.value != "awaiting_information" or not skill_id:
            return {"form": "not needed"}
        form = form_for(skill_id)
        if not form or not form.get("client_form", True):
            return {"form": "no client form for this skill"}
        sender = str((job.project_context or {}).get("reply_to") or (job.project_context or {}).get("from") or "")
        kind = classify_sender(sender)
        if kind in {"invalid", "automated"}:
            return {"form": f"skipped ({kind} sender)"}
        token = attach_form(job, skill_id)
        url = form_url(token)
        text = form_message(job, skill_id, url)
        cf = job.project_context["client_form"]
        cf.update({"url": url, "message": text, "channel": "marketplace" if kind == "marketplace" else "email"})
        if kind == "marketplace":
            service.store.save(job)
            return {"form": "ready to paste into the marketplace chat", "form_url": url}
        address = _addr(sender)
        if _recent_to(service, address):
            service.store.save(job)
            return {"form": "skipped (a form was sent to this sender in the last 24 hours)"}
        from integrations.providers.gmail import build_reply_message
        raw = build_reply_message(to=address, subject=subject or "Your enquiry", body_text=text,
                                  in_reply_to=(job.project_context or {}).get("message_id_header") or None)
        gmail_client.send_message(tenant_id, raw_b64url=raw, thread_id=(job.project_context or {}).get("thread_id"))
        cf.update({"sent_to": address, "sent_at": datetime.now(timezone.utc).isoformat()})
        job.add_event("client_form_sent", "Information form sent to the client by email.", to=address)
        service.store.save(job)
        return {"form": "sent", "form_url": url}
    except Exception as exc:  # noqa: BLE001 - never block the enquiry because the form could not be sent
        try:
            job.add_event("client_form_failed", f"Information form could not be sent: {type(exc).__name__}")
            service.store.save(job)
        except Exception:  # noqa: BLE001
            pass
        return {"form": f"failed ({type(exc).__name__})"}
