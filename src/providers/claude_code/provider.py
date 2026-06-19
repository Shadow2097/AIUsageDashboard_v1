"""
Claude Code log provider.

Parses JSONL session files written by the Claude Code CLI tool.

Log path: ~/.claude/projects/**/*.jsonl
  Windows: C:\\Users\\{user}\\.claude\\projects\\

Directory structure:
  Each subdirectory under projects/ represents a project (named after the
  working directory path with slashes replaced by dashes). Each .jsonl file
  within a project directory is one session, named by session UUID.

Format: typed event objects; each line is a JSON object with a `type` field.
Token counts: NATIVE — `message.usage` in every `assistant` event includes:
    input_tokens, output_tokens,
    cache_creation_input_tokens, cache_read_input_tokens
Model: `message.model` field on assistant events.
Title: native `ai-title` event type.
Project path: `cwd` field on user/assistant events.
Git branch: `gitBranch` field on user/assistant events.

Key event types parsed:
    user       — user message turn
    assistant  — model response turn (contains usage + content)
    ai-title   — auto-generated session title (first occurrence wins)

Event types intentionally skipped:
    attachment, file-history-snapshot, mode, permission-mode, last-prompt
"""

import os
import json
import hashlib

from ..base import LogProvider, SessionMeta, CanonicalTurn, PricingRate
from src.database.schema import get_setting

# Assistant message content block types to extract text from
TEXT_BLOCK_TYPES = {"text", "thinking"}

# Event types that carry conversation content worth storing
TURN_EVENT_TYPES = {"user", "assistant"}

# Event types to skip entirely during parsing
SKIP_EVENT_TYPES = {
    "attachment", "file-history-snapshot", "mode",
    "permission-mode", "last-prompt", "skill_listing",
}


class ClaudeCodeProvider(LogProvider):
    provider_id = "claude-code"
    display_name = "Claude Code"
    capabilities = {
        "native_token_counts",
        "native_title",
        "cache_tokens",
        "tool_use_tracking",
        "git_branch",
    }

    def discover_sessions(self, log_dir: str) -> list[SessionMeta]:
        """
        Recursively scans log_dir for *.jsonl session files.
        Claude Code organises files as:
            {log_dir}/{project-slug}/{session-uuid}.jsonl
        """
        sessions = []
        if not log_dir or not os.path.isdir(log_dir):
            return sessions

        for project_dir in os.scandir(log_dir):
            if not project_dir.is_dir():
                continue
            for entry in os.scandir(project_dir.path):
                if not entry.name.endswith(".jsonl") or not entry.is_file():
                    continue
                stat = entry.stat()
                session_id = entry.name.replace(".jsonl", "")
                # Derive human-readable project path from the directory name
                project_path = project_dir.name.replace("-", os.sep).replace("--", ":")
                sessions.append(SessionMeta(
                    session_id=session_id,
                    file_path=entry.path,
                    project_path=project_path,
                    file_size=stat.st_size,
                    last_modified=stat.st_mtime,
                ))
        return sessions

    def parse_turns(self, session_meta: SessionMeta, start_line: int) -> list[CanonicalTurn]:
        """
        Parses new lines from a Claude Code JSONL session file.
        Token counts, model name, and cache data are extracted directly
        from the `message.usage` field — no API call required.
        """
        turns = []
        session_id = session_meta.session_id
        current_line = 0

        try:
            with open(session_meta.file_path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    if current_line < start_line:
                        current_line += 1
                        continue

                    line_str = raw_line.strip()
                    if not line_str:
                        current_line += 1
                        continue

                    try:
                        event = json.loads(line_str)
                    except json.JSONDecodeError:
                        current_line += 1
                        continue

                    event_type = event.get("type", "")

                    if event_type in SKIP_EVENT_TYPES:
                        current_line += 1
                        continue

                    if event_type not in TURN_EVENT_TYPES:
                        current_line += 1
                        continue

                    turn = self._parse_turn_event(event, session_id, current_line)
                    if turn:
                        turns.append(turn)

                    current_line += 1

        except Exception as e:
            print(f"[ClaudeCodeProvider] Error reading {session_meta.file_path}: {e}")

        return turns

    def _parse_turn_event(
        self, event: dict, session_id: str, line_index: int
    ) -> CanonicalTurn | None:
        """Converts a single user or assistant event to a CanonicalTurn."""
        event_type = event.get("type", "")
        timestamp = event.get("timestamp", "")
        message = event.get("message", {})

        # Extract content text
        raw_content = message.get("content", "")
        if isinstance(raw_content, list):
            # Content is a list of typed blocks (text, thinking, tool_use, etc.)
            content = "\n".join(
                block.get("text", block.get("thinking", ""))
                for block in raw_content
                if isinstance(block, dict) and block.get("type") in TEXT_BLOCK_TYPES
            ).strip()
        else:
            content = str(raw_content) if raw_content else ""

        if not content:
            return None

        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

        # Token counts — native from message.usage (assistant turns only)
        usage = message.get("usage", {})
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        cache_creation = usage.get("cache_creation_input_tokens", None)
        cache_read = usage.get("cache_read_input_tokens", None)

        # Model
        model = message.get("model", "")

        # Cost
        pricing = self.get_pricing(model)
        cost = 0.0
        if event_type == "assistant" and input_tokens > 0:
            cost = (
                (input_tokens * pricing.input_rate / 1_000_000) +
                (output_tokens * pricing.output_rate / 1_000_000)
            )

        # Canonical role
        role = "user" if event_type == "user" else "assistant"

        turn_id = f"{session_id}_{line_index}"

        return CanonicalTurn(
            turn_id=turn_id,
            session_id=session_id,
            provider=self.provider_id,
            sequence_index=line_index,
            role=role,
            raw_type=event_type,
            content=content,
            content_hash=content_hash,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
            cost=cost,
            created_at=timestamp,
        )

    def get_pricing(self, model_name: str) -> PricingRate:
        """Returns pricing rates from settings based on the Claude model tier."""
        model_lower = model_name.lower()
        if "opus" in model_lower:
            return PricingRate(
                input_rate=float(get_setting("claude_opus_input_rate", "15.00")),
                output_rate=float(get_setting("claude_opus_output_rate", "75.00")),
            )
        if "haiku" in model_lower:
            return PricingRate(
                input_rate=float(get_setting("claude_haiku_input_rate", "0.80")),
                output_rate=float(get_setting("claude_haiku_output_rate", "4.00")),
            )
        # Default: Sonnet
        return PricingRate(
            input_rate=float(get_setting("claude_sonnet_input_rate", "3.00")),
            output_rate=float(get_setting("claude_sonnet_output_rate", "15.00")),
        )
