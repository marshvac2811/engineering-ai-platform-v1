"""Minimal provider-neutral WSGI API for the engineering job service.

This boundary intentionally contains no engineering calculations. In production,
X-Tenant-ID should be derived from the authenticated Supabase JWT rather than
trusted directly from the HTTP client.
"""
from __future__ import annotations
import json
import os

from dotenv import load_dotenv

load_dotenv()
from urllib.parse import parse_qs
from typing import Callable, Dict, Tuple
from jobs.service import JobService
from jobs.models import JobStatus
from jobs.store import InMemoryJobStore
from jobs.supabase_store import build_supabase_job_store_from_env
from ingestion.factory import build_ingestion_service
from orchestrator.registry_loader import load_registry
from orchestrator.intake import build_plan
from orchestrator.provider_factory import build_intent_provider
from orchestrator.provider import ProviderUnavailableError
from api.auth import DevelopmentHeaderAuthenticator, ApiKeyAuthenticator, SupabaseJWTAuthenticator, AuthContext, AuthenticationError
from api.security import InMemoryApiKeyStore, InMemoryUsageStore, UsageEvent
from crm.service import CRMService
from crm.store import InMemoryCRMStore
from crm.supabase_store import build_supabase_crm_store_from_env
from integrations.service import IntegrationService, InMemoryIntegrationStore
from integrations.supabase_store import build_supabase_integration_store_from_env
from workflow.service import WorkflowTaskService
from workflow.store import InMemoryWorkflowTaskStore
from workflow.supabase_store import build_supabase_workflow_task_store_from_env
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

class APIApp:
    def __init__(self, service_factory: Callable[[str], JobService] | None = None, *,
                 development_authenticator=None, api_keys=None, usage_store=None,
                 gmail_client=None, gmail_token_store=None, gmail_state_store=None,
                 store=None, ingestion=None, crm_store=None, integration_store=None, workflow_task_store=None) -> None:
        self.store = store or build_supabase_job_store_from_env() or InMemoryJobStore()
        self.ingestion = ingestion or build_ingestion_service()
        self.api_keys = api_keys or InMemoryApiKeyStore()
        self.usage = usage_store or InMemoryUsageStore()
        self.crm_store = crm_store or build_supabase_crm_store_from_env() or InMemoryCRMStore()
        self.integration_store = integration_store or build_supabase_integration_store_from_env() or InMemoryIntegrationStore()
        self.workflow_task_store = workflow_task_store or build_supabase_workflow_task_store_from_env() or InMemoryWorkflowTaskStore()
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
        self.service_factory = service_factory or (lambda tenant: JobService(self.store, tenant_id=tenant, ingestion_service=self.ingestion))

    def _authenticate(self, environ) -> AuthContext:
        auth = environ.get("HTTP_AUTHORIZATION", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()

            # Supabase JWTs are three-part tokens; existing API keys remain opaque.
            if token.count(".") == 2:
                if self.supabase_jwt_authenticator is None:
                    self.supabase_jwt_authenticator = SupabaseJWTAuthenticator()
                return self.supabase_jwt_authenticator.authenticate(environ)

            return self.api_key_authenticator.authenticate(environ)

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

        if path == "/app" and method == "GET":
            data = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Engineering AI Platform</title>
<style>
body{margin:0;font-family:Arial,sans-serif;background:#f4f7fb;color:#172033}
header{background:#172033;color:white;padding:20px 28px}
main{max-width:1100px;margin:30px auto;padding:0 20px}
.card{background:white;padding:24px;border-radius:14px;box-shadow:0 5px 20px rgba(0,0,0,.08);margin-bottom:20px}
h1{margin:0;font-size:25px}
h2{margin-top:0}
.status{color:#176b3a;font-weight:600}
</style>
</head>
<body>
<header><h1>Engineering AI Platform</h1></header>
<main>
<div class="card">
<h2>Engineering Operations Dashboard</h2>
<p class="status" id="authStatus">Authenticated</p>
<div id="account">Loading account...</div>
</div>
<div class="card">
<h2>Engineering Skills</h2>
<div id="skills-status">Loading engineering skills...</div>
<div id="skills"></div>
<div id="skill-detail" style="display:none;margin-top:20px"></div>
</div>

<div class="card">
<h2>Engineering Jobs</h2>
<div id="jobs">Loading jobs...</div>
<div id="job-detail" style="display:none;margin-top:20px"></div>
</div>

<div class="card">
<h2>Engineering Request</h2>
<p>Submit an engineering request for automatic skill selection, input validation, execution, human review and dispatch.</p>

<label for="intake-message"><strong>Engineering Request</strong></label>
<textarea id="intake-message" rows="5" style="width:100%;box-sizing:border-box;padding:10px;margin-top:8px;border:1px solid #ccc;border-radius:8px" placeholder="Example: Size a round duct for 8000 CFM using velocity at 7 m/s"></textarea>

<div style="margin-top:14px">
<label for="intake-skill"><strong>Skill Selection</strong></label>
<select id="intake-skill" style="width:100%;box-sizing:border-box;padding:10px;margin-top:8px;border:1px solid #ccc;border-radius:8px">
<option value="">Auto-detect</option>
</select>
</div>

<div style="margin-top:14px">
<label for="intake-inputs"><strong>Optional Inputs (JSON)</strong></label>
<textarea id="intake-inputs" rows="5" style="width:100%;box-sizing:border-box;padding:10px;margin-top:8px;border:1px solid #ccc;border-radius:8px" placeholder='{"example":"value"}'></textarea>
</div>

<div style="margin-top:14px">
<label for="intake-context"><strong>Project Context (JSON)</strong></label>
<textarea id="intake-context" rows="5" style="width:100%;box-sizing:border-box;padding:10px;margin-top:8px;border:1px solid #ccc;border-radius:8px" placeholder='{"project":"Example project","location":"Gurgaon"}'></textarea>
</div>

<div style="margin-top:14px">
<button onclick="submitEngineeringRequest()">Submit Engineering Request</button>
</div>

<div id="intake-result" style="display:none;margin-top:20px"></div>
<div id="intake-information" style="display:none;margin-top:20px"></div>
</div>

<script>
const token = localStorage.getItem("engineering_ai_access_token");

async function refreshAccessToken() {
    const refreshToken = localStorage.getItem("engineering_ai_refresh_token");

    if (!refreshToken) {
        throw new Error("No refresh token available. Please sign in again.");
    }

    const response = await fetch(
        "https://vaxerlbgwwlfamncevdg.supabase.co/auth/v1/token?grant_type=refresh_token",
        {
            method: "POST",
            headers: {
                "apikey": "sb_publishable_X68FRNA50gzwKqH7SFbOGQ_OyemX0_s",
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                refresh_token: refreshToken
            })
        }
    );

    const data = await response.json();

    if (!response.ok || !data.access_token) {
        localStorage.removeItem("engineering_ai_access_token");
        localStorage.removeItem("engineering_ai_refresh_token");
        throw new Error(data.error_description || data.msg || "Session refresh failed. Please sign in again.");
    }

    localStorage.setItem("engineering_ai_access_token", data.access_token);

    if (data.refresh_token) {
        localStorage.setItem("engineering_ai_refresh_token", data.refresh_token);
    }

    return data.access_token;
}

async function authFetch(url, options = {}) {
    const requestOptions = Object.assign({}, options);
    const headers = Object.assign({}, requestOptions.headers || {});

    let accessToken = localStorage.getItem("engineering_ai_access_token");

    if (!accessToken) {
        throw new Error("No active authentication session. Please sign in.");
    }

    headers["Authorization"] = "Bearer " + accessToken;
    requestOptions.headers = headers;

    let response = await fetch(url, requestOptions);

    if (response.status !== 401) {
        return response;
    }

    accessToken = await refreshAccessToken();

    const retryHeaders = Object.assign({}, headers, {
        "Authorization": "Bearer " + accessToken
    });

    requestOptions.headers = retryHeaders;

    return fetch(url, requestOptions);
}
const accountBox = document.getElementById("account");
const skillsStatusBox = document.getElementById("skills-status");
const skillsBox = document.getElementById("skills");
const skillDetailBox = document.getElementById("skill-detail");
const jobsBox = document.getElementById("jobs");
const detailBox = document.getElementById("job-detail");

function esc(value) {

    return String(value ?? "").replace(/[&<>"']/g, function(c) {
        return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
}


async function loadAccount() {
    if (!token) {
        accountBox.textContent = "No active authentication session.";
        return;
    }

    try {
        const response = await authFetch("/v1/account", {
            headers: {"Authorization": "Bearer " + token}
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Account request failed");
        }

        accountBox.innerHTML =
            "<p><strong>Tenant:</strong> " + esc(data.tenant_id) + "</p>" +
            "<p><strong>User ID:</strong> " + esc(data.user_id) + "</p>" +
            "<p><strong>Role:</strong> " + esc(data.role) + "</p>" +
            "<p><strong>Authentication:</strong> " + esc(data.auth_method) + "</p>" +
            "<p><strong>Scopes:</strong> " + esc((data.scopes || []).join(", ")) + "</p>";
    } catch (error) {
        accountBox.textContent = "Account load failed: " + error.message;
    }
}

async function loadSkills() {
    if (!token) {
        skillsStatusBox.textContent = "No active authentication session.";
        return;
    }

    try {
        const response = await authFetch("/v1/skills", {
            headers: {"Authorization": "Bearer " + token}
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Skills request failed");
        }

        const skills = data.skills || [];

        skillsStatusBox.innerHTML =
            "<p><strong>Registry:</strong> v" + esc(data.version) +
            " &nbsp; <strong>Status:</strong> " + esc(data.status) +
            " &nbsp; <strong>Total:</strong> " + esc(data.count) + "</p>";

        if (skills.length === 0) {
            skillsBox.innerHTML = "<p>No engineering skills registered.</p>";
            return;
        }

        skillsBox.innerHTML = skills.map(function(skill, index) {
            const executable = skill.integration_status === "integrated";

            return "<div style='border:1px solid #ddd;padding:12px;margin:10px 0;border-radius:8px'>" +
                "<div style='display:flex;justify-content:space-between;gap:12px;align-items:center'>" +
                "<div>" +
                "<p style='margin:0'><strong>" + esc(skill.skill_id) + "</strong></p>" +
                "<p style='margin:5px 0'><strong>Domain:</strong> " + esc(skill.domain || "-") +
                " &nbsp; <strong>Classification:</strong> " + esc(skill.classification || "-") + "</p>" +
                "<p style='margin:5px 0'><strong>Integration:</strong> " + esc(skill.integration_status || "-") +
                " &nbsp; <strong>Human Review:</strong> " + (skill.human_review_required ? "Yes" : "No") + "</p>" +
                "</div>" +
                "<button onclick='showSkill(" + index + ")'>View Inputs</button>" +
                "</div>" +
                "</div>";
        }).join("");

        window.engineeringSkills = skills;
    } catch (error) {
        skillsStatusBox.textContent = "Skills load failed: " + error.message;
        skillsBox.innerHTML = "";
    }
}

function showSkill(index) {
    const skill = (window.engineeringSkills || [])[index];

    if (!skill) {
        return;
    }

    function inputRows(items) {
        if (!items || items.length === 0) {
            return "<p>None</p>";
        }

        return "<ul>" + items.map(function(item) {
            return "<li><strong>" + esc(item.name) + "</strong> Ã¢â‚¬â€ " +
                esc(item.data_type || "value") +
                (item.allowed_values ? " Ã¢â‚¬â€ Allowed: " + esc(item.allowed_values.join(", ")) : "") +
                (item.description ? " Ã¢â‚¬â€ " + esc(item.description) : "") +
                "</li>";
        }).join("") + "</ul>";
    }

    skillDetailBox.style.display = "block";
    skillDetailBox.innerHTML =
        "<div style='border-top:1px solid #ddd;padding-top:16px'>" +
        "<h3>Skill Detail</h3>" +
        "<p><strong>Skill ID:</strong> " + esc(skill.skill_id) + "</p>" +
        "<p><strong>Domain:</strong> " + esc(skill.domain || "-") + "</p>" +
        "<p><strong>Source Repository:</strong> " + esc(skill.source_repository || "-") + "</p>" +
        "<p><strong>Execution:</strong> " + esc(skill.execution || "-") + "</p>" +
        "<p><strong>Classification:</strong> " + esc(skill.classification || "-") + "</p>" +
        "<p><strong>Integration Status:</strong> " + esc(skill.integration_status || "-") + "</p>" +
        "<p><strong>Human Review Required:</strong> " + (skill.human_review_required ? "Yes" : "No") + "</p>" +
        "<h4>Required Inputs</h4>" +
        inputRows(skill.required_inputs) +
        "<h4>Optional Inputs</h4>" +
        inputRows(skill.optional_inputs) +
        "<h4>Conditional Inputs</h4>" +
        inputRows(skill.conditional_inputs) +
        "<button onclick='skillDetailBox.style.display=\\\"none\\\"'>Close</button>" +
        "</div>";
}

function parseJsonField(id, label) {
    const raw = document.getElementById(id).value.trim();

    if (!raw) {
        return {};
    }

    try {
        const value = JSON.parse(raw);

        if (!value || Array.isArray(value) || typeof value !== "object") {
            throw new Error(label + " must be a JSON object.");
        }

        return value;
    } catch (error) {
        throw new Error(label + " is invalid JSON: " + error.message);
    }
}

async function loadIntakeSkills() {
    const select = document.getElementById("intake-skill");

    if (!select || !window.engineeringSkills) {
        return;
    }

    const executableSkills = window.engineeringSkills.filter(function(skill) {
        return skill.integration_status === "integrated";
    });

    executableSkills.forEach(function(skill) {
        const option = document.createElement("option");
        option.value = skill.skill_id;
        option.textContent = skill.skill_id + " (" + (skill.domain || "Engineering") + ")";
        select.appendChild(option);
    });
}

function renderIntakePlan(plan, job) {
    const resultBox = document.getElementById("intake-result");
    const informationBox = document.getElementById("intake-information");

    resultBox.style.display = "block";
    informationBox.style.display = "none";

    const missing = plan.missing_inputs || [];
    const questions = plan.questions || [];
    const extracted = plan.extracted_inputs || {};

    resultBox.innerHTML =
        "<div style='border-top:1px solid #ddd;padding-top:16px'>" +
        "<h3>Engineering Request Result</h3>" +
        "<p><strong>Status:</strong> " + esc(plan.status || "-") + "</p>" +
        "<p><strong>Selected Skill:</strong> " + esc(plan.selected_skill_id || "-") + "</p>" +
        "<p><strong>Confidence:</strong> " + esc(plan.confidence ?? "-") + "</p>" +
        "<p><strong>Job ID:</strong> " + esc((job || {}).job_id || "-") + "</p>" +
        "<p><strong>Job Status:</strong> " + esc((job || {}).status || "-") + "</p>" +
        "<p><strong>Routing Rationale:</strong> " + esc(plan.rationale || "-") + "</p>" +
        "<h4>Extracted / Provided Inputs</h4>" +
        "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px'>" +
        esc(JSON.stringify(extracted, null, 2)) + "</pre>" +
        "<h4>Missing Inputs</h4>" +
        "<pre style='white-space:pre-wrap;background:#fff8e1;padding:10px;border-radius:6px'>" +
        esc(JSON.stringify(missing, null, 2)) + "</pre>" +
        "<h4>Questions</h4>" +
        "<pre style='white-space:pre-wrap;background:#fff8e1;padding:10px;border-radius:6px'>" +
        esc(JSON.stringify(questions, null, 2)) + "</pre>" +
        "</div>";

    if (missing.length > 0 && job && job.job_id) {
        informationBox.style.display = "block";

        informationBox.innerHTML =
            "<div style='border:1px solid #ddd;padding:16px;border-radius:8px'>" +
            "<h3>Provide Missing Engineering Information</h3>" +
            "<p>The job is waiting for additional inputs. Enter the missing values as JSON.</p>" +
            "<p><strong>Required:</strong> " + esc(missing.join(", ")) + "</p>" +
            "<p><strong>Questions:</strong></p>" +
            "<ul>" +
            questions.map(function(question) {
                return "<li>" + esc(question) + "</li>";
            }).join("") +
            "</ul>" +
            "<textarea id='missing-inputs' rows='6' style='width:100%;box-sizing:border-box;padding:10px;border:1px solid #ccc;border-radius:8px' placeholder='{&quot;flow_m3hr&quot;:20,&quot;diameter_mm&quot;:80,&quot;straight_length_m&quot;:60,&quot;static_head_m&quot;:8,&quot;margin_pct&quot;:10}'></textarea>" +
            "<div style='margin-top:12px'>" +
            "<button onclick=&quot;provideMissingInformation('" + esc(job.job_id) + "')&quot;>Submit Missing Information</button>" +
            "</div>" +
            "</div>";
    }
}

async function submitEngineeringRequest() {
    const resultBox = document.getElementById("intake-result");

    try {
        const message = document.getElementById("intake-message").value.trim();

        if (!message) {
            throw new Error("Engineering Request is required.");
        }

        const skill = document.getElementById("intake-skill").value;
        const inputs = parseJsonField("intake-inputs", "Optional Inputs");
        const projectContext = parseJsonField("intake-context", "Project Context");

        const payload = {
            message: message,
            inputs: inputs,
            project_context: projectContext
        };

        if (skill) {
            payload.requested_skill_id = skill;
        }

        resultBox.style.display = "block";
        resultBox.innerHTML = "<p>Submitting engineering request...</p>";

        const response = await authFetch("/v1/intake", {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Engineering intake failed");
        }

        renderIntakePlan(data.plan || {}, data.job || {});
        await loadJobs();

        if (data.job && data.job.job_id) {
            await openJob(data.job.job_id);
        }
    } catch (error) {
        resultBox.style.display = "block";
        resultBox.innerHTML =
            "<p style='color:#b00020'><strong>Request failed:</strong> " +
            esc(error.message) + "</p>";
    }
}

async function provideMissingInformation(jobId) {
    try {
        const raw = document.getElementById("missing-inputs").value.trim();

        if (!raw) {
            throw new Error("Missing information JSON is required.");
        }

        let inputs;

        try {
            inputs = JSON.parse(raw);
        } catch (error) {
            throw new Error("Missing information must be valid JSON: " + error.message);
        }

        if (!inputs || Array.isArray(inputs) || typeof inputs !== "object") {
            throw new Error("Missing information must be a JSON object.");
        }

        const response = await authFetch(
            "/v1/jobs/" + encodeURIComponent(jobId) + "/information",
            {
                method: "POST",
                headers: {
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({inputs: inputs})
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Information update failed");
        }

        alert("Engineering information updated successfully.");

        await loadJobs();
        await openJob(jobId);
    } catch (error) {
        alert(error.message);
    }
}

async function loadJobs() {
    if (!token) {
        jobsBox.textContent = "No active authentication session.";
        return;
    }

    try {
        const response = await authFetch("/v1/jobs", {
            headers: {"Authorization": "Bearer " + token}
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Jobs request failed");
        }

        if (!data.jobs || data.jobs.length === 0) {
            jobsBox.innerHTML = "<p>No engineering jobs found.</p>";
            return;
        }

        jobsBox.innerHTML =
            "<p><strong>Total Jobs:</strong> " + esc(data.count) + "</p>" +
            data.jobs.map(function(job) {
                return "<div style='border:1px solid #ddd;padding:12px;margin:10px 0;border-radius:8px;cursor:pointer' " +
                    "onclick='openJob(\\"" + esc(job.job_id) + "\\")'>" +
                    "<p><strong>Job ID:</strong> " + esc(job.job_id) + "</p>" +
                    "<p><strong>Status:</strong> " + esc(job.status) + "</p>" +
                    "<p><strong>Skill:</strong> " + esc(job.skill_id || job.requested_skill_id || "Not selected") + "</p>" +
                    "<p><strong>Source:</strong> " + esc(job.source || "api") + "</p>" +
                    "</div>";
            }).join("");
    } catch (error) {
        jobsBox.textContent = error.message;
    }
}

async function openJob(jobId) {
    detailBox.style.display = "block";
    detailBox.innerHTML = "<p>Loading job detail...</p>";

    try {
        const response = await authFetch("/v1/jobs/" + encodeURIComponent(jobId), {
            headers: {"Authorization": "Bearer " + token}
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Job request failed");
        }

        const result = data.result || {};
        const engineering = result.engineering_result || result;

        detailBox.innerHTML =
            "<div style='border-top:1px solid #ddd;padding-top:16px'>" +
            "<h3>Job Detail</h3>" +
            "<p><strong>Job ID:</strong> " + esc(data.job_id) + "</p>" +
            "<p><strong>Tenant:</strong> " + esc(data.tenant_id) + "</p>" +
            "<p><strong>Status:</strong> " + esc(data.status) + "</p>" +
            "<p><strong>Source:</strong> " + esc(data.source) + "</p>" +
            "<p><strong>Requested Skill:</strong> " + esc(data.requested_skill_id || "-") + "</p>" +
            "<p><strong>Resolved Skill:</strong> " + esc(data.skill_id || "-") + "</p>" +
            "<p><strong>Attempt:</strong> " + esc(data.attempt) + "</p>" +

            "<h4>Inputs</h4>" +
            "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(data.inputs || {}, null, 2)) + "</pre>" +

            "<h4>Engineering Result</h4>" +
            "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(engineering || {}, null, 2)) + "</pre>" +

            "<h4>Warnings</h4>" +
            "<pre style='white-space:pre-wrap;background:#fff8e1;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(data.warnings || [], null, 2)) + "</pre>" +

            "<h4>Errors</h4>" +
            "<pre style='white-space:pre-wrap;background:#ffebee;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(data.errors || [], null, 2)) + "</pre>" +

            "<h4>Lifecycle Events</h4>" +
            "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px'>" +
            esc(JSON.stringify(data.events || [], null, 2)) + "</pre>" +

            "<p><strong>Human Review Required:</strong> " +
            (result.human_review_required ? "Yes" : "No") + "</p>" +

            "<p><strong>Dispatch:</strong> " +
            esc((data.dispatch_result || {}).mode || "manual") + "</p>" +

            "<div style='margin-top:15px'>" +
            "<button onclick=&quot;jobAction('" + esc(data.job_id) + "','enqueue')&quot;>Enqueue</button> " +
            "<button onclick=&quot;jobAction('" + esc(data.job_id) + "','process')&quot;>Process</button> " +
            "<button onclick=&quot;approveJob('" + esc(data.job_id) + "')&quot;>Approve</button> " +
            "<button onclick=&quot;jobAction('" + esc(data.job_id) + "','dispatch')&quot;>Dispatch</button> " +
            "<button onclick=&quot;detailBox.style.display='none'&quot;>Close</button>" +
            "</div>" +
            "</div>";
    } catch (error) {
        detailBox.innerHTML = "<p>" + esc(error.message) + "</p>";
    }
}

async function jobAction(jobId, action) {
    const response = await authFetch(
        "/v1/jobs/" + encodeURIComponent(jobId) + "/" + action,
        {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            },
            body: "{}"
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.error || "Action failed");
        return;
    }

    await loadJobs();
    await openJob(jobId);
}

async function approveJob(jobId) {
    const comment = prompt("Reviewer comment (optional):", "");

    if (comment === null) {
        return;
    }

    const response = await authFetch(
        "/v1/jobs/" + encodeURIComponent(jobId) + "/approve",
        {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                reviewer: "browser-user",
                comment: comment
            })
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.error || "Approval failed");
        return;
    }

    await loadJobs();
    await openJob(jobId);
}

loadAccount();
loadSkills().then(loadIntakeSkills);
loadJobs();
</script>
</body>
</html>""".encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(data)))
            ])
            return [data]

        if path == "/health" and method == "GET":
            return self._json(start_response, "200 OK", {"status": "ok"})
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
                tenant_id = str(environ.get("HTTP_X_TENANT_ID") or "").strip()
                if not tenant_id:
                    raise AuthenticationError("X-Tenant-ID is required for integration webhooks")
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
                plan = build_plan(
                    message,
                    requested_skill_id=body.get("requested_skill_id"),
                    provided_inputs=body.get("inputs", {}),
                    project_context=body.get("project_context", {}),
                    standards_context=body.get("standards_context", {}),
                    assumptions_context=body.get("assumptions_context", {}),
                    provider=provider,
                )
                job = service.create_from_plan(plan)
                return self._json(start_response, "201 Created", {"plan": plan.to_dict(), "job": job.to_dict()})

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
                job = service.create_job(
                    source=body.get("source", "api"),
                    requested_skill_id=body.get("requested_skill_id"),
                    inputs=body.get("inputs", {}),
                    project_context=body.get("project_context", {}),
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
                job = service._get(job_id)
                if hasattr(service.store, "get_report_artifact"):
                    artifact = service.store.get_report_artifact(job_id, tenant_id=service.tenant_id)
                else:
                    artifact = None
                if artifact is None:
                    report = (job.result or {}).get("compliance_report")
                    if report is None:
                        return self._json(start_response, "404 Not Found", {"error": "Engineering report not available"})
                    artifact = {
                        "report_id": job.report_id if hasattr(job, "report_id") else None,
                        "job_id": job.job_id,
                        "tenant_id": job.tenant_id,
                        "version": 1,
                        "status": "approved" if job.status == JobStatus.APPROVED else "draft",
                        "title": f"Engineering Report — {job.skill_id or job.requested_skill_id or 'analysis'}",
                        "skill_id": job.skill_id or job.requested_skill_id,
                        "report": report,
                    }
                return self._json(start_response, "200 OK", artifact)

            if len(parts) == 4 and parts[0] == "v1" and parts[1] == "jobs" and parts[3] == "compliance" and method == "GET":
                job_id = parts[2]
                ctx.require_scope("jobs:read")
                job = service._get(job_id)
                if hasattr(service.store, "get_compliance_checks"):
                    checks = service.store.get_compliance_checks(job_id, tenant_id=service.tenant_id)
                else:
                    checks = list(((job.result or {}).get("engineering_result") or {}).get("compliance") or [])
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
                if not isinstance(updates, dict):
                    raise ValueError("inputs must be an object")
                job = service.provide_missing_information(job_id, updates)
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
                    job = service.approve(job_id, body.get("reviewer", ctx.user_id), body.get("comment", ""))
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







