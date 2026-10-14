"""Automatic CRM linkage: engineering jobs create and update CRM deals without manual entry.

  * job created   -> find or create a deal for that client + project (stage Budgetary, follow-up in 3 days) and link the job
  * rework asked  -> add a numbered revision (with the reviewer's comment) to the deal's delivery record
  * dispatched    -> record the delivery date (first dispatch) and the final submission date (latest dispatch)

Payments are never inferred: only a person can confirm money received. CRM failures must never break an engineering job,
so the service calls this through a guard that swallows errors.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from email.utils import parseaddr
from typing import Any, Dict, Optional

from .models import CRMDeal

FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com", "icloud.com", "proton.me", "protonmail.com"}
NOISE = {"upwork.com", "fiverr.com", "linkedin.com", "google.com"}
_PREFIX = re.compile(r"^\s*((re|fwd?|fw)\s*:\s*)+", re.I)
CATEGORY_BY_HINT = (("retrofit", "Retrofit Jobs"), ("energy", "Energy Optimization"), ("decarbon", "Energy Optimization"), ("vfd", "Energy Optimization"), ("solar", "Energy Optimization"))


def _today() -> str:
    return date.today().isoformat()


def client_from_context(ctx: Dict[str, Any]) -> str:
    explicit = str(ctx.get("client") or "").strip()
    if explicit:
        return explicit
    name, addr = parseaddr(str(ctx.get("from") or ""))
    name = name.strip().strip('"')
    domain = addr.split("@", 1)[1].lower() if "@" in addr else ""
    if name and domain not in NOISE:
        return name
    if domain and domain not in FREE_MAIL and domain not in NOISE:
        return domain.split(".")[0].replace("-", " ").title()
    return ""


def deal_name_from_context(ctx: Dict[str, Any], skill: str) -> str:
    for key in ("project", "subject"):
        text = _PREFIX.sub("", str(ctx.get(key) or "")).strip()
        if text:
            return text[:120]
    return (skill or "Engineering request").replace("_", " ").title()


class CRMLinker:
    def __init__(self, crm_store: Any) -> None:
        self.store = crm_store

    def handle(self, event: str, job: Any, **info: Any) -> bool:
        """Returns True when the job's project_context was changed and the job should be saved."""
        if event == "created":
            return self._created(job)
        deal = self._deal_for(job)
        if deal is None:
            return False
        if event == "rework":
            d = dict(deal.delivery or {})
            revs = list(d.get("revisions") or [])
            revs.append({"date": _today(), "note": str(info.get("comment") or "Rework requested")[:500]})
            d["revisions"] = revs[-50:]
            deal.delivery = d
        elif event == "dispatched":
            d = dict(deal.delivery or {})
            d["delivered_on"] = d.get("delivered_on") or _today()
            d["final_submitted_on"] = _today()
            deal.delivery = d
        else:
            return False
        deal.validate()
        self.store.save(deal)
        return False

    def _deal_for(self, job: Any) -> Optional[CRMDeal]:
        deal_id = (job.project_context or {}).get("crm_deal_id")
        return self.store.get(job.tenant_id, str(deal_id)) if deal_id else None

    def _created(self, job: Any) -> bool:
        ctx = job.project_context or {}
        if ctx.get("crm_deal_id"):
            return False
        company = client_from_context(ctx)
        skill = str(job.requested_skill_id or "")
        name = deal_name_from_context(ctx, skill)
        deal = next((d for d in self.store.list(job.tenant_id)
                     if d.stage != "lost" and d.name.strip().lower() == name.lower() and d.company.strip().lower() == company.lower()), None)
        if deal is None:
            hint = (skill + " " + name).lower()
            category = next((c for k, c in CATEGORY_BY_HINT if k in hint), "Project Sales")
            deal = CRMDeal(tenant_id=job.tenant_id, name=name, company=company, category=category,
                           contact=str(ctx.get("from") or "")[:120], stage="budgetary",
                           next_follow_up=(date.today() + timedelta(days=3)).isoformat(),
                           notes=f"Created automatically from a {job.source} request ({skill or 'unclassified'}). Set the value and stage when you quote.")
        deal.engineering_job_id = job.job_id
        deal.validate()
        self.store.save(deal)
        ctx["crm_deal_id"] = deal.deal_id
        job.project_context = ctx
        return True
