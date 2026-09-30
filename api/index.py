"""Vercel entry point for the Engineering AI Platform.

The Vercel route maps /v1/* requests to this Python function. The original
public path is passed in a normal query parameter so Vercel does not consume
it as an internal routing parameter.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

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

    # IMPORTANT: use an ordinary query key. Vercel may consume/reserve names
    # beginning with __, which caused the previous routing fix to be lost.
    original_path = (query.get("engineering_path") or [""])[0]

    # Vercel can rewrite PATH_INFO to the function path and may normalize the
    # query string before invoking Python. Prefer original request-path
    # headers when available, then the explicit routing parameter.
    forwarded_path = (
        environ.get("HTTP_X_INVOKE_PATH")
        or environ.get("HTTP_X_MATCHED_PATH")
        or environ.get("HTTP_X_NOW_ROUTE_MATCHES")
        or ""
    )
    path = original_path or forwarded_path or environ.get("PATH_INFO", "")
    if path and path.startswith("/api/index.py/"):
        path = path[len("/api/index.py"):]
    method = environ.get("REQUEST_METHOD", "GET")

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
