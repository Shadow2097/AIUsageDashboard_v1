"""
Ingestion loader — provider-agnostic pipeline.

Iterates all registered providers, discovers sessions, loads new turns
incrementally, calculates session aggregates, and writes to SQLite.

Usage:
    from src.ingestion.loader import ingest_all, ingest_provider

    sessions_updated, turns_added = ingest_all()
    sessions_updated, turns_added = ingest_provider("claude-code")
"""

import hashlib
from src.database.connection import get_connection
from src.database.schema import get_setting
from src.providers.registry import get_all_providers, get_provider
from src.providers.base import LogProvider, SessionMeta


def _calculate_file_hash(file_path: str) -> str:
    """Returns MD5 hash of a file's contents."""
    md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
    except Exception:
        pass
    return md5.hexdigest()


def _get_file_state(file_path: str) -> dict | None:
    """Returns the processed_files row for a path, or None if not yet seen."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM processed_files WHERE file_path = ?", (file_path,)
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def _update_file_state(file_path: str, provider: str, file_size: int,
                       file_hash: str, last_read_line: int, last_modified: float):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO processed_files
                (file_path, provider, file_size, file_hash, last_read_line, last_modified)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_size      = excluded.file_size,
                file_hash      = excluded.file_hash,
                last_read_line = excluded.last_read_line,
                last_modified  = excluded.last_modified
        """, (file_path, provider, file_size, file_hash, last_read_line, last_modified))


def _get_log_dir(provider_id: str) -> str:
    """Reads the configured log directory for a provider from settings."""
    return get_setting(f"{provider_id}_log_directory", "")


def _upsert_turns(turns: list, session_id: str):
    """Upserts a list of CanonicalTurn objects into the turns table."""
    with get_connection() as conn:
        for t in turns:
            conn.execute("""
                INSERT INTO turns (
                    turn_id, session_id, provider, sequence_index, role, raw_type,
                    content, content_hash, model, input_tokens, output_tokens,
                    cache_creation_tokens, cache_read_tokens, cost, created_at, is_dismissed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(turn_id) DO UPDATE SET
                    content               = excluded.content,
                    content_hash          = excluded.content_hash,
                    model                 = excluded.model,
                    input_tokens          = excluded.input_tokens,
                    output_tokens         = excluded.output_tokens,
                    cache_creation_tokens = excluded.cache_creation_tokens,
                    cache_read_tokens     = excluded.cache_read_tokens,
                    cost                  = excluded.cost
            """, (
                t.turn_id, t.session_id, t.provider, t.sequence_index,
                t.role, t.raw_type, t.content, t.content_hash, t.model,
                t.input_tokens, t.output_tokens,
                t.cache_creation_tokens, t.cache_read_tokens,
                t.cost, t.created_at, t.is_dismissed,
            ))


def _upsert_session_aggregates(session_id: str, provider: str,
                                project_path: str, title: str):
    """Recalculates and saves session-level aggregate columns from turns."""
    with get_connection() as conn:
        agg = conn.execute("""
            SELECT
                COUNT(*)                          AS turn_count,
                MIN(created_at)                   AS created_at,
                MAX(created_at)                   AS updated_at,
                MAX(model)                        AS model,
                SUM(input_tokens)                 AS total_input,
                SUM(output_tokens)                AS total_output,
                SUM(COALESCE(cache_creation_tokens, 0)) AS cache_input,
                SUM(COALESCE(cache_read_tokens, 0))     AS cache_output,
                SUM(cost)                         AS total_cost
            FROM turns WHERE session_id = ?
        """, (session_id,)).fetchone()

        if not agg or agg["turn_count"] == 0:
            return

        total_input = agg["total_input"] or 0
        total_output = agg["total_output"] or 0
        efficiency = (total_output / max(1, total_input)) * 100.0

        conn.execute("""
            INSERT INTO sessions (
                session_id, provider, project_path, title, model,
                created_at, updated_at, turn_count,
                total_input_tokens, total_output_tokens,
                cache_input_tokens, cache_output_tokens,
                total_cost, efficiency_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                title               = excluded.title,
                model               = excluded.model,
                updated_at          = excluded.updated_at,
                turn_count          = excluded.turn_count,
                total_input_tokens  = excluded.total_input_tokens,
                total_output_tokens = excluded.total_output_tokens,
                cache_input_tokens  = excluded.cache_input_tokens,
                cache_output_tokens = excluded.cache_output_tokens,
                total_cost          = excluded.total_cost,
                efficiency_score    = excluded.efficiency_score
        """, (
            session_id, provider, project_path, title,
            agg["model"] or "",
            agg["created_at"] or "", agg["updated_at"] or "",
            agg["turn_count"],
            total_input, total_output,
            agg["cache_input"], agg["cache_output"],
            agg["total_cost"] or 0.0, efficiency,
        ))


def _derive_title(turns: list) -> str:
    """Extracts a session title from the first user turn."""
    for t in turns:
        if t.role == "user" and t.content:
            first_line = t.content.split("\n")[0].strip()
            # Strip XML-style tags that Claude Code wraps commands in
            import re
            first_line = re.sub(r"<[^>]+>", "", first_line).strip()
            if first_line:
                return first_line[:60] + ("..." if len(first_line) > 60 else "")
    return "Untitled Session"


def ingest_provider(provider_id: str) -> tuple[int, int]:
    """Runs incremental ingestion for a single provider. Returns (sessions, turns)."""
    provider = get_provider(provider_id)
    if not provider:
        return 0, 0

    log_dir = _get_log_dir(provider_id)
    if not log_dir:
        return 0, 0

    sessions_updated = 0
    turns_added = 0

    for session_meta in provider.discover_sessions(log_dir):
        file_path = session_meta.file_path
        current_hash = _calculate_file_hash(file_path)
        state = _get_file_state(file_path)

        start_line = 0
        if state:
            if (current_hash == state["file_hash"] and
                    session_meta.file_size >= state["file_size"]):
                start_line = state["last_read_line"]

        new_turns = provider.parse_turns(session_meta, start_line)

        if not new_turns and start_line > 0:
            continue  # File unchanged

        if new_turns:
            sessions_updated += 1
            turns_added += len(new_turns)

            # Ensure session header row exists before upserting turns
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO sessions
                        (session_id, provider, project_path, created_at, updated_at)
                    VALUES (?, ?, ?, '', '')
                """, (session_meta.session_id, provider_id, session_meta.project_path))

            _upsert_turns(new_turns, session_meta.session_id)

            # Derive title from all turns for this session
            with get_connection() as conn:
                all_turn_rows = conn.execute(
                    "SELECT role, content FROM turns WHERE session_id = ? ORDER BY sequence_index",
                    (session_meta.session_id,)
                ).fetchall()

            # Reuse _derive_title with lightweight objects
            class _T:
                def __init__(self, r): self.role = r["role"]; self.content = r["content"]
            title = _derive_title([_T(r) for r in all_turn_rows])

            _upsert_session_aggregates(
                session_meta.session_id, provider_id,
                session_meta.project_path, title
            )

        total_lines = start_line + len(new_turns)
        _update_file_state(
            file_path, provider_id, session_meta.file_size,
            current_hash, total_lines, session_meta.last_modified
        )

    return sessions_updated, turns_added


def ingest_all() -> tuple[int, int]:
    """Runs incremental ingestion for all registered providers."""
    total_sessions = 0
    total_turns = 0
    for provider in get_all_providers():
        s, t = ingest_provider(provider.provider_id)
        total_sessions += s
        total_turns += t
    return total_sessions, total_turns
