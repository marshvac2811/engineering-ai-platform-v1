"""Minimal provider-neutral WSGI API for the engineering job service.

This boundary intentionally contains no engineering calculations. In production,
X-Tenant-ID should be derived from the authenticated Supabase JWT rather than
trusted directly from the HTTP client.
"""
from __future__ import annotations
import json
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
from urllib.parse import parse_qs
from typing import Callable, Dict, Tuple
from jobs.service import JobService
from jobs.models import JobStatus
from jobs.store import InMemoryJobStore
from reports.service import ReportService
from reports.store import InMemoryReportStore
from jobs.supabase_store import build_supabase_job_store_from_env
from ingestion.factory import build_ingestion_service
from orchestrator.registry_loader import load_registry
from orchestrator.intake import build_plan
from orchestrator.provider_factory import build_intent_provider
from orchestrator.provider import ProviderUnavailableError
from api.auth import DevelopmentHeaderAuthenticator, ApiKeyAuthenticator, SupabaseJWTAuthenticator, EdgeVerifiedAuthenticator, AuthContext, AuthenticationError
from api.security import InMemoryApiKeyStore, InMemoryUsageStore, SupabaseApiKeyStore, SupabaseUsageStore, UsageEvent
from crm.service import CRMService
from crm.store import InMemoryCRMStore
from crm.supabase_store import build_supabase_crm_store_from_env, SupabaseCRMStore
from integrations.service import IntegrationService, InMemoryIntegrationStore
from integrations.supabase_store import build_supabase_integration_store_from_env, SupabaseIntegrationStore
from workflow.service import WorkflowTaskService
from workflow.store import InMemoryWorkflowTaskStore
from workflow.supabase_store import build_supabase_workflow_task_store_from_env, SupabaseWorkflowTaskStore
from engineering.building.ingest import ingest_structured_layout
from engineering.building.serialization import to_dict as building_to_dict
from engineering.design.planner import plan_discipline_layout
from engineering.drawing.export import drawing_to_dict, drawing_to_svg
from engineering.drawing.service import build_job_drawing_package, authorize_drawing_package_issue
from engineering.coordination.model import find_coordinate_conflicts
from integrations.providers.upwork import (
    UpworkOAuthStateStore, TrialUpworkTokenStore, authorization_url as upwork_authorization_url,
    exchange_code as upwork_exchange_code, UpworkProviderError,
)
from integrations.providers.gmail import (
    GmailAPIClient,
    GmailOAuthStateStore,
    TrialGmailTokenStore,
    authorization_url as gmail_authorization_url,
    exchange_code as gmail_exchange_code,
    normalize_message as normalize_gmail_message,
    GmailProviderError,
)

# External dashboard contract.
DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "web" / "app.html"
_SUPABASE_AUTH_LOCK = threading.Lock()

class APIApp:
    def __init__(self, service_factory: Callable[[str], JobService] | None = None, *,
                 development_authenticator=None, api_keys=None, usage_store=None,
                 gmail_client=None, gmail_token_store=None, gmail_state_store=None,
                 store=None, ingestion=None, crm_store=None, integration_store=None, workflow_task_store=None, report_store=None) -> None:
        configured_store = store or build_supabase_job_store_from_env()
        if configured_store is None and os.getenv("ENGINEERING_ENV", "").strip().lower() == "production":
            supabase_url_present = bool((os.getenv("SUPABASE_URL") or "").strip())
            service_role_key_present = bool((os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip())
            raise RuntimeError(
                "Production requires a Supabase job store. "
                f"SUPABASE_URL={'PRESENT' if supabase_url_present else 'MISSING'}; "
                f"SUPABASE_SERVICE_ROLE_KEY={'PRESENT' if service_role_key_present else 'MISSING'}."
            )
        self.store = configured_store or InMemoryJobStore()
        self.ingestion = ingestion or build_ingestion_service()
        # Reuse the already-created production Supabase client across all persistent
        # stores. Creating several independent clients during Render startup can
        # stall initialization before Uvicorn binds its port.
        supabase_client = getattr(self.store, "client", None)
        self.api_keys = api_keys or (SupabaseApiKeyStore(supabase_client) if supabase_client is not None else InMemoryApiKeyStore())
        self.usage = usage_store or (SupabaseUsageStore(supabase_client) if supabase_client is not None else InMemoryUsageStore())
        if supabase_client is not None:
            self.crm_store = crm_store or SupabaseCRMStore(supabase_client)
            self.integration_store = integration_store or SupabaseIntegrationStore(supabase_client)
            self.workflow_task_store = workflow_task_store or SupabaseWorkflowTaskStore(supabase_client)
        else:
            self.crm_store = crm_store or build_supabase_crm_store_from_env() or InMemoryCRMStore()
            self.integration_store = integration_store or build_supabase_integration_store_from_env() or InMemoryIntegrationStore()
            self.workflow_task_store = workflow_task_store or (build_supabase_workflow_task_store_from_env() if store is None else InMemoryWorkflowTaskStore())
        # ReportService is an in-process report builder; the authoritative
        # SupabaseJobStore persists the generated report into
        # engineering_report_artifacts when the job is saved. Keeping these
        # concerns separate avoids treating a JobStore as a ReportStore.
        self.report_store = report_store or InMemoryReportStore()
        self.upwork_state_store = UpworkOAuthStateStore()
        self.upwork_token_store = TrialUpworkTokenStore()
        self.gmail_token_store = gmail_token_store or TrialGmailTokenStore()
        self.gmail_state_store = gmail_state_store or GmailOAuthStateStore()
        self.gmail_client = gmail_client or GmailAPIClient(
            client_id=os.getenv("GMAIL_CLIENT_ID", ""),
            client_secret=os.getenv("GMAIL_CLIENT_SECRET", ""),
            token_store=self.gmail_token_store,
        )
        self.development_authenticator = development_authenticator or DevelopmentHeaderAuthenticator()
        self.api_key_authenticator = ApiKeyAuthenticator(self.api_keys.lookup)
        # Lazy-load Supabase JWT verification so startup does not require Supabase env vars.
        self.supabase_jwt_authenticator = None
        self.service_factory = service_factory or (lambda tenant: JobService(
            self.store,
            tenant_id=tenant,
            ingestion_service=self.ingestion,
            report_service=ReportService(self.report_store, tenant_id=tenant),
        ))

    def _authenticate(self, environ) -> AuthContext:
        # Vercel Edge Middleware performs Supabase JWT signature verification
        # before the Python function. This keeps Supabase JWKS/Auth off the
        # Python request path, which was failing with EBUSY in Vercel.
        # SECURITY: the edge header is only trustworthy where that middleware actually
        # runs (Vercel sets VERCEL=1). Anywhere else (e.g. Render) a client could forge
        # it, so it is ignored and the signed Supabase bearer token is required.
        if environ.get("HTTP_X_ENGINEERING_AUTH") and os.getenv("VERCEL"):
            return EdgeVerifiedAuthenticator().authenticate(environ)

        auth = environ.get("HTTP_AUTHORIZATION", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()

            # Supabase JWTs are three-part tokens; existing API keys remain opaque.
            if token.count(".") == 2:
                if self.supabase_jwt_authenticator is None:
                    self.supabase_jwt_authenticator = SupabaseJWTAuthenticator()
                with _SUPABASE_AUTH_LOCK:
                    return self.supabase_jwt_authenticator.authenticate(environ)

            return self.api_key_authenticator.authenticate(environ)

        # SECURITY: plain X-Tenant-ID/X-User-ID headers grant owner access and exist only
        # for local development and tests. Never accept them in production.
        if os.getenv("ENGINEERING_ENV", "").strip().lower() == "production" and os.getenv("ENGINEERING_ALLOW_DEV_AUTH", "").strip() != "1":
            raise AuthenticationError("Authentication required: sign in to obtain a bearer token")
        return self.development_authenticator.authenticate(environ)

    def _meter(self, ctx: AuthContext, event_type: str, *, job_id=None, skill_id=None, units=1.0, metadata=None) -> None:
        self.usage.record(UsageEvent(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            event_type=event_type,
            units=units,
            job_id=job_id,
            skill_id=skill_id,
            metadata=metadata or {},
        ))

    @staticmethod
    def _json(start_response, status: str, payload: Dict) -> list[bytes]:
        body = json.dumps(payload, default=str).encode("utf-8")
        start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]

    @staticmethod
    def _read_json(environ) -> Dict:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length == 0:
            return {}
        raw = environ["wsgi.input"].read(length)
        data = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _gmail_oauth_callback(self, environ, start_response):
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        state = (query.get("state") or [""])[0]
        code = (query.get("code") or [""])[0]
        oauth_error = (query.get("error") or [""])[0]
        if oauth_error:
            return self._json(start_response, "400 Bad Request", {"error": f"Google OAuth error: {oauth_error}"})
        if not state or not code:
            return self._json(start_response, "400 Bad Request", {"error": "state and code are required"})
        callback_tenant = self.gmail_state_store.consume(state)
        client_id = os.getenv("GMAIL_CLIENT_ID", "").strip()
        client_secret = os.getenv("GMAIL_CLIENT_SECRET", "").strip()
        redirect_uri = os.getenv("GMAIL_REDIRECT_URI", "").strip()
        if not client_id or not client_secret or not redirect_uri:
            raise ValueError("Gmail OAuth environment is incomplete")
        token = gmail_exchange_code(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            code=code,
        )
        if not token.get("access_token"):
            raise GmailProviderError("Google OAuth response did not contain access_token")
        if not token.get("refresh_token"):
            existing = self.gmail_token_store.get(callback_tenant) or {}
            if existing.get("refresh_token"):
                token["refresh_token"] = existing["refresh_token"]
            else:
                raise GmailProviderError("No refresh_token returned; reconnect Gmail with consent")
        token["expires_at"] = __import__("time").time() + float(token.get("expires_in", 3600))
        self.gmail_token_store.save(callback_tenant, token)
        profile = self.gmail_client.profile(callback_tenant)
        integrations = IntegrationService(self.integration_store, tenant_id=callback_tenant)
        connection = integrations.configure(
            provider="gmail",
            status="connected",
            external_account_id=profile.get("emailAddress"),
            scopes=str(token.get("scope", "")).split(),
            metadata={"oauth": "google", "trial_token_store": "local"},
        )
        return self._json(start_response, "200 OK", {
            "connected": True,
            "tenant_id": callback_tenant,
            "email_address": profile.get("emailAddress"),
            "connection_id": connection.connection_id,
        })

    def _upwork_oauth_callback(self, environ, start_response):
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        state = (query.get("state") or [""])[0]
        code = (query.get("code") or [""])[0]
        oauth_error = (query.get("error") or [""])[0]
        if oauth_error:
            return self._json(start_response, "400 Bad Request", {"error": f"Upwork OAuth error: {oauth_error}"})
        if not state or not code:
            return self._json(start_response, "400 Bad Request", {"error": "state and code are required"})
        tenant = self.upwork_state_store.consume(state)
        client_id = os.getenv("UPWORK_CLIENT_ID", "").strip()
        client_secret = os.getenv("UPWORK_CLIENT_SECRET", "").strip()
        redirect_uri = os.getenv("UPWORK_REDIRECT_URI", "").strip()
        if not client_id or not client_secret or not redirect_uri:
            raise ValueError("UPWORK_CLIENT_ID, UPWORK_CLIENT_SECRET and UPWORK_REDIRECT_URI must be configured")
        token = upwork_exchange_code(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, code=code)
        if not token.get("access_token"):
            raise UpworkProviderError("Upwork OAuth response did not contain access_token")
        token["expires_at"] = __import__("time").time() + float(token.get("expires_in", 86400))
        self.upwork_token_store.save(tenant, token)
        integrations = IntegrationService(self.integration_store, tenant_id=tenant)
        connection = integrations.configure(
            provider="upwork", status="connected",
            scopes=str(token.get("scope", "")).split(),
            metadata={"oauth": "upwork", "trial_token_store": "local"},
        )
        return self._json(start_response, "200 OK", {"connected": True, "tenant_id": tenant, "connection_id": connection.connection_id, "provider": "upwork"})

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "")

        # Preserve the original public API path even when Vercel rewrites the
        # request to a Python function pathname.
        public_path = (
            environ.get("HTTP_X_ENGINEERING_REQUEST_PATH")
            or environ.get("HTTP_X_NOW_ROUTE_MATCHES")
            or environ.get("HTTP_X_MATCHED_PATH")
            or ""
        )
        if public_path.startswith("/v1/") or public_path == "/v1":
            path = public_path

        # Final deployment-safe normalization for internal function paths.
        if not path.startswith("/v1/") and "/v1/" in path:
            path = path[path.index("/v1/"):]
        elif path.endswith("/v1"):
            path = "/v1"
        if path == "/login" and method == "GET":
            data = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>Engineering AI Platform - Sign In</title>\n<style>\nbody{margin:0;font-family:Arial,sans-serif;background:#f4f7fb;display:flex;align-items:center;justify-content:center;min-height:100vh}\n.card{width:380px;background:white;padding:38px;border-radius:16px;box-shadow:0 10px 35px rgba(0,0,0,.12)}\nh1{margin:0 0 8px;font-size:27px;color:#172033}\np{color:#687386;margin-bottom:28px}\nlabel{display:block;margin:14px 0 6px;font-weight:600;color:#303949}\ninput{width:100%;box-sizing:border-box;padding:12px;border:1px solid #ccd3df;border-radius:8px;font-size:15px}\nbutton{width:100%;margin-top:24px;padding:13px;border:0;border-radius:8px;background:#1769e0;color:white;font-size:16px;font-weight:600;cursor:pointer}\nbutton:disabled{opacity:.6}\n#message{margin-top:18px;padding:10px;border-radius:8px;display:none;font-size:14px}\n.success{display:block!important;background:#e8f7ee;color:#176b3a}\n.error{display:block!important;background:#fdecec;color:#a12626}\n.small{text-align:center;font-size:12px;color:#8993a3;margin-top:20px}\n</style>\n</head>\n<body>\n<div class="card">\n<h1>Engineering AI Platform</h1>\n<p>Engineering operations, automation and AI intelligence.</p>\n\n<label>Email</label>\n<input id="email" type="email" placeholder="Enter your email" autocomplete="username">\n\n<label>Password</label>\n<input id="password" type="password" placeholder="Enter your password" autocomplete="current-password">\n\n<button id="loginBtn" type="button">Sign In</button>\n<div id="message"></div>\n<div class="small">Secure engineering operations platform</div>\n</div>\n\n<script>\nconst SUPABASE_URL = "https://vaxerlbgwwlfamncevdg.supabase.co";\nconst SUPABASE_KEY = "sb_publishable_X68FRNA50gzwKqH7SFbOGQ_OyemX0_s";\n\nconst btn = document.getElementById("loginBtn");\nconst message = document.getElementById("message");\n\nbtn.addEventListener("click", async () => {\n    const email = document.getElementById("email").value.trim();\n    const password = document.getElementById("password").value;\n\n    message.className = "";\n    message.style.display = "none";\n\n    if (!email || !password) {\n        message.textContent = "Please enter email and password.";\n        message.className = "error";\n        return;\n    }\n\n    btn.disabled = true;\n    btn.textContent = "Signing in...";\n\n    try {\n        const response = await fetch(\n            SUPABASE_URL + "/auth/v1/token?grant_type=password",\n            {\n                method: "POST",\n                headers: {\n                    "apikey": SUPABASE_KEY,\n                    "Content-Type": "application/json"\n                },\n                body: JSON.stringify({\n                    email: email,\n                    password: password\n                })\n            }\n        );\n\n        const data = await response.json();\n\n        if (!response.ok) {\n            throw new Error(data.error_description || data.msg || "Authentication failed");\n        }\n\n        localStorage.setItem("engineering_ai_access_token", data.access_token);\n        localStorage.setItem("engineering_ai_refresh_token", data.refresh_token || "");\n\n        message.textContent = "Login successful. Opening Engineering AI dashboard..."; setTimeout(() => { window.location.href = "/app"; }, 500);\n        message.className = "success";\n\n    } catch (error) {\n        message.textContent = error.message;\n        message.className = "error";\n    } finally {\n        btn.disabled = false;\n        btn.textContent = "Sign In";\n    }\n});\n</script>\n</body>\n</html>'.encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(data)))
            ])
            return [data]

        if path == "/favicon.ico" and method == "GET":
            start_response("204 No Content", [("Content-Length", "0")])
            return [b""]

        if path in {"/", "/app"} and method == "GET":
            try:
                data = DASHBOARD_PATH.read_bytes()
            except OSError as exc:
                return self._json(start_response, "500 Internal Server Error", {"error": f"Dashboard unavailable: {exc}"})
            start_response("200 OK", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(data))),
                ("Cache-Control", "no-store"),
            ])
            return [data]

        if path == "/health" and method == "GET":
            # Render health must validate the live production dependency, not
            # merely prove that the Python process is running.
            if os.getenv("ENGINEERING_ENV", "").strip().lower() == "production" and hasattr(self.store, "client"):
                try:
                    self.store.client.table("automation_jobs").select("job_id").limit(1).execute()
                except Exception as exc:
                    return self._json(start_response, "503 Service Unavailable", {
                        "status": "degraded",
                        "job_store": type(self.store).__name__,
                        "database": "unreachable",
                        "error": str(exc),
                    })
                return self._json(start_response, "200 OK", {
                    "status": "ok",
                    "job_store": type(self.store).__name__,
                    "database": "reachable",
                })
            return self._json(start_response, "200 OK", {
                "status": "ok",
                "job_store": type(self.store).__name__,
            })
        if path == "/v1/integrations/gmail/oauth/callback" and method == "GET":
            try:
                return self._gmail_oauth_callback(environ, start_response)
            except KeyError as exc:
                return self._json(start_response, "404 Not Found", {"error": str(exc)})
            except (ValueError, TypeError, GmailProviderError) as exc:
                return self._json(start_response, "400 Bad Request", {"error": str(exc)})
        if path == "/v1/integrations/upwork/oauth/callback" and method == "GET":
            try:
                return self._upwork_oauth_callback(environ, start_response)
            except (ValueError, TypeError, UpworkProviderError) as exc:
                return self._json(start_response, "400 Bad Request", {"error": str(exc)})

        try:
            webhook_parts = [p for p in path.split("/") if p]
            webhook_provider = webhook_parts[2].lower() if len(webhook_parts) == 4 and webhook_parts[:2] == ["v1", "integrations"] and webhook_parts[3] == "events" else None
            webhook_secret = environ.get("HTTP_X_INTEGRATION_SECRET")
            configured_secret = os.getenv(f"INTEGRATION_WEBHOOK_SECRET_{webhook_provider.upper()}") if webhook_provider else None
            authorized_webhook = bool(webhook_provider and webhook_secret and configured_secret and webhook_secret == configured_secret)
            if authorized_webhook:
                # A validated integration webhook is already authenticated by the
                # provider-specific shared secret. Do not require the browser/client
                # to supply a trusted tenant header. For this single-tenant trial,
                # resolve the server-side default tenant instead.
                tenant_id = str(
                    os.getenv("SUPABASE_DEFAULT_TENANT_ID")
                    or os.getenv("DEFAULT_TENANT_ID")
                    or "00000000-0000-0000-0000-000000000001"
                ).strip()
                if not tenant_id:
                    raise AuthenticationError("No default tenant is configured for integration webhooks")
                ctx = AuthContext(tenant_id=tenant_id, user_id="integration-webhook", role="member", scopes={"integrations:write"}, auth_method="webhook")
            else:
                ctx = self._authenticate(environ)
                self._meter(ctx, "api_request", metadata={"method": method, "path": path})
            tenant_id = ctx.tenant_id
            service = self.service_factory(tenant_id)
            body = self._read_json(environ) if method in {"POST", "PUT", "PATCH"} else {}
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            parts = [p for p in path.split("/") if p]
            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "skills" and method == "GET":
                ctx.require_scope("jobs:read")
                registry = load_registry()
                skills = registry.get("skills", [])
                return self._json(
                    start_response,
                    "200 OK",
                    {
                        "version": registry.get("version"),
                        "status": registry.get("status"),
                        "skills": skills,
                        "count": len(skills),
                    },
                )

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "intake" and method == "POST":
                message = str(body.get("message", "")).strip()
                if not message:
                    raise ValueError("message is required")
                provider = build_intent_provider()
                project_context = dict(body.get("project_context") or {})
                if body.get("project"):
                    project_context["project"] = str(body.get("project")).strip()
                if body.get("client"):
                    project_context["client"] = str(body.get("client")).strip()
                plan = build_plan(
                    message,
                    requested_skill_id=body.get("requested_skill_id"),
                    provided_inputs=body.get("inputs", {}),
                    project_context=project_context,
                    standards_context=body.get("standards_context", {}),
                    assumptions_context=body.get("assumptions_context", {}),
                    provider=provider,
                )
                attachments = body.get("attachments", [])
                if attachments is None:
                    attachments = []
                if not isinstance(attachments, list):
                    raise ValueError("attachments must be an array")
                job = service.create_from_plan(plan, attachments=attachments, provider=provider)
                return self._json(start_response, "201 Created", {"plan": job.orchestration or plan.to_dict(), "job": job.to_dict()})

            if len(parts) == 3 and parts[0] == "v1" and parts[1] == "drawings" and parts[2] == "plan" and method == "POST":
                ctx.require_scope("jobs:write")
                payload = body.get("building")
                if not isinstance(payload, dict):
                    raise ValueError("building must be an object")
                building = ingest_structured_layout(payload)
                discipline = str(body.get("discipline", "")).strip().upper()
                floor_id = str(body.get("floor_id", "")).strip()
                room_inputs = body.get("room_inputs")
                if not isinstance(room_inputs, dict):
                    raise ValueError("room_inputs must be an object")
                drawing = plan_discipline_layout(building, discipline, floor_id, room_inputs, revision=str(body.get("revision", "A")))
                return self._json(start_response, "200 OK", {"building": building_to_dict(building), "drawing": drawing_to_dict(drawing), "svg": drawing_to_svg(drawing), "governance": {"status": "preliminary", "human_review_required": True}})

            if len(parts) == 3 and parts[0] == "v1" and parts[1] == "drawings" and parts[2] == "coordinate" and method == "POST":
                ctx.require_scope("jobs:write")
                raw_objects = body.get("objects")
                if not isinstance(raw_objects, list):
                    raise ValueError("objects must be an array")
                from engineering.drawing.objects import EngineeringObject
                objects = [EngineeringObject(str(o["object_id"]),str(o["discipline"]),str(o["kind"]),float(o["x_mm"]),float(o["y_mm"]),str(o["floor_id"]),o.get("size"),o.get("source_calculation"),o.get("confidence"),dict(o.get("attributes") or {})) for o in raw_objects]
                conflicts = find_coordinate_conflicts(objects, float(body.get("clearance_mm", 100)))
                return self._json(start_response, "200 OK", {"conflicts": [x.__dict__ for x in conflicts], "count": len(conflicts), "human_review_required": bool(conflicts)})

            if len(parts) == 3 and parts[0] == "v1" and parts[1] == "drawings" and parts[2] == "package" and method == "POST":
                ctx.require_scope("jobs:write")
                job_id = str(body.get("job_id") or "").strip()
                if not job_id:
                    raise ValueError("job_id is required")
                job = service._get(job_id)
                drawing_specs = body.get("drawings")
                if not isinstance(drawing_specs, list) or not drawing_specs:
                    raise ValueError("drawings must be a non-empty array")
                building_payload = body.get("building")
                if not isinstance(building_payload, dict):
                    raise ValueError("building must be an object")
                building = ingest_structured_layout(building_payload)
                drawings = []
                for spec in drawing_specs:
                    if not isinstance(spec, dict):
                        raise ValueError("each drawing specification must be an object")
                    drawing = plan_discipline_layout(
                        building,
                        str(spec.get("discipline", "")).strip().upper(),
                        str(spec.get("floor_id", "")).strip(),
                        spec.get("room_inputs") if isinstance(spec.get("room_inputs"), dict) else {},
                        revision=str(spec.get("revision", "A")),
                    )
                    drawings.append(drawing)
                from engineering.drawing.objects import EngineeringObject
                all_objects = [o for d in drawings for o in d.objects]
                conflicts = find_coordinate_conflicts(all_objects, float(body.get("clearance_mm", 100)))
                manifest = build_job_drawing_package(
                    job,
                    drawings,
                    source_hashes=dict(body.get("source_hashes") or {}),
                    conflicts=conflicts,
                )
                if job.status.value == "approved":
                    manifest = authorize_drawing_package_issue(manifest, job)
                result = job.result if isinstance(job.result, dict) else {}
                packages = list(result.get("drawing_packages") or [])
                packages.append(manifest)
                result["drawing_packages"] = packages
                job.result = result
                job.add_event(
                    "drawing_package_created",
                    "Controlled drawing package linked to engineering job.",
                    package_hash=manifest.get("manifest_sha256"),
                    drawing_count=len(drawings),
                    issue_status=manifest.get("issue_status"),
                )
                self.store.save(job)
                return self._json(start_response, "201 Created", {
                    "job_id": job.job_id,
                    "package": manifest,
                    "drawings": [drawing_to_dict(d) for d in drawings],
                    "svgs": [drawing_to_svg(d) for d in drawings],
                    "governance": {
                        "preliminary": True,
                        "human_review_required": True,
                        "dispatch_allowed": bool(manifest.get("dispatch_allowed")),
                    },
                })

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "api-keys" and method == "POST":
                ctx.require_scope_role("admin")
                ctx.require_scope("admin:keys")
                requested_role = str(body.get("role", "member"))
                role_rank = {"member": 1, "reviewer": 2, "engineer": 3, "admin": 4, "owner": 5}
                if requested_role not in role_rank or role_rank[requested_role] > role_rank[ctx.role]:
                    raise PermissionError("Cannot create an API key with a role above your own")
                public, secret = self.api_keys.issue(
                    tenant_id=ctx.tenant_id,
                    created_by=ctx.user_id,
                    role=requested_role,
                    name=str(body.get("name", "API key")),
                    scopes=[str(x) for x in body.get("scopes", ["jobs:read", "jobs:write", "integrations:read", "integrations:write"])],
                    expires_at=body.get("expires_at"),
                )
                return self._json(start_response, "201 Created", {"api_key": public, "secret": secret})

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "api-keys" and method == "GET":
                ctx.require_scope_role("admin")
                ctx.require_scope("admin:keys")
                return self._json(start_response, "200 OK", {"api_keys": self.api_keys.list(ctx.tenant_id)})

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "api-keys" and parts[3] == "revoke" and method == "POST":
                ctx.require_scope_role("admin")
                ctx.require_scope("admin:keys")
                record = self.api_keys.revoke(ctx.tenant_id, parts[2])
                return self._json(start_response, "200 OK", {"api_key": record})

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "usage" and method == "GET":
                ctx.require_scope("usage:read")
                return self._json(start_response, "200 OK", self.usage.summarize(ctx.tenant_id))

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "account" and method == "GET":
                return self._json(start_response, "200 OK", {
                    "tenant_id": ctx.tenant_id,
                    "user_id": ctx.user_id,
                    "role": ctx.role,
                    "auth_method": ctx.auth_method,
                    "scopes": sorted(ctx.scopes),
                })

            # Upwork OAuth and production-workflow intake
            if parts == ["v1", "integrations", "upwork", "oauth", "start"] and method == "GET":
                ctx.require_scope_role("admin")
                ctx.require_scope("integrations:write")
                client_id = os.getenv("UPWORK_CLIENT_ID", "").strip()
                redirect_uri = os.getenv("UPWORK_REDIRECT_URI", "").strip()
                if not client_id or not redirect_uri:
                    raise ValueError("UPWORK_CLIENT_ID and UPWORK_REDIRECT_URI must be configured")
                state = self.upwork_state_store.create(tenant_id)
                auth_url = upwork_authorization_url(client_id=client_id, redirect_uri=redirect_uri, state=state)
                return self._json(start_response, "200 OK", {"provider": "upwork", "authorization_url": auth_url, "state": state, "grant": "authorization_code"})

            # Workflow tasks are business-level work items; engineering Jobs remain the execution authority.
            if parts == ["v1", "workflow", "tasks"] and method == "GET":
                ctx.require_scope("workflow:read")
                workflow = WorkflowTaskService(self.workflow_task_store, tenant_id=tenant_id)
                return self._json(start_response, "200 OK", {"tasks": [t.to_dict() for t in workflow.list()]})

            if parts == ["v1", "workflow", "tasks"] and method == "POST":
                ctx.require_scope("workflow:write")
                workflow = WorkflowTaskService(self.workflow_task_store, tenant_id=tenant_id)
                task = workflow.create(
                    source=str(body.get("source", "manual")), title=str(body.get("title", "")),
                    requirement=str(body.get("requirement", "")), client_name=str(body.get("client_name", "")),
                    client_contact=str(body.get("client_contact", "")), company=str(body.get("company", "")),
                    skill_id=body.get("skill_id"), priority=str(body.get("priority", "NORMAL")).upper(),
                    deadline=body.get("deadline"), deliverable=body.get("deliverable"), notes=str(body.get("notes", "")),
                )
                return self._json(start_response, "201 Created", task.to_dict())

            if len(parts) == 4 and parts[:3] == ["v1", "workflow", "tasks"] and method == "GET":
                ctx.require_scope("workflow:read")
                workflow = WorkflowTaskService(self.workflow_task_store, tenant_id=tenant_id)
                return self._json(start_response, "200 OK", workflow.get(parts[3]).to_dict())

            if len(parts) == 5 and parts[:3] == ["v1", "workflow", "tasks"] and parts[4] == "status" and method == "POST":
                ctx.require_scope("workflow:write")
                workflow = WorkflowTaskService(self.workflow_task_store, tenant_id=tenant_id)
                updated = workflow.transition(parts[3], str(body.get("status", "")))
                return self._json(start_response, "200 OK", updated.to_dict())

            # Gmail OAuth and live trial sync
            if parts == ["v1", "integrations", "gmail", "oauth", "start"] and method == "GET":
                ctx.require_scope_role("admin")
                ctx.require_scope("integrations:write")
                client_id = os.getenv("GMAIL_CLIENT_ID", "").strip()
                redirect_uri = os.getenv("GMAIL_REDIRECT_URI", "").strip()
                if not client_id or not redirect_uri:
                    raise ValueError("GMAIL_CLIENT_ID and GMAIL_REDIRECT_URI must be configured")
                state = self.gmail_state_store.create(tenant_id)
                login_hint = (query.get("login_hint") or [None])[0]
                auth_url = gmail_authorization_url(
                    client_id=client_id,
                    redirect_uri=redirect_uri,
                    state=state,
                    login_hint=login_hint,
                )
                return self._json(start_response, "200 OK", {
                    "provider": "gmail",
                    "authorization_url": auth_url,
                    "state": state,
                    "scope": "https://www.googleapis.com/auth/gmail.readonly",
                })

            if parts == ["v1", "integrations", "gmail", "sync"] and method == "POST":
                ctx.require_scope("integrations:write")
                q = str(body.get("q") or os.getenv("GMAIL_SYNC_QUERY", "is:unread")).strip()
                max_results = min(max(1, int(body.get("max_results", 20) or 20)), 100)
                download_attachments = bool(body.get("download_attachments", True))
                ids = self.gmail_client.list_message_ids(tenant_id, q=q, max_results=max_results)
                results = []
                for item in ids:
                    message_id = str(item.get("id", ""))
                    if not message_id:
                        continue
                    raw = self.gmail_client.get_message(tenant_id, message_id)
                    normalized = normalize_gmail_message(tenant_id=tenant_id, message=raw)
                    payload = normalized["payload"]
                    integrations = IntegrationService(self.integration_store, tenant_id=tenant_id)
                    event, created = integrations.ingest(
                        provider="gmail",
                        event_type=normalized["event_type"],
                        external_event_id=normalized["external_event_id"],
                        payload=payload,
                        source_message=normalized.get("source_message"),
                    )
                    result = {"message_id": message_id, "created": created, "job_created": False}
                    if created:
                        subject = str(payload.get("subject", ""))
                        message_text = str(payload.get("body_text", ""))
                        intake_message = (subject + "\n" + message_text).strip()
                        if intake_message:
                            provider = build_intent_provider()
                            plan = build_plan(
                                intake_message,
                                project_context={"source_provider": "gmail", "external_event_id": message_id, "from": payload.get("from", "")},
                                provider=provider,
                            )
                            job = service.create_from_plan(plan)
                            result.update({"job_created": True, "job_id": job.job_id, "job_status": job.status.value, "selected_skill_id": plan.selected_skill_id})
                            if download_attachments:
                                downloaded = []
                                for attachment in payload.get("attachments", []):
                                    attachment_id = attachment.get("attachment_id")
                                    filename = str(attachment.get("filename") or "attachment.bin")
                                    if not attachment_id:
                                        continue
                                    data = self.gmail_client.get_attachment(tenant_id, message_id, str(attachment_id))
                                    registered = service.register_attachment(
                                        job.job_id,
                                        filename=filename,
                                        mime_type=attachment.get("mime_type"),
                                        data=data,
                                        metadata={"source_provider": "gmail", "source_message_id": message_id},
                                    )
                                    downloaded.append({"filename": filename, "attachment_id": registered.attachments[-1].get("attachment_id")})
                                result["attachments_downloaded"] = downloaded
                    results.append(result)
                return self._json(start_response, "200 OK", {"provider": "gmail", "query": q, "messages_seen": len(ids), "results": results})

            # External integrations / normalized inbound events
            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "integrations" and method == "GET":
                ctx.require_scope("integrations:read")
                integrations = IntegrationService(self.integration_store, tenant_id=tenant_id)
                return self._json(start_response, "200 OK", {"connections": [c.to_dict() for c in integrations.list()]})

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "integrations" and method == "POST":
                ctx.require_scope_role("admin")
                ctx.require_scope("integrations:write")
                provider_name = str(body.get("provider", "")).strip().lower()
                if not provider_name:
                    raise ValueError("provider is required")
                integrations = IntegrationService(self.integration_store, tenant_id=tenant_id)
                connection = integrations.configure(
                    provider=provider_name,
                    status=str(body.get("status", "configured")),
                    external_account_id=body.get("external_account_id"),
                    scopes=body.get("scopes", []),
                    metadata=body.get("metadata", {}),
                )
                return self._json(start_response, "201 Created", connection.to_dict())

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "integrations" and parts[3] == "events" and method == "POST":
                provider_name = parts[2].lower()
                # Webhooks may not have an end-user JWT. For trial/local use, accept
                # a per-provider shared secret; authenticated API clients can use
                # integrations:write instead. Production should use signed webhooks
                # or provider OAuth/webhook verification where supported.
                webhook_secret = environ.get("HTTP_X_INTEGRATION_SECRET")
                configured_secret = os.getenv(f"INTEGRATION_WEBHOOK_SECRET_{provider_name.upper()}")
                authorized_webhook = bool(webhook_secret and configured_secret and webhook_secret == configured_secret)
                if not authorized_webhook:
                    ctx.require_scope("integrations:write")
                integrations = IntegrationService(self.integration_store, tenant_id=tenant_id)
                external_id = str(body.get("external_event_id") or body.get("id") or "")
                if not external_id:
                    raise ValueError("external_event_id is required")
                event_type = str(body.get("event_type", "message.received"))
                payload = body.get("payload", {})
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                event, created = integrations.ingest(
                    provider=provider_name,
                    event_type=event_type,
                    external_event_id=external_id,
                    payload=payload,
                    source_message=body.get("source_message"),
                )
                response = {"event": event.to_dict(), "created": created, "task_created": False, "job_created": False}

                # Message-bearing providers first create a business task, then the existing
                # registry-driven intake creates the engineering Job. This keeps business
                # workflow and engineering execution distinct.
                if created and provider_name in {"gmail", "upwork", "fiverr"}:
                    workflow = WorkflowTaskService(self.workflow_task_store, tenant_id=tenant_id)
                    task, task_created = workflow.create_from_event(source=provider_name, external_id=external_id, payload=payload)
                    response["task_created"] = task_created
                    p = payload
                    subject = str(p.get("subject", ""))
                    message_text = str(p.get("body_text", p.get("message", p.get("text", ""))))
                    intake_message = (subject + "\n" + message_text).strip()
                    if intake_message:
                        provider = build_intent_provider()
                        plan = build_plan(
                            intake_message,
                            project_context={"source_provider": provider_name, "external_event_id": external_id, "workflow_task_id": task.task_id},
                            provider=provider,
                        )
                        job = service.create_from_plan(plan)
                        workflow.link_job(task.task_id, job.job_id)
                        response["job_created"] = True
                        response["job"] = job.to_dict()
                        response["plan"] = plan.to_dict()
                        response["task"] = workflow.get(task.task_id).to_dict()
                    else:
                        response["task"] = task.to_dict()
                return self._json(start_response, "201 Created", response)

            # Canonical internal CRM / pipeline
            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "crm" and method == "GET":
                ctx.require_scope("crm:read")
                crm = CRMService(self.crm_store, tenant_id=tenant_id)
                return self._json(start_response, "200 OK", {"deals": [d.to_dict() for d in crm.list()]})

            if len(parts) == 3 and parts[0] == "v1" and parts[1] == "crm" and parts[2] == "deals" and method == "POST":
                ctx.require_scope("crm:write")
                crm = CRMService(self.crm_store, tenant_id=tenant_id)
                deal = crm.create_deal(
                    name=str(body.get("name", "")),
                    category=str(body.get("category", "Project Sales")),
                    stakeholder=str(body.get("stakeholder", "Other")),
                    contact=str(body.get("contact", "")),
                    company=str(body.get("company", "")),
                    value=float(body.get("value", 0) or 0),
                    stage=str(body.get("stage", "budgetary")),
                    next_follow_up=body.get("next_follow_up"),
                    notes=str(body.get("notes", "")),
                    engineering_job_id=body.get("engineering_job_id"),
                )
                return self._json(start_response, "201 Created", deal.to_dict())

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "crm" and parts[2] == "deals":
                ctx.require_scope("crm:read") if method == "GET" else ctx.require_scope("crm:write")
                crm = CRMService(self.crm_store, tenant_id=tenant_id)
                deal_id = parts[3]
                if method == "GET":
                    return self._json(start_response, "200 OK", crm.get(deal_id).to_dict())
                if method == "PATCH":
                    updated = crm.update(deal_id, **body)
                    return self._json(start_response, "200 OK", updated.to_dict())

            if len(parts) == 5 and parts[0] == "v1" and parts[1] == "crm" and parts[2] == "deals" and parts[4] == "sync-hubspot" and method == "POST":
                ctx.require_scope("crm:write")
                crm = CRMService(self.crm_store, tenant_id=tenant_id)
                result = crm.sync_hubspot(parts[3])
                return self._json(start_response, "200 OK", result)

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "jobs" and method == "GET":
                ctx.require_scope("jobs:read")
                if hasattr(service.store, "list_summaries"):
                    jobs = list(service.store.list_summaries(tenant_id=service.tenant_id))
                else:
                    jobs = [job.to_dict() for job in service.list_jobs()]
                return self._json(start_response, "200 OK", {"jobs": jobs, "count": len(jobs)})

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "jobs" and method == "POST":
                ctx.require_scope("jobs:write")
                project_context = dict(body.get("project_context") or {})
                if body.get("project"):
                    project_context["project"] = str(body.get("project")).strip()
                if body.get("client"):
                    project_context["client"] = str(body.get("client")).strip()
                job = service.create_job(
                    source=body.get("source", "api"),
                    requested_skill_id=body.get("requested_skill_id"),
                    inputs=body.get("inputs", {}),
                    project_context=project_context,
                    standards_context=body.get("standards_context", {}),
                    assumptions_context=body.get("assumptions_context", {}),
                )
                return self._json(start_response, "201 Created", job.to_dict())

            if len(parts) == 3 and parts[0] == "v1" and parts[1] == "jobs":
                job_id = parts[2]
                job = service._get(job_id)
                if method == "GET":
                    ctx.require_scope("jobs:read")
                    return self._json(start_response, "200 OK", job.to_dict())

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "report" and method == "GET":
                job_id = parts[2]
                ctx.require_scope("jobs:read")
                try:
                    job = service._get(job_id)
                except KeyError:
                    return self._json(start_response, "404 Not Found", {"error": "Report is not available for this job"})
                if hasattr(service.store, "get_report_artifact"):
                    artifact = service.store.get_report_artifact(job_id, tenant_id=service.tenant_id)
                else:
                    artifact = None
                if artifact is None:
                    report = (job.result or {}).get("compliance_report")
                    if report is None:
                        # Universal workflow results are already the authoritative
                        # engineering envelope. Expose a governed report view from
                        # that envelope instead of requiring a separate legacy
                        # report artifact store.
                        result = job.result or {}
                        engineering = result.get("engineering_result") or {}
                        checks = list(engineering.get("compliance") or result.get("compliance") or [])
                        if not checks:
                            for task_result in list(engineering.get("task_results") or engineering.get("results") or []):
                                if isinstance(task_result, dict):
                                    task_engineering = task_result.get("engineering_result") or {}
                                    if isinstance(task_engineering, dict):
                                        checks.extend(task_engineering.get("compliance") or [])
                        report = {
                            "report_type": "engineering_compliance_report",
                            "engineering_result": engineering,
                            "compliance_checks": checks,
                            "checks": checks,
                            "request_understanding": result.get("request_understanding") or {},
                            "governance": result.get("governance") or {},
                            "human_review": result.get("human_review") or {"required": True},
                        }
                    artifact = {
                        "report_id": job.report_id if hasattr(job, "report_id") else None,
                        "job_id": job.job_id,
                        "tenant_id": job.tenant_id,
                        "version": 1,
                        "status": "approved" if job.status in {JobStatus.APPROVED, JobStatus.DISPATCHING, JobStatus.DISPATCHED, JobStatus.COMPLETED} else "draft",
                        "title": f"Engineering Report — {job.skill_id or job.requested_skill_id or 'analysis'}",
                        "skill_id": job.skill_id or job.requested_skill_id,
                        "report": report,
                    }

                # Backward compatibility for report artifacts created before the
                # complete ReportService envelope was persisted. If the stored
                # report has no work_items, recover the authoritative engineering
                # task results from the job record instead of returning a blank
                # report view.
                stored_report = artifact.get("report") or {}
                if not stored_report.get("work_items"):
                    result = job.result or {}
                    full_report = result.get("report") or {}
                    if full_report.get("work_items"):
                        artifact["report"] = full_report
                    else:
                        engineering = result.get("engineering_result") or {}
                        task_results = list(engineering.get("task_results") or engineering.get("results") or [])
                        if task_results:
                            artifact["report"] = {
                                **stored_report,
                                "report_type": stored_report.get("report_type") or "engineering_workflow_report",
                                "work_items": [
                                    {
                                        "skill_id": item.get("capability_id") or item.get("skill_id"),
                                        "result": {
                                            "status": item.get("status"),
                                            "engineering_result": item.get("engineering_result") or {},
                                            "calculation_trace": item.get("calculation_trace") or [],
                                            "standards": item.get("standards") or [],
                                            "compliance": item.get("compliance") or [],
                                            "assumptions": item.get("assumptions") or [],
                                            "warnings": item.get("warnings") or [],
                                            "skill_version": item.get("skill_version"),
                                            "source_revision": item.get("source_revision"),
                                            "limitations": item.get("limitations") or [],
                                        },
                                    }
                                    for item in task_results
                                    if isinstance(item, dict)
                                ],
                            }
                return self._json(start_response, "200 OK", artifact)

            if len(parts) == 2 and parts[0] == "v1" and parts[1] == "reports" and method == "GET":
                ctx.require_scope("jobs:read")
                from reports.register import VIEWS, filter_rows, rows_from_jobs, view_counts
                lister = getattr(service.store, "list_report_register", None)
                rows = lister(tenant_id=service.tenant_id) if lister else rows_from_jobs(service.list_jobs())
                view = (query.get("view") or ["all"])[0]
                if view not in VIEWS:
                    return self._json(start_response, "400 Bad Request", {"error": "Unknown view", "views": sorted(VIEWS)})
                shown = filter_rows(rows, view=view, q=(query.get("q") or [""])[0], skill=(query.get("skill") or [""])[0])
                try:
                    limit = max(1, min(int((query.get("limit") or ["200"])[0]), 500))
                    offset = max(0, int((query.get("offset") or ["0"])[0]))
                except ValueError:
                    limit, offset = 200, 0
                return self._json(start_response, "200 OK", {
                    "reports": shown[offset:offset + limit], "count": len(shown[offset:offset + limit]),
                    "total": len(shown), "views": view_counts(rows),
                    "skills": sorted({r["skill_id"] for r in rows if r["skill_id"]}),
                })

            if len(parts) == 3 and parts[0] == "v1" and parts[1] == "reports" and parts[2] == "export" and method == "GET":
                ctx.require_scope("jobs:read")
                from reports.register import VIEWS, build_register_workbook, filter_rows, rows_from_jobs
                lister = getattr(service.store, "list_report_register", None)
                rows = lister(tenant_id=service.tenant_id) if lister else rows_from_jobs(service.list_jobs())
                view = (query.get("view") or ["all"])[0]
                if view not in VIEWS:
                    return self._json(start_response, "400 Bad Request", {"error": "Unknown view", "views": sorted(VIEWS)})
                shown = filter_rows(rows, view=view, q=(query.get("q") or [""])[0], skill=(query.get("skill") or [""])[0])
                data = build_register_workbook(shown)
                start_response("200 OK", [
                    ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ("Content-Length", str(len(data))),
                    ("Content-Disposition", 'attachment; filename="engineering-report-register.xlsx"'),
                ])
                return [data]

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "audit" and method == "GET":
                ctx.require_scope("jobs:read")
                try:
                    job = service._get(parts[2])
                except KeyError:
                    return self._json(start_response, "404 Not Found", {"error": "Job not found"})
                events = [{"created_at": e.created_at, "event_type": e.event_type, "status": e.status,
                           "message": e.message, "metadata": e.metadata} for e in job.events]
                return self._json(start_response, "200 OK", {"job_id": job.job_id, "report_id": job.report_id, "events": events, "count": len(events)})

            if len(parts) == 5 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "artifacts" and method == "GET":
                job_id, kind = parts[2], parts[4]
                ctx.require_scope("jobs:read")
                if kind not in {"pdf", "xlsx"}:
                    return self._json(start_response, "404 Not Found", {"error": "Unknown artifact type; use pdf or xlsx"})
                try:
                    service._get(job_id)
                except KeyError:
                    return self._json(start_response, "404 Not Found", {"error": "Job not found"})
                getter = getattr(service.store, "get_artifact_download", None)
                link = getter(job_id, kind, tenant_id=service.tenant_id) if getter else None
                if link is None:
                    return self._json(start_response, "404 Not Found", {
                        "error": "The PDF and Excel evidence workbook are created when the job is dispatched. Approve and dispatch the job first.",
                    })
                return self._json(start_response, "200 OK", link)

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "evidence" and method == "GET":
                job_id = parts[2]
                ctx.require_scope("jobs:read")
                job = service._get(job_id)
                bundle = (job.result or {}).get("evidence_bundle")
                if not bundle:
                    return self._json(start_response, "404 Not Found", {"error": "Evidence bundle is not available for this job"})
                return self._json(start_response, "200 OK", {
                    "job_id": job.job_id,
                    "report_id": job.report_id,
                    "status": job.status.value,
                    "evidence_bundle": bundle,
                })

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "compliance" and method == "GET":
                job_id = parts[2]
                ctx.require_scope("jobs:read")
                job = service._get(job_id)
                if hasattr(service.store, "get_compliance_checks"):
                    checks = list(service.store.get_compliance_checks(job_id, tenant_id=service.tenant_id))
                else:
                    engineering = (job.result or {}).get("engineering_result") or {}
                    checks = list(engineering.get("compliance") or [])
                    if not checks:
                        for task_result in list(engineering.get("task_results") or engineering.get("results") or []):
                            if isinstance(task_result, dict):
                                task_engineering = task_result.get("engineering_result") or {}
                                if isinstance(task_engineering, dict):
                                    checks.extend(task_engineering.get("compliance") or [])
                return self._json(start_response, "200 OK", {"job_id": job.job_id, "checks": checks, "count": len(checks)})

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "attachments" and method == "POST":
                job_id = parts[2]
                ctx.require_scope("jobs:write")
                import base64
                raw = body.get("content_base64")
                if not raw:
                    raise ValueError("content_base64 is required")
                data = base64.b64decode(raw, validate=True)
                job = service.register_attachment(job_id, filename=str(body.get("filename", "attachment.bin")), mime_type=body.get("mime_type"), data=data, metadata=body.get("metadata", {}))
                return self._json(start_response, "201 Created", job.to_dict())

            if len(parts) == 5 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "attachments" and parts[4]:
                job_id, attachment_id = parts[2], parts[4]
                if method == "POST":
                    ctx.require_scope("jobs:write")
                    result = service.extract_attachment(job_id, attachment_id)
                    return self._json(start_response, "200 OK", result)
            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "information":
                job_id = parts[2]
                if method != "POST":
                    return self._json(start_response, "405 Method Not Allowed", {"error": "POST required"})
                ctx.require_scope("jobs:write")
                updates = body.get("inputs", {})
                if updates is None:
                    updates = {}
                if not isinstance(updates, dict):
                    raise ValueError("inputs must be an object")
                message = body.get("message")
                if message is not None and not isinstance(message, str):
                    raise ValueError("message must be a string")
                job = service.provide_missing_information(job_id, updates, message=message)
                return self._json(start_response, "200 OK", job.to_dict())

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "jobs":
                job_id, action = parts[2], parts[3]
                if method != "POST":
                    return self._json(start_response, "405 Method Not Allowed", {"error": "POST required"})
                if action == "enqueue":
                    ctx.require_scope("jobs:write")
                    job = service.enqueue(job_id)
                elif action == "process":
                    ctx.require_scope("jobs:write")
                    job = service.process(job_id)
                    self._meter(ctx, "skill_execution", job_id=job.job_id, skill_id=job.skill_id)
                elif action == "approve":
                    ctx.require_scope("jobs:approve")
                    ctx.require_scope_role("review")
                    # The reviewer must be the verified signed-in person, never a name typed by the client.
                    reviewer = body.get("reviewer", ctx.user_id) if ctx.auth_method == "development" else ctx.reviewer_label()
                    job = service.approve(job_id, reviewer, body.get("comment", ""))
                    # Optional one-click approve-and-dispatch: lets a reviewer clear the whole
                    # day's queue without a second click per job, as long as they also hold
                    # dispatch rights. Approval itself always succeeds even if this part fails.
                    if body.get("dispatch"):
                        try:
                            ctx.require_scope("jobs:dispatch")
                            ctx.require_scope_role("dispatch")
                        except PermissionError:
                            pass  # Approval stands; the job simply waits for someone with dispatch rights.
                        else:
                            job = service.dispatch(job.job_id)
                elif action == "rework":
                    ctx.require_scope("jobs:approve")
                    ctx.require_scope_role("review")
                    reviewer = body.get("reviewer", ctx.user_id) if ctx.auth_method == "development" else ctx.reviewer_label()
                    job = service.request_rework(job_id, reviewer, body.get("comment", ""))
                elif action == "resubmit":
                    ctx.require_scope("jobs:write")
                    updates = body.get("inputs") or {}
                    if not isinstance(updates, dict):
                        raise ValueError("inputs must be an object")
                    actor = body.get("reviewer", ctx.user_id) if ctx.auth_method == "development" else ctx.reviewer_label()
                    job = service.resubmit_after_rework(job_id, actor, updates, str(body.get("note") or ""))
                    self._meter(ctx, "skill_execution", job_id=job.job_id, skill_id=job.skill_id)
                elif action == "dispatch":
                    ctx.require_scope("jobs:dispatch")
                    ctx.require_scope_role("dispatch")
                    job = service.dispatch(job_id)
                else:
                    return self._json(start_response, "404 Not Found", {"error": "Unknown job action"})
                return self._json(start_response, "200 OK", job.to_dict())

            return self._json(start_response, "404 Not Found", {"error": "Route not found"})
        except KeyError as exc:
            return self._json(start_response, "404 Not Found", {"error": str(exc)})
        except AuthenticationError as exc:
            return self._json(start_response, "401 Unauthorized", {"error": str(exc)})
        except PermissionError as exc:
            return self._json(start_response, "403 Forbidden", {"error": str(exc)})
        except ProviderUnavailableError as exc:
            return self._json(start_response, "503 Service Unavailable", {"error": str(exc)})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self._json(start_response, "400 Bad Request", {"error": str(exc)})
        except Exception as exc:
            return self._json(start_response, "500 Internal Server Error", {"error": str(exc)})

from uvicorn.middleware.wsgi import WSGIMiddleware

app = WSGIMiddleware(APIApp())







