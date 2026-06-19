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
| **Token Estimation** | Provider SDK or character-based fallback | Per-provider; Claude and Codex logs include usage natively |
| **LLM Compression** | anthropic SDK (Haiku) / google-generativeai (Flash) | Prompt Auditor rewrite feature |

---

## UI Structure

The dashboard uses a **two-level tab hierarchy**:

### Root Level — Provider Tabs
Each configured and enabled provider gets a top-level tab. The Compare tab appears
automatically when two or more providers have ingested data.

```
[ Gemini ]  [ Claude Code ]  [ Codex ]  [ Devin ]  [ ⚖️ Compare ]
```

Tabs with no configured log directory and no existing data are hidden from the root level.

### Provider Level — Feature Sub-Tabs
Every provider tab contains the same four sub-tabs. Provider-specific panels
are conditionally rendered based on the provider's declared capability flags.

```
[ 📈 Overview ]  [ 💬 Session Explorer ]  [ 💡 Advice ]  [ 🔍 Prompt Auditor ]
```

**Overview** — aggregate metrics for this provider: total sessions, total cost,
token volume, daily cost/token trend chart with session-count annotations,
session summary table.

**Session Explorer** — select a session; view context accumulation curve, full
conversation transcript, per-turn token and cost breakdown, heuristic warnings inline.

**Advice** — sorted list of optimization opportunities across three card types:
- ⚠️ **Pleasantry** (amber) — user turns with low-signal phrases
- 🚨 **Context Debt** (red) — turns where context > 80% of context window
- 💸 **High Cost** (purple) — turns with cost > $0.05

Each card is dismissible. A summary banner shows total count by type and aggregate
cost exposure.

**Prompt Auditor** — paste a prompt; see raw token count, pleasantry flags, and
cost projection. If an API key is configured, **✨ Compress with AI** rewrites the
prompt with an LLM and shows before/after token savings. Result persists in
`st.session_state` across Streamlit rerenders.

### Compare Tab (Phase 3)
Aggregate metrics only — no session content. Renders automatically when 2+ providers
have data. Contains:
- At a Glance summary table (sessions, cost, tokens, turns, avg cost/session, output ratio)
- Total Spend bar chart
- Token Volume grouped bar chart (input vs. output per provider)
- Daily Cost Trends multi-line overlay
- Efficiency Leaderboard table + cost/1K output bar chart
- Donut pies: Sessions by Provider | Spend by Provider

---

## Canonical Data Model

All providers write to the same SQLite tables. The `provider` column is the only
segregation mechanism needed.

### `providers` table
Tracks registered providers and their configuration.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `provider_id` | TEXT PK | Slug: `gemini`, `claude-code`, `codex`, `devin` |
| `display_name` | TEXT | Shown in UI tabs |
| `log_directory` | TEXT | User-configured path |
| `enabled` | INTEGER | 0/1 |
| `last_scanned_at` | TEXT | ISO timestamp |

### `sessions` table

| Column | Type | Notes |
| :--- | :--- | :--- |
| `session_id` | TEXT PK | Provider-native ID (UUID, hash, or timestamp slug) |
| `provider` | TEXT | FK → providers.provider_id |
| `project_path` | TEXT | Working directory or project root |
| `title` | TEXT | Derived from first user turn, or native title field (Claude) |
| `model` | TEXT | Last known or dominant model for this session |
| `created_at` | TEXT | ISO timestamp of first turn |
| `updated_at` | TEXT | ISO timestamp of last turn |
| `turn_count` | INTEGER | |
| `total_input_tokens` | INTEGER | |
| `total_output_tokens` | INTEGER | |
| `cache_input_tokens` | INTEGER | Cache creation tokens (Claude only) |
| `cache_output_tokens` | INTEGER | Cache read tokens (Claude, Codex) |
| `total_cost` | REAL | USD |
| `efficiency_score` | REAL | output_tokens / input_tokens * 100 |

### `turns` table

| Column | Type | Notes |
| :--- | :--- | :--- |
| `turn_id` | TEXT PK | `{session_id}_{sequence_index}` or provider-native ID |
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
| `cache_read_tokens` | INTEGER | Claude Code + Codex; null otherwise |
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
Avoids redundant token-count API calls for providers that require them (Gemini).

| Column | Type | Notes |
| :--- | :--- | :--- |
| `text_hash` | TEXT PK | MD5 of content |
| `token_count` | INTEGER | |

### `settings` table
Key-value store for user configuration.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `key` | TEXT PK | e.g. `gemini_api_key`, `claude_sonnet_input_rate`, `codex_input_rate` |
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

| Flag | Meaning | Providers |
| :--- | :--- | :--- |
| `native_token_counts` | Token counts are in the log; no API call needed | Claude Code, Codex |
| `cache_tokens` | Provider logs cache creation/read token counts | Claude Code, Codex |
| `native_title` | Provider supplies a session title in the log | Claude Code (`ai-title` event) |
| `model_switching` | Sessions can change models mid-stream | Gemini |
| `tool_use_tracking` | Tool invocations are logged as discrete events | Claude Code |
| `git_branch` | Log entries include the active git branch | Claude Code |

### Provider Registry (`src/providers/registry.py`)
Explicit registration list — no filesystem magic. Adding a provider means
importing it and adding one line to the registry.

```python
PROVIDERS: list[type[LogProvider]] = [
    GeminiProvider,
    ClaudeCodeProvider,
    CodexProvider,
    DevinProvider,   # stub — parse_turns() is a no-op until format is known
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
├── app.py                     # Streamlit entry point; all UI rendering
│
├── src/
│   ├── __init__.py
│   │
│   ├── database/
│   │   ├── connection.py      # SQLite connection helper
│   │   └── schema.py          # init_db(); get_setting(); save_setting()
│   │
│   ├── providers/
│   │   ├── base.py            # LogProvider ABC + CanonicalTurn + SessionMeta + PricingRate
│   │   ├── registry.py        # PROVIDERS list + get_all_providers() + get_provider()
│   │   ├── gemini/
│   │   │   ├── __init__.py
│   │   │   └── provider.py    # GeminiProvider — JSONL, SDK token counting, model switching
│   │   ├── claude_code/
│   │   │   ├── __init__.py
│   │   │   └── provider.py    # ClaudeCodeProvider — typed events, native tokens, cache
│   │   ├── codex/
│   │   │   ├── __init__.py
│   │   │   └── provider.py    # CodexProvider — task_started/complete state machine
│   │   └── devin/
│   │       ├── __init__.py
│   │       └── provider.py    # DevinProvider — STUB; discover_sessions() functional
│   │
│   ├── ingestion/
│   │   └── loader.py          # Iterates registry; dispatches to providers; writes DB
│   │
│   └── metrics/
│       ├── cost_calculator.py # Provider-agnostic; uses provider.get_pricing()
│       └── heuristics.py      # Pleasantry detection (high/low confidence); context debt
│
├── data/
│   └── dashboard.db           # SQLite (git-ignored)
│
└── tests/
    └── test_providers.py
```

---

## Key Flow

1. **Startup**: `init_db()` creates tables and seeds provider rows if absent.
   `get_all_providers()` instantiates every registered provider.
2. **Ingestion**: For each enabled provider, `loader.py` calls `discover_sessions()`,
   checks `processed_files` for each file (hash + last-read-line), calls `parse_turns()`
   for new lines only, upserts turns, then recalculates session aggregates.
3. **UI**: `app.py` queries SQLite filtered by `provider_id`. Each provider tab calls
   the same render functions with its `provider_id` as a scope argument. The Compare
   tab queries all providers at once.
4. **Extensibility**: New provider = new folder under `src/providers/`, one class,
   one line in `registry.py`, one `INSERT OR IGNORE` row in `schema.py`. No changes
   to ingestion, metrics, or UI layout required.
