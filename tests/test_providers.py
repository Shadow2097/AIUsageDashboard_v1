"""Basic smoke tests for provider pipeline."""

import pytest
from src.providers.claude_code.provider import ClaudeCodeProvider
from src.providers.gemini.provider import GeminiProvider
from src.providers.registry import get_all_providers, get_provider


def test_registry_loads_all_providers():
    providers = get_all_providers()
    ids = [p.provider_id for p in providers]
    assert "gemini" in ids
    assert "claude-code" in ids


def test_get_provider_by_id():
    provider = get_provider("claude-code")
    assert provider is not None
    assert provider.display_name == "Claude Code"


def test_claude_code_capabilities():
    provider = ClaudeCodeProvider()
    assert "native_token_counts" in provider.capabilities
    assert "cache_tokens" in provider.capabilities


def test_claude_code_pricing_sonnet():
    provider = ClaudeCodeProvider()
    rate = provider.get_pricing("claude-sonnet-4-6")
    assert rate.input_rate > 0
    assert rate.output_rate > 0


def test_claude_code_pricing_opus():
    provider = ClaudeCodeProvider()
    rate = provider.get_pricing("claude-opus-4")
    assert rate.input_rate >= rate.output_rate / 10  # Opus is more expensive


def test_claude_code_discover_sessions_empty_dir(tmp_path):
    provider = ClaudeCodeProvider()
    sessions = provider.discover_sessions(str(tmp_path))
    assert sessions == []


def test_claude_code_parse_turns_empty_file(tmp_path):
    provider = ClaudeCodeProvider()
    session_file = tmp_path / "test-project" / "abc123.jsonl"
    session_file.parent.mkdir()
    session_file.write_text("")

    from src.providers.base import SessionMeta
    meta = SessionMeta(
        session_id="abc123",
        file_path=str(session_file),
        project_path=str(tmp_path),
        file_size=0,
        last_modified=0.0,
    )
    turns = provider.parse_turns(meta, start_line=0)
    assert turns == []
