"""Environment-based provider selection with safe deterministic fallback."""
from __future__ import annotations

import os

from orchestrator.provider import ProviderUnavailableError
from orchestrator.intake import RuleBasedIntentProvider


def build_intent_provider():
    mode = os.getenv("ENGINEERING_AI_INTENT_PROVIDER", "rule_based").strip().lower()
    if mode != "openai":
        return RuleBasedIntentProvider()
    try:
        from orchestrator.openai_provider import OpenAIIntentProvider
        return OpenAIIntentProvider()
    except ProviderUnavailableError:
        raise
