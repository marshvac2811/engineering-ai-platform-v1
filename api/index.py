"""Vercel entry point for the Engineering AI Platform.

Keep module import lightweight. The full API application is loaded lazily so a
dependency/startup problem produces a useful HTTP response instead of a generic
FUNCTION_INVOCATION_FAILED during function initialization.
"""

from __future__ import annotations

import json
from typing import Callable
from urllib.parse import parse_qs, urlsplit

_cached_app = None


def _json(start_response, status: str, payload: dict):
    body = json.dumps(payload, default=str).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def _load_app():
    global _cached_app
    if _cached_app is None:
        from api.app import APIApp
        _cached_app = APIApp()
    return _cached_app


def app(environ, start_response):
    query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    original_path = (query.get("__vercel_path") or [""])[0]
    request_uri = environ.get("REQUEST_URI") or environ.get("RAW_URI") or ""
    request_uri_path = urlsplit(request_uri).path if request_uri else ""
    path = original_path or request_uri_path or environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "GET")

    # Vercel routes /v1/* through /api/index.py. WSGI otherwise sees the
    # function path (/api/index.py), which makes the API report "Route not found".
    # Restore the externally requested path before handing off to APIApp.
    if path:
        environ["PATH_INFO"] = path

    if path == "/health" and method == "GET":
        return _json(
            start_response,
            "200 OK",
            {"status": "ok", "service": "engineering-ai-platform"},
        )

    try:
        return _load_app()(environ, start_response)
    except Exception as exc:
        return _json(
            start_response,
            "500 Internal Server Error",
            {
                "error": "API startup failed",
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            },
        )
