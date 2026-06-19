"""
Gemini / AntiGravity CLI log provider.

Parses JSONL transcript files from the AntiGravity log directory.
Ported from GeminiLogDashboard_v1 and adapted to the LogProvider interface.

Log path (default): ~/.gemini/antigravity/brain/
Format: one JSONL file per session; each line is a turn with fields:
    source, type, content, created_at, step_index
Token counts: NOT in log — requires google-generativeai SDK count_tokens() call.
Model detection: regex on USER turn content for USER_SETTINGS_CHANGE events.
"""

import os
import re
import json
import hashlib
from typing import Optional

from ..base import LogProvider, SessionMeta, CanonicalTurn, PricingRate
from src.database.schema import get_setting
from src.database.connection import get_connection


SETTINGS_CHANGE_PATTERN = re.compile(
    r"changed setting `?Model Selection`? from (?:.*?) to `?([^`\.\n]+)",
    re.IGNORECASE
)

# Role mapping from Gemini source values to canonical roles
ROLE_MAP = {
    "USER": "user",
    "USER_EXPLICIT": "user",
    "MODEL": "assistant",
    "SYSTEM": "system",
}

# Module-level cache for the GenerativeModel instance
_genai_model = None
_active_api_key = None


def _extract_model_change(content: str) -> Optional[str]:
    """Parses a model selection change from USER_SETTINGS_CHANGE content."""
    if not content:
        return None
    match = SETTINGS_CHANGE_PATTERN.search(content)
    if not match:
        return None
    val = match.group(1).strip().strip("'\"`().")
    val = val.split(".")[0].split(" (")[0]
    return val.strip() or None


class GeminiProvider(LogProvider):
    provider_id = "gemini"
    display_name = "Antigravity / Gemini"
    capabilities = {"model_switching"}

    def discover_sessions(self, log_dir: str) -> list[SessionMeta]:
        """Scans log_dir for .jsonl session files."""
        sessions = []
        if not log_dir or not os.path.isdir(log_dir):
            return sessions
        for fname in os.listdir(log_dir):
            if not fname.endswith(".jsonl"):
                continue
            file_path = os.path.join(log_dir, fname)
            stat = os.stat(file_path)
            session_id = fname.replace(".jsonl", "")
            sessions.append(SessionMeta(
                session_id=session_id,
                file_path=file_path,
                project_path=log_dir,
                file_size=stat.st_size,
                last_modified=stat.st_mtime,
            ))
        return sessions

    def parse_turns(self, session_meta: SessionMeta, start_line: int) -> list[CanonicalTurn]:
        """
        Parses new lines from the Gemini JSONL file starting at start_line.

        Gemini logs do not include token counts, so this method estimates them via
        count_tokens() (SDK call with SQLite cache, heuristic fallback).
        Context accumulates across turns so input_tokens on each assistant turn
        reflects the full prompt sent to the model up to that point.
        """
        turns = []
        session_id = session_meta.session_id
        current_line = 0
        current_model = ""
        context_tokens = 0

        if not os.path.exists(session_meta.file_path):
            return turns

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
                    except json.JSONDecodeError as e:
                        print(f"[GeminiProvider] Skipping malformed JSON on line {current_line}: {e}")
                        current_line += 1
                        continue

                    source = event.get("source", "")
                    raw_type = event.get("type", source)
                    content = event.get("content", "") or ""
                    created_at = event.get("created_at", "")

                    model_change = _extract_model_change(content)
                    if model_change:
                        current_model = model_change

                    role = ROLE_MAP.get(source, "system")
                    content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
                    turn_tokens = self.count_tokens(content)

                    if role == "assistant":
                        input_tokens = context_tokens
                        output_tokens = turn_tokens
                    else:
                        input_tokens = turn_tokens
                        output_tokens = 0

                    context_tokens += turn_tokens

                    pricing = self.get_pricing(current_model)
                    cost = (
                        (input_tokens * pricing.input_rate / 1_000_000) +
                        (output_tokens * pricing.output_rate / 1_000_000)
                    )

                    turns.append(CanonicalTurn(
                        turn_id=f"{session_id}_{current_line}",
                        session_id=session_id,
                        provider=self.provider_id,
                        sequence_index=current_line,
                        role=role,
                        raw_type=raw_type,
                        content=content,
                        content_hash=content_hash,
                        model=current_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost,
                        created_at=created_at,
                    ))

                    current_line += 1

        except Exception as e:
            print(f"[GeminiProvider] Error reading {session_meta.file_path}: {e}")

        return turns

    def get_pricing(self, model_name: str) -> PricingRate:
        """Returns pricing rates from settings for the given Gemini model tier."""
        model_lower = model_name.lower()
        if "pro" in model_lower:
            return PricingRate(
                input_rate=float(get_setting("gemini_pro_input_rate", "1.25")),
                output_rate=float(get_setting("gemini_pro_output_rate", "5.00")),
            )
        return PricingRate(
            input_rate=float(get_setting("gemini_flash_input_rate", "0.075")),
            output_rate=float(get_setting("gemini_flash_output_rate", "0.30")),
        )

    def _get_genai_model(self):
        """Returns a cached GenerativeModel, re-initialising if the API key changed."""
        global _genai_model, _active_api_key
        api_key = get_setting("gemini_api_key", "")
        if not api_key:
            _genai_model = None
            _active_api_key = None
            return None
        if _genai_model is None or _active_api_key != api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                _genai_model = genai.GenerativeModel("gemini-1.5-flash")
                _active_api_key = api_key
            except Exception as e:
                print(f"[GeminiProvider] Error configuring Gemini SDK: {e}")
                _genai_model = None
                _active_api_key = None
        return _genai_model

    def count_tokens(self, text: str) -> int:
        """
        Counts tokens via the google-generativeai SDK with a SQLite cache.
        Falls back to a character-based estimate (~4 chars/token) when the API
        key is absent or the SDK call fails.
        """
        if not text:
            return 0

        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT token_count FROM token_cache WHERE text_hash = ?",
                    (text_hash,),
                ).fetchone()
                if row:
                    return row["token_count"]
        except Exception as e:
            print(f"[GeminiProvider] DB error reading token_cache: {e}")

        token_count = None
        model = self._get_genai_model()
        if model:
            try:
                response = model.count_tokens(text)
                token_count = response.total_tokens
            except Exception as e:
                print(f"[GeminiProvider] SDK token count failed, falling back to heuristic: {e}")

        if token_count is None:
            token_count = max(1, len(text) // 4)

        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO token_cache (text_hash, token_count) VALUES (?, ?)",
                    (text_hash, token_count),
                )
        except Exception as e:
            print(f"[GeminiProvider] DB error writing token_cache: {e}")

        return token_count
