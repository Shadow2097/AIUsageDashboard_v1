# Architecture & Directory Structure

This document defines the tech stack, data model, component design, and directory
structure for the **AI Usage Dashboard (v1)**.

---

## Tech Stack

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.x | Consistent with GeminiLogDashboard_v1; strong ecosystem for data work |
| **Dashboard UI** | Streamlit | Rapid iteration; already proven in v1 |
| **Data Visualization** | Plotly | Interactive charts; dual-axis support; dark theme |
| **Datastore** | SQLite | Zero-config; file-based; sufficient for local log volumes |
| **Token Estimation** | Provider SDK or tiktoken fallback | Per-provider; Claude logs include usage natively |

---

## UI Structure

The dashboard uses a **two-level tab hierarchy**:

### Root Level — Provider Tabs
Each configured and enabled provider gets a top-level tab. A special tab appears
at the end when two or more providers have data.

```
[ Antigravity/Gemini ]  [ Claude Code ]  [ Cursor ]  [ 📊 Compare ]
```

### Provider Level — Feature Sub-Tabs
Every provider tab contains the same four sub-tabs. Provider-specific panels
are conditionally rendered based on the provider's declared capability flags.

```
[ 📈 Overview ]  [ 💬 Session Explorer ]  [ 💡 Advice ]  [ 🔍 Prompt Auditor ]
```

**Overview** — aggregate metrics for this provider: total sessions, total cost,
token volume, daily cost/token trend chart, session summary table.

**Session Explorer** — select a session; view context accumulation curve, full
conversation transcript, per-turn token and cost breakdown, heuristic warnings.

**Advice** — ranked list of optimization opportunities: pleasantry matches,
context debt spikes, high-cost turns. Each card is dismissible.

**Prompt Auditor** — paste a prompt; see raw token count, pleasantry flags, and
(if an API key is configured) an LLM-rewritten compressed version with token savings.

### Compare Tab (Phase 3)
Aggregate metrics only — no session content, no provider mixing in Explorer views.
Shows cross-provider spend, volume, efficiency rankings, and trend overlays.

---

## Canonical Data Model

All providers write to the same SQLite tables. The `provider` column is the only
segregation mechanism needed.

### `providers` table
Tracks registered providers and their configuration.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `provider_id` | TEXT PK | Slug: `gemini`, `claude-code`, `cursor` |
| `display_name` | TEXT | Shown in UI tabs |
| `log_directory` | TEXT | User-configured path |
| `enabled` | INTEGER | 0/1 |
| `last_scanned_at` | TEXT | ISO timestamp |

### `sessions` table

| Column | Type | Notes |
| :--- | :--- | :--- |
| `session_id` | TEXT PK | Provider-native ID (UUID or hash) |
| `provider` | TEXT | FK → providers.provider_id |
| `project_path` | TEXT | Working directory or project root |
| `title` | TEXT | Derived from first user turn or native title field |
| `model` | TEXT | Last known or dominant model for this session |
| `created_at` | TEXT | ISO timestamp of first turn |
| `updated_at` | TEXT | ISO timestamp of last turn |
| `turn_count` | INTEGER | |
| `total_input_tokens` | INTEGER | |
| `total_output_tokens` | INTEGER | |
| `cache_input_tokens` | INTEGER | Null for providers that don't support caching |
| `cache_output_tokens` | INTEGER | Null for providers that don't support caching |
| `total_cost` | REAL | USD |
| `efficiency_score` | REAL | output_tokens / input_tokens * 100 |

### `turns` table

| Column | Type | Notes |
| :--- | :--- | :--- |
| `turn_id` | TEXT PK | `{session_id}_{sequence_index}` |
| `session_id` | TEXT | FK → sessions.session_id |
| `provider` | TEXT | Denormalized for query performance |
| `sequence_index` | INTEGER | Order within session |
| `role` | TEXT | `user`, `assistant`, `system`, `tool` (canonical) |
| `raw_type` | TEXT | Provider-native event type, preserved for debugging |
| `content` | TEXT | |
| `content_hash` | TEXT | MD5 of content; used for token cache lookup |
| `model` | TEXT | Model active at this turn |
| `input_tokens` | INTEGER | |
| `output_tokens` | INTEGER | |
| `cache_creation_tokens` | INTEGER | Claude-specific; null otherwise |
| `cache_read_tokens` | INTEGER | Claude-specific; null otherwise |
| `cost` | REAL | USD for this turn |
| `created_at` | TEXT | ISO timestamp |
| `is_dismissed` | INTEGER | 0/1; used by Advice tab |

### `processed_files` table
Tracks ingestion state for incremental loading.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `file_path` | TEXT PK | Absolute path |
| `provider` | TEXT | |
| `file_size` | INTEGER | |
| `file_hash` | TEXT | MD5; detect truncation/reset |
| `last_read_line` | INTEGER | Resume point |
| `last_modified` | REAL | mtime |

### `token_cache` table
Avoids redundant token-count API calls for providers that require them.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `text_hash` | TEXT PK | MD5 of content |
| `token_count` | INTEGER | |

### `settings` table
Key-value store for user configuration.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `key` | TEXT PK | e.g. `gemini_api_key`, `claude_input_rate_sonnet` |
| `value` | TEXT | |

---

## Provider Plugin System

### Base Class (`src/providers/base.py`)

Every provider implements `LogProvider`:

```python
class LogProvider(ABC):
    provider_id: str        # "claude-code"
    display_name: str       # "Claude Code"
    capabilities: set[str]  # {"cache_tokens", "native_title", "tool_use_tracking"}

    @abstractmethod
    def discover_sessions(self, log_dir: str) -> list[SessionMeta]:
        """Scan log_dir and return metadata for all sessions found."""

    @abstractmethod
    def parse_turns(self, session_meta: SessionMeta, start_line: int) -> list[CanonicalTurn]:
        """Parse new turns from start_line onward. Returns canonical turn dicts."""

    def get_pricing(self, model_name: str) -> PricingRate:
        """Return $/1M input and output token rates for this model."""

    def count_tokens(self, text: str) -> int:
        """Count tokens for this provider. Default: character-based estimate."""
```

### Capability Flags
Providers declare what they support. The UI renders panels conditionally.

| Flag | Meaning |
| :--- | :--- |
| `cache_tokens` | Provider logs cache creation/read token counts (Claude) |
| `native_title` | Provider supplies a session title in the log (Claude `ai-title` event) |
| `native_token_counts` | Token counts are in the log; no API call needed (Claude) |
| `model_switching` | Sessions can change models mid-stream (Gemini) |
| `tool_use_tracking` | Tool invocations are logged as discrete events (Claude Code) |
| `git_branch` | Log entries include the active git branch (Claude Code) |

### Provider Registry (`src/providers/registry.py`)
Explicit registration list — no filesystem magic. Adding a provider means
importing it and adding one line to the registry.

```python
PROVIDERS: list[type[LogProvider]] = [
    GeminiProvider,
    ClaudeCodeProvider,
    # CursorProvider,  # uncomment when implemented
]
```

---

## Directory Structure

```
AIUsageDashboard_v1/
│
├── README.md
├── project_goals.md
├── architecture.md
├── providers.md               # Provider research: log formats, paths, status
├── requirements.txt
│
├── app.py                     # Streamlit entry point
│
├── src/
│   ├── __init__.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   └── schema.py          # Canonical schema; migrations via ALTER TABLE
│   │
│   ├── providers/
│   │   ├── base.py            # LogProvider ABC + CanonicalTurn + SessionMeta types
│   │   ├── registry.py        # PROVIDERS list + get_all_providers()
│   │   ├── gemini/
│   │   │   ├── __init__.py
│   │   │   └── provider.py    # GeminiProvider
│   │   └── claude_code/
│   │       ├── __init__.py
│   │       └── provider.py    # ClaudeCodeProvider
│   │
│   ├── ingestion/
│   │   └── loader.py          # Iterates registry; dispatches to providers; writes DB
│   │
│   └── metrics/
│       ├── cost_calculator.py # Provider-agnostic; uses provider.get_pricing()
│       └── heuristics.py      # Pleasantry detection; context debt; capability-aware
│
├── data/
│   └── dashboard.db           # SQLite (git-ignored)
│
└── tests/
    └── test_providers.py
```

---

## Key Flow

1. **Startup**: `init_db()` creates tables if absent; `ProviderRegistry` loads all providers.
2. **Ingestion**: For each enabled provider, `loader.py` calls `discover_sessions()`,
   checks `processed_files` for each file, calls `parse_turns()` for new lines only,
   runs cost calculation, and upserts into `sessions` and `turns`.
3. **UI**: `app.py` queries SQLite filtered by `provider`. Each provider tab calls
   the same render functions with its `provider_id` as a scope argument.
4. **Extensibility**: New provider = new folder under `src/providers/`, one class,
   one line in `registry.py`. No changes to schema, ingestion, metrics, or UI layout.
