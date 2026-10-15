import base64
import json

from jobs.compact import LARGE_VALUE_CHARS, compact_large_values, marker
from tests.test_project_client_and_export import _app, _call


def test_compact_replaces_only_large_strings_and_keeps_structure():
    big = "A" * (LARGE_VALUE_CHARS + 1)
    out = compact_large_values({"a": big, "b": "short", "c": [{"d": big}, 3], "e": 1.5})
    assert out["b"] == "short" and out["c"][1] == 3 and out["e"] == 1.5
    assert out["a"] == marker(big) and out["c"][0]["d"] == marker(big)
    assert "sha256" in out["a"] and f"{len(big):,}" in out["a"]
    assert compact_large_values("x" * LARGE_VALUE_CHARS) == "x" * LARGE_VALUE_CHARS


def test_uploaded_blob_is_stored_once_and_input_hash_is_over_the_full_value():
    from reports.evidence import sha256
    import os
    blob = base64.b64encode(os.urandom(36000)).decode()
    inputs = {"boq_csv": "item,qty,unit\nGypsum ceiling,100,sqm\n", "note_blob": blob}
    app = _app()
    st, job = _call(app, "POST", "/v1/intake", {"message": "Prepare the preliminary BOQ material takeoff", "requested_skill_id": "boq_takeoff", "inputs": inputs})
    assert st.startswith("201"), job
    jid = job["job"]["job_id"]
    for action in ("enqueue", "process"):
        _call(app, "POST", f"/v1/jobs/{jid}/{action}")
    j = app.store.get(jid)
    text = json.dumps(j.to_dict(), default=str)
    assert text.count(blob[:300]) == 1                      # only job.inputs holds the full value
    assert j.inputs["note_blob"] == blob
    assert j.result["evidence_bundle"]["manifest"]["input_hash"] == sha256(j.inputs)
    assert "large value omitted" in text
