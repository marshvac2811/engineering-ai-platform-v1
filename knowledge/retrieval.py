"""Lightweight evidence retrieval over extracted project-document chunks.

This V1 retriever is intentionally deterministic and dependency-free. It is a
bridge until a tenant-isolated embedding/vector index is introduced. It ranks
existing extracted chunks by lexical relevance and always preserves attachment
provenance.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "what",
    "calculate", "calculate", "please", "provide", "required", "engineering",
}


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9_]+", (text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def retrieve_relevant_chunks(
    query: str,
    project_context: Dict[str, Any] | None,
    *,
    max_chunks: int = 12,
) -> List[Dict[str, Any]]:
    """Return the highest-overlap extracted chunks with provenance."""
    context = project_context or {}
    query_tokens = _tokens(query)
    candidates: List[tuple[int, int, Dict[str, Any]]] = []

    for document in context.get("documents") or []:
        if not isinstance(document, dict):
            continue
        for chunk in document.get("chunks") or []:
            if not isinstance(chunk, dict):
                continue
            text = str(chunk.get("text") or "")
            if not text:
                continue
            overlap = len(query_tokens & _tokens(text))
            # Exact numeric/unit mentions are valuable engineering evidence.
            query_numbers = set(re.findall(r"\d+(?:\.\d+)?", query))
            chunk_numbers = set(re.findall(r"\d+(?:\.\d+)?", text))
            overlap += 2 * len(query_numbers & chunk_numbers)
            if overlap <= 0:
                continue
            candidates.append((
                overlap,
                -int(chunk.get("index", 0)),
                {
                    "attachment_id": document.get("attachment_id"),
                    "filename": document.get("filename"),
                    "sha256": document.get("sha256"),
                    "source_type": document.get("source_type"),
                    "chunk_id": chunk.get("chunk_id"),
                    "chunk_index": chunk.get("index"),
                    "text": text,
                    "metadata": chunk.get("metadata") or {},
                    "retrieval": {"method": "lexical_v1", "score": overlap},
                },
            ))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in candidates[:max_chunks]]


def build_ai_project_context(query: str, project_context: Dict[str, Any] | None) -> Dict[str, Any]:
    """Create bounded context for the AI interpreter without losing source metadata."""
    context = dict(project_context or {})
    evidence = retrieve_relevant_chunks(query, context)
    context["retrieved_evidence"] = evidence
    return context


__all__ = ["retrieve_relevant_chunks", "build_ai_project_context"]
