"""WhatsApp sending through Twilio. Inactive until the credentials are added in the host environment."""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def configured() -> bool:
    return all(os.environ.get(k, "").strip() for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "STATUS_REPORT_WHATSAPP_TO"))


def send_whatsapp(text: str) -> dict:
    """Returns {"status": "sent"|"not_configured"|"failed", "detail": str}. Never raises."""
    if not configured():
        return {"status": "not_configured", "detail": "WhatsApp is not set up yet (Twilio credentials and your WhatsApp number are needed)."}
    sid, tok = os.environ["TWILIO_ACCOUNT_SID"].strip(), os.environ["TWILIO_AUTH_TOKEN"].strip()
    num = lambda v: v.strip() if v.strip().startswith("whatsapp:") else "whatsapp:" + v.strip()
    data = urllib.parse.urlencode({"From": num(os.environ["TWILIO_WHATSAPP_FROM"]), "To": num(os.environ["STATUS_REPORT_WHATSAPP_TO"]), "Body": text[:1500]}).encode()
    req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data, method="POST")
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{tok}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode() or "{}")
        return {"status": "sent", "detail": str(body.get("sid") or "")}
    except urllib.error.HTTPError as exc:
        return {"status": "failed", "detail": f"WhatsApp provider refused the message (HTTP {exc.code})."}
    except Exception:
        return {"status": "failed", "detail": "WhatsApp provider could not be reached."}
