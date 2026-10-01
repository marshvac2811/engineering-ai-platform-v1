from knowledge.retrieval import build_ai_project_context, retrieve_relevant_chunks


def test_retrieval_ranks_relevant_project_chunk():
    context = {
        "documents": [{
            "attachment_id": "a1",
            "filename": "hvac-spec.txt",
            "sha256": "abc",
            "source_type": "text",
            "chunks": [
                {"chunk_id": "c1", "index": 0, "text": "Pump flow is 25 m3/hr and pipe diameter is 80 mm."},
                {"chunk_id": "c2", "index": 1, "text": "Architectural finishes include paint and gypsum partitions."},
            ],
        }]
    }
    rows = retrieve_relevant_chunks("calculate pump head for 25 m3/hr pipe 80 mm", context)
    assert rows
    assert rows[0]["chunk_id"] == "c1"
    assert rows[0]["filename"] == "hvac-spec.txt"


def test_ai_context_is_bounded_and_provenance_preserved():
    context = {
        "documents": [{
            "attachment_id": "a1",
            "filename": "spec.txt",
            "sha256": "abc",
            "source_type": "text",
            "chunks": [{"chunk_id": str(i), "index": i, "text": f"pump flow {i} m3/hr"} for i in range(30)],
        }]
    }
    ai_context = build_ai_project_context("pump flow m3/hr", context)
    assert len(ai_context["retrieved_evidence"]) <= 12
    assert ai_context["retrieved_evidence"][0]["attachment_id"] == "a1"
