from reports.formatting import flatten_rows, assumption_parts
from integrations.providers.gmail import normalize_message
import base64


def test_nested_plant_summary_rows_get_labels_and_units():
    rows = {l: u for l, v, u in flatten_rows({"plant_summary": {"total_outdoor_air_l_s": 45, "chilled_water_header_dn": 20, "chilled_water_flow_m3h": 1.62}})}
    assert rows["Total outdoor air (ASHRAE 62.1)"] == "L/s"
    assert rows["Chilled-water header size"] == "DN"
    assert rows["Chilled-water flow (block)"] == "m³/hr"


def test_assumption_parts_readable():
    l, v, b = assumption_parts({"name": "cfm_per_tr", "value": 400, "basis": "Airflow per TR"})
    assert v == "400 CFM per TR" and b == "Airflow per TR" and "_" not in l


def _b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode()


def test_gmail_body_uses_plain_part_not_duplicate_html():
    msg = {"id": "1", "payload": {"headers": [{"name": "Subject", "value": "s"}], "mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/plain", "body": {"data": _b64("Design HVAC for 120 m2 office")}},
        {"mimeType": "text/html", "body": {"data": _b64('<div dir="ltr">Design HVAC for 120 m2 office</div>')}}]}}
    body = normalize_message(tenant_id="t", message=msg)["payload"]["body_text"]
    assert body == "Design HVAC for 120 m2 office"


def test_gmail_html_only_is_stripped():
    msg = {"id": "1", "payload": {"headers": [], "mimeType": "text/html", "body": {"data": _b64("<div>Size a duct<br>for 5000 CFM</div>")}}}
    assert normalize_message(tenant_id="t", message=msg)["payload"]["body_text"] == "Size a duct\nfor 5000 CFM"
