"""Shared normalization helpers for external provider adapters."""
from __future__ import annotations

import base64
import email
import re
from email.message import Message
from typing import Any, Dict, Iterable


def decode_b64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return str(value)


def extract_email_address(header_value: str) -> str:
    match = re.search(r"<([^>]+)>", header_value or "")
    return (match.group(1) if match else header_value or "").strip()


def message_headers(headers: Iterable[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in headers or []:
        name = str(item.get("name", "")).lower()
        if name:
            out[name] = str(item.get("value", ""))
    return out


def parse_rfc822(raw: bytes) -> Dict[str, Any]:
    msg: Message = email.message_from_bytes(raw)
    attachments: list[dict] = []
    text_parts: list[str] = []
    for part in msg.walk():
        filename = part.get_filename()
        disposition = part.get_content_disposition()
        if filename or disposition == "attachment":
            attachments.append({
                "filename": filename or "attachment.bin",
                "content_type": part.get_content_type(),
                "size": len(part.get_payload(decode=True) or b""),
            })
            continue
        if part.get_content_type() == "text/plain":
            text_parts.append((part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", errors="replace"))
    return {
        "subject": str(msg.get("Subject", "")),
        "from": extract_email_address(str(msg.get("From", ""))),
        "to": extract_email_address(str(msg.get("To", ""))),
        "body_text": "\n".join(text_parts).strip(),
        "attachments": attachments,
    }
