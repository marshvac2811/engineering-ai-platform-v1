"""Environment-based provider selection with safe deterministic fallback."""
from __future__ import annotations

import os

from orchestrator.provider import ProviderUnavailableError
from orchestrator.intake import RuleBasedIntentProvider


def build_intent_provider():
    mode = os.getenv("ENGINEERING_AI_INTENT_PROVIDER", "auto").strip().lower()
    if mode == "rule_based":
        return RuleBasedIntentProvider()
    if mode in {"auto", "openai"}:
        # AI is the primary interpretation layer when configured. The fallback
        # remains deterministic and never fabricates an engineering result.
        if mode == "auto" and not os.getenv("OPENAI_API_KEY"):
            return RuleBasedIntentProvider()
        from orchestrator.openai_provider import OpenAIIntentProvider
        return OpenAIIntentProvider()
    raise ValueError(f"Unsupported ENGINEERING_AI_INTENT_PROVIDER: {mode}")
