"""Turn a client's form answers into job inputs, and manage the private form link."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Any

from intake_forms import ENGINEER_DEFAULTS, STRUCTURED, form_for


def new_token() -> str:
    return secrets.token_urlsafe(24)


def attach_form(job, skill_id: str) -> str:
    """Give a job one private form link token (idempotent)."""
    cf = job.project_context.setdefault("client_form", {})
    if not cf.get("token"):
        cf.update({"token": new_token(), "skill_id": skill_id, "created_at": datetime.now(timezone.utc).isoformat()})
    return cf["token"]


def find_job(service, token: str):
    token = str(token or "")
    if len(token) < 20:
        return None
    for job in service.list_jobs():
        cf = (job.project_context or {}).get("client_form") or {}
        if cf.get("token") == token:
            return job
    return None


def form_url(token: str) -> str:
    base = (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    return f"{base}/form/{token}"


def assemble(skill_id: str, answers: dict[str, Any]) -> tuple[dict[str, Any], str, list[str]]:
    """Return (scalar inputs, text block for structured answers, problems)."""
    form = form_for(skill_id)
    if not form:
        return {}, "", ["unknown form"]
    scalars: dict[str, Any] = {}
    blocks: list[str] = []
    problems: list[str] = []
    for f in form["fields"]:
        if not f.get("client", True):
            if f["key"] in ENGINEER_DEFAULTS:
                scalars[f["key"]] = ENGINEER_DEFAULTS[f["key"]]
            continue
        raw = str(answers.get(f["key"], "") or "").strip()
        if not raw:
            if f["required"]:
                problems.append(f"{f['label']} is required")
            continue
        if f.get("structured"):
            head = STRUCTURED[f["key"]]["header"]
            blocks.append((head + "\n" if head else "") + raw)
            continue
        if f["type"] == "number":
            try:
                scalars[f["key"]] = float(raw.replace(",", ""))
                if f["key"] == "airflow":
                    scalars["airflow_unit"] = "m3/h"  # the form states m3/h; the calculation otherwise assumes CFM
            except ValueError:
                problems.append(f"{f['label']} must be a number")
            continue
        if f.get("choices"):
            match = [c for c in f["choices"] if c.lower() == raw.lower()]
            if not match:
                problems.append(f"{f['label']}: choose one of {', '.join(f['choices'])}")
                continue
            scalars[f["key"]] = match[0] if f.get("exact") else match[0].replace(" ", "_")
            continue
        scalars[f["key"]] = raw
    return scalars, "\n".join(blocks), problems
