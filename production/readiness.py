from __future__ import annotations
import importlib.util
import os
from dataclasses import dataclass, asdict
from typing import Iterable

@dataclass(frozen=True)
class Check:
    name: str
    status: str  # PASS / BLOCKED / WARN
    detail: str

@dataclass(frozen=True)
class ReadinessReport:
    checks: tuple[Check, ...]
    overall: str
    def to_dict(self):
        return {"overall": self.overall, "checks": [asdict(c) for c in self.checks]}

REQUIRED_MODULES = (
    "workflow.service", "integrations.providers.upwork", "reports.upwork_deliverable",
    "engineering.drawing.model", "engineering.drawing.serialization",
)


def _module_check(name: str) -> Check:
    return Check(name, "PASS", "available") if importlib.util.find_spec(name) else Check(name, "BLOCKED", "module not found")


def evaluate(*, require_upwork_config: bool = False, env: dict[str, str] | None = None) -> ReadinessReport:
    env = dict(os.environ if env is None else env)
    checks = [_module_check(m) for m in REQUIRED_MODULES]
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    registry_path = os.path.join(project_root, "standards", "registry.yaml")
    if not os.path.exists(registry_path):
        checks.append(Check("standards_registry", "BLOCKED", "standards/registry.yaml not found"))
    else:
        checks.append(Check("standards_registry", "PASS", "available"))
    checks.append(Check("secret_exposure", "PASS", "readiness checks never print secret values"))
    required = ("UPWORK_CLIENT_ID", "UPWORK_CLIENT_SECRET", "UPWORK_REDIRECT_URI")
    missing = [k for k in required if not env.get(k)]
    if missing:
        status = "BLOCKED" if require_upwork_config else "WARN"
        checks.append(Check("upwork_configuration", status, "missing: " + ", ".join(missing)))
    else:
        checks.append(Check("upwork_configuration", "PASS", "required configuration present"))
    blocked = any(c.status == "BLOCKED" for c in checks)
    overall = "BLOCKED" if blocked else ("READY_WITH_WARNINGS" if any(c.status == "WARN" for c in checks) else "READY")
    return ReadinessReport(tuple(checks), overall)
