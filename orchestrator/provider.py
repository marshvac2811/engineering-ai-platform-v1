"""Provider-neutral intent-planning protocol.

External LLM/agent providers should implement `IntentProvider`. The rest of the
platform only depends on the structured routing contract, so changing providers
does not change the engineering skills or job lifecycle.
"""
from __future__ import annotations
from typing import Any, Dict, Optional, Protocol


class StructuredIntentProvider(Protocol):
    name: str

    def classify_and_extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return JSON-like data containing skill_id, confidence and inputs."""
        ...


class ProviderUnavailableError(RuntimeError):
    pass
