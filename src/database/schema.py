"""
Canonical database schema for AI Usage Dashboard.

All providers write to the same tables. The `provider` column is the only
segregation mechanism — no separate tables or schemas per provider.

Run init_db() once on startup. Schema migrations are handled via ALTER TABLE
guards (check column existence before adding).
"""

from .connection import get_connection


def init_db():
    """Creates all tables if they do not exist and runs any pending migrations."""
    with get_connection() as conn:

        # --- providers ---
        conn.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            provider_id     TEXT PRIMARY KEY,
            display_name    TEXT NOT NULL,
            log_directory   TEXT NOT NULL DEFAULT '',
            enabled         INTEGER NOT NULL DEFAULT 1,
            last_scanned_at TEXT NOT NULL DEFAULT ''
        );
        """)

        # --- sessions ---
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id           TEXT PRIMARY KEY,
            provider             TEXT NOT NULL,
            project_path         TEXT NOT NULL DEFAULT '',
            title                TEXT NOT NULL DEFAULT '',
            model                TEXT NOT NULL DEFAULT '',
            created_at           TEXT NOT NULL DEFAULT '',
            updated_at           TEXT NOT NULL DEFAULT '',
            turn_count           INTEGER NOT NULL DEFAULT 0,
            total_input_tokens   INTEGER NOT NULL DEFAULT 0,
            total_output_tokens  INTEGER NOT NULL DEFAULT 0,
            cache_input_tokens   INTEGER,
            cache_output_tokens  INTEGER,
            total_cost           REAL NOT NULL DEFAULT 0.0,
            efficiency_score     REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (provider) REFERENCES providers (provider_id)
        );
        """)

        # --- turns ---
        conn.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            turn_id               TEXT PRIMARY KEY,
            session_id            TEXT NOT NULL,
            provider              TEXT NOT NULL,
            sequence_index        INTEGER NOT NULL,
            role                  TEXT NOT NULL,
            raw_type              TEXT NOT NULL DEFAULT '',
            content               TEXT NOT NULL DEFAULT '',
            content_hash          TEXT NOT NULL DEFAULT '',
            model                 TEXT NOT NULL DEFAULT '',
            input_tokens          INTEGER NOT NULL DEFAULT 0,
            output_tokens         INTEGER NOT NULL DEFAULT 0,
            cache_creation_tokens INTEGER,
            cache_read_tokens     INTEGER,
            cost                  REAL NOT NULL DEFAULT 0.0,
            created_at            TEXT NOT NULL DEFAULT '',
            is_dismissed          INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        );
        """)

        # --- processed_files ---
        conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            file_path     TEXT PRIMARY KEY,
            provider      TEXT NOT NULL,
            file_size     INTEGER NOT NULL DEFAULT 0,
            file_hash     TEXT NOT NULL DEFAULT '',
            last_read_line INTEGER NOT NULL DEFAULT 0,
            last_modified REAL NOT NULL DEFAULT 0
        );
        """)

        # --- token_cache ---
        conn.execute("""
        CREATE TABLE IF NOT EXISTS token_cache (
            text_hash   TEXT PRIMARY KEY,
            token_count INTEGER NOT NULL
        );
        """)

        # --- settings ---
        conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        """)

        # Default settings
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gemini_api_key', '');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gemini_flash_input_rate', '0.075');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gemini_flash_output_rate', '0.30');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gemini_pro_input_rate', '1.25');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gemini_pro_output_rate', '5.00');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('claude_haiku_input_rate', '0.80');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('claude_haiku_output_rate', '4.00');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('claude_sonnet_input_rate', '3.00');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('claude_sonnet_output_rate', '15.00');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('claude_opus_input_rate', '15.00');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('claude_opus_output_rate', '75.00');")


def get_setting(key: str, default: str = "") -> str:
    """Retrieves a single setting value by key."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default
    except Exception:
        return default


def save_setting(key: str, value: str):
    """Upserts a setting value."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
