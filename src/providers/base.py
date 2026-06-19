"""
LogProvider base class and canonical data types.

Every AI tool provider implements LogProvider. The ingestion pipeline calls
discover_sessions() and parse_turns() only — everything else is provider-internal.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionMeta:
    """Lightweight descriptor returned by discover_sessions()."""
    session_id: str
    file_path: str
    project_path: str
    file_size: int
    last_modified: float


@dataclass
class PricingRate:
    """Token pricing in USD per 1,000,000 tokens."""
    input_rate: float
    output_rate: float


@dataclass
class CanonicalTurn:
    """
    A single normalized turn, independent of provider log format.
    Cache fields are None for providers that do not support prompt caching.
    """
    turn_id: str
    session_id: str
    provider: str
    sequence_index: int
    role: str                          # "user" | "assistant" | "system" | "tool"
    raw_type: str                      # Provider-native event type
    content: str
    content_hash: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    created_at: str
    cache_creation_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    is_dismissed: int = 0


class LogProvider(ABC):
    """
    Abstract base class for all AI tool log providers.

    Subclasses must set provider_id, display_name, and capabilities,
    and implement discover_sessions() and parse_turns().
    """

    provider_id: str = ""
    display_name: str = ""

    # Declare which optional features this provider supports.
    # The UI renders panels conditionally based on these flags.
    capabilities: set[str] = set()
    #
    # Known capability flags:
    #   "native_token_counts"  - token counts are in the log (no API call needed)
    #   "native_title"         - provider supplies a session title in the log
    #   "cache_tokens"         - provider logs cache creation/read token counts
    #   "model_switching"      - sessions can change models mid-stream
    #   "tool_use_tracking"    - tool invocations are discrete logged events
    #   "git_branch"           - log entries include the active git branch

    @abstractmethod
    def discover_sessions(self, log_dir: str) -> list[SessionMeta]:
        """
        Scan log_dir and return metadata for all sessions found.
        Called by the ingestion loader on every rescan.
        """

    @abstractmethod
    def parse_turns(self, session_meta: SessionMeta, start_line: int) -> list[CanonicalTurn]:
        """
        Parse new turns from session_meta.file_path starting at start_line.
        Returns a list of CanonicalTurn dicts ready to be upserted into the DB.
        """

    def get_pricing(self, model_name: str) -> PricingRate:
        """
        Return USD/1M token rates for the given model name.
        Override in subclasses for provider-specific pricing logic.
        Default falls back to zero rates (safe — just means $0 cost shown).
        """
        return PricingRate(input_rate=0.0, output_rate=0.0)

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Override in subclasses that have SDK or API access for accurate counts.
        Default: character-based approximation (~4 chars per token).
        """
        return max(1, len(text) // 4)
