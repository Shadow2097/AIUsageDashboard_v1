"""
Codex log provider.

Parses JSONL session files written by OpenAI's Codex Desktop / CLI.

Log path: ~/.codex/sessions/{year}/{month}/{day}/
Format: typed event objects; turns are bracketed by task_started / task_complete pairs.

Token counts: NATIVE — token_count events carry cumulative input/output/cached counts
  for the entire turn (including all tool-call round-trips).

Model: turn_context event, model field (e.g. gpt-5.5, gpt-5.4-mini).
Title: derived from first user message (no native title event).

Key event types parsed:
    session_meta             — session ID, cwd, model_provider, timestamp
    event_msg/task_started   — turn boundary open; yields turn_id, started_at
    event_msg/user_message   — user message text (payload.message)
    turn_context             — model name for the current turn
    event_msg/token_count    — cumulative token usage; last-seen value used per turn
    event_msg/task_complete  — turn boundary close; last_agent_message is assistant content

Event types intentionally skipped:
    response_item/reasoning          — encrypted; not readable
    response_item/function_call      — tool call details; not needed for accounting
    response_item/function_call_output — tool outputs
    event_msg/agent_message          — interim commentary; task_complete has the final text
    response_item/message role=developer — system/environment context
"""

import os
import re
import json
import hashlib
from datetime import datetime, timezone

from ..base import LogProvider, SessionMeta, CanonicalTurn, PricingRate
from src.database.schema import get_setting


_SESSION_ID_RE = re.compile(
    r"^rollout-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-(.+)$"
)


class CodexProvider(LogProvider):
    provider_id = "codex"
    display_name = "Codex"
    capabilities = {
        "native_token_counts",
        "cache_tokens",
    }

    def discover_sessions(self, log_dir: str) -> list[SessionMeta]:
        sessions = []
        if not log_dir or not os.path.isdir(log_dir):
            return sessions

        for root, _dirs, files in os.walk(log_dir):
            for fname in sorted(files):
                if not fname.endswith(".jsonl"):
                    continue

                fpath = os.path.join(root, fname)
                try:
                    stat = os.stat(fpath)
                except OSError:
                    continue

                # Extract session UUID from filename
                stem = fname[:-6]  # strip .jsonl
                m = _SESSION_ID_RE.match(stem)
                session_id = m.group(1) if m else stem

                # Read only the first line for cwd; avoids loading entire file
                project_path = ""
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        first = f.readline().strip()
                    if first:
                        meta = json.loads(first)
                        if meta.get("type") == "session_meta":
                            project_path = meta.get("payload", {}).get("cwd", "")
                except Exception:
                    pass

                sessions.append(SessionMeta(
                    session_id=session_id,
                    file_path=fpath,
                    project_path=project_path,
                    file_size=stat.st_size,
                    last_modified=stat.st_mtime,
                ))

        return sessions

    def parse_turns(self, session_meta: SessionMeta, start_line: int) -> list[CanonicalTurn]:
        turns: list[CanonicalTurn] = []
        session_id = session_meta.session_id

        # State for the current in-progress turn; reset on each task_complete
        turn: dict | None = None
        turn_seq = 0

        try:
            with open(session_meta.file_path, "r", encoding="utf-8") as f:
                for line_num, raw_line in enumerate(f):
                    if line_num < start_line:
                        continue

                    stripped = raw_line.strip()
                    if not stripped:
                        continue

                    try:
                        event = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue

                    etype   = event.get("type", "")
                    payload = event.get("payload", {}) or {}
                    ptype   = payload.get("type", "")
                    ts      = event.get("timestamp", "")

                    # ── Turn open ────────────────────────────────────────────
                    if etype == "event_msg" and ptype == "task_started":
                        turn = {
                            "turn_id":    payload.get("turn_id", f"{session_id}_{line_num}"),
                            "started_at": payload.get("started_at", 0),
                            "user_msg":   "",
                            "user_ts":    ts,
                            "model":      "",
                            "tok":        {},
                            "line_num":   line_num,
                            "seq":        turn_seq,
                        }
                        continue

                    # Skip events that arrive before the first task_started
                    if turn is None:
                        continue

                    # ── Model name ───────────────────────────────────────────
                    if etype == "turn_context":
                        turn["model"] = payload.get("model", "") or turn["model"]
                        continue

                    # ── User message ─────────────────────────────────────────
                    # event_msg/user_message carries the cleanest user text
                    if etype == "event_msg" and ptype == "user_message":
                        msg = (payload.get("message") or "").strip()
                        if msg and not turn["user_msg"]:
                            turn["user_msg"] = msg
                            turn["user_ts"]  = ts
                        continue

                    # ── Cumulative token tracking ────────────────────────────
                    # token_count fires after every API call; keep the last one
                    if etype == "event_msg" and ptype == "token_count":
                        info = payload.get("info") or {}
                        if "total_token_usage" in info:
                            turn["tok"] = info["total_token_usage"]
                        continue

                    # ── Turn close ───────────────────────────────────────────
                    if etype == "event_msg" and ptype == "task_complete":
                        agent_msg    = (payload.get("last_agent_message") or "").strip()
                        completed_at = payload.get("completed_at", 0)
                        model        = turn["model"]
                        tok          = turn["tok"]

                        input_tok  = tok.get("input_tokens",        0) or 0
                        output_tok = tok.get("output_tokens",       0) or 0
                        cached_tok = tok.get("cached_input_tokens", 0) or 0

                        pricing = self.get_pricing(model)
                        cost = (
                            input_tok  * pricing.input_rate  / 1_000_000
                            + output_tok * pricing.output_rate / 1_000_000
                        )

                        asst_ts = (
                            datetime.fromtimestamp(completed_at, tz=timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%S.000Z")
                            if completed_at else ts
                        )

                        # User turn — no tokens (all usage is billed on the assistant side)
                        user_text = turn["user_msg"]
                        if user_text:
                            uid = f"{session_id}_{turn['line_num']}_u"
                            turns.append(CanonicalTurn(
                                turn_id=uid,
                                session_id=session_id,
                                provider=self.provider_id,
                                sequence_index=turn["seq"] * 2,
                                role="user",
                                raw_type="user_message",
                                content=user_text,
                                content_hash=hashlib.md5(user_text.encode()).hexdigest(),
                                model="",
                                input_tokens=0,
                                output_tokens=0,
                                cost=0.0,
                                created_at=turn["user_ts"],
                            ))

                        # Assistant turn — carries all token counts for the full turn
                        if agent_msg:
                            aid = f"{session_id}_{turn['line_num']}_a"
                            turns.append(CanonicalTurn(
                                turn_id=aid,
                                session_id=session_id,
                                provider=self.provider_id,
                                sequence_index=turn["seq"] * 2 + 1,
                                role="assistant",
                                raw_type="task_complete",
                                content=agent_msg,
                                content_hash=hashlib.md5(agent_msg.encode()).hexdigest(),
                                model=model,
                                input_tokens=input_tok,
                                output_tokens=output_tok,
                                cache_read_tokens=cached_tok if cached_tok else None,
                                cost=cost,
                                created_at=asst_ts,
                            ))

                        turn_seq += 1
                        turn = None

        except Exception as e:
            print(f"[CodexProvider] Error reading {session_meta.file_path}: {e}")

        return turns

    def get_pricing(self, model_name: str) -> PricingRate:
        model_lower = (model_name or "").lower()
        if "mini" in model_lower:
            return PricingRate(
                input_rate=float(get_setting("codex_mini_input_rate", "0.0")),
                output_rate=float(get_setting("codex_mini_output_rate", "0.0")),
            )
        return PricingRate(
            input_rate=float(get_setting("codex_input_rate", "0.0")),
            output_rate=float(get_setting("codex_output_rate", "0.0")),
        )
