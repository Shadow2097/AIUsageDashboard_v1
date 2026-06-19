"""
Provider registry.

Add a new provider by importing its class and appending it to PROVIDERS.
No other file needs to change.
"""

from .base import LogProvider
from .gemini.provider import GeminiProvider
from .claude_code.provider import ClaudeCodeProvider
from .codex.provider import CodexProvider

PROVIDERS: list[type[LogProvider]] = [
    GeminiProvider,
    ClaudeCodeProvider,
    CodexProvider,
]


def get_all_providers() -> list[LogProvider]:
    """Returns instantiated provider objects for all registered providers."""
    return [p() for p in PROVIDERS]


def get_provider(provider_id: str) -> LogProvider | None:
    """Returns an instantiated provider by its provider_id, or None if not found."""
    for p in PROVIDERS:
        instance = p()
        if instance.provider_id == provider_id:
            return instance
    return None
