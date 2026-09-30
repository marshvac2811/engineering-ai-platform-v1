"""Vercel entry point for the Engineering AI Platform.

Keep module import lightweight. The full API application is loaded lazily so a
dependency/startup problem produces a useful HTTP response instead of a generic
FUNCTION_INVOCATION_FAILED during function initialization.
"""

from __future__ import annotations

import json
from typing import Callable

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
    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "GET")

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
