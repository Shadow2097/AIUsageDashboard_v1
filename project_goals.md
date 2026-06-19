# Project Goals & Scope

This document defines the phases and scope for the **AI Usage Dashboard (v1)**.

## Vision

A single, locally-running dashboard that ingests conversation logs from any supported
AI coding tool, normalizes them into a unified data model, and surfaces token usage,
cost, and prompt efficiency insights — per provider and in aggregate.

The dashboard is purely analytical. It reads logs and presents data. It does not alter,
intercept, or influence the behavior of any AI tool it monitors.

---

## Phase 1: Multi-Provider Foundation ✅ Complete

- [x] Define and implement the canonical database schema (sessions, turns, providers,
      token_cache, processed_files, settings).
- [x] Implement the `LogProvider` base class and `ProviderRegistry`.
- [x] Implement the **Antigravity/Gemini** provider:
      - `discover_sessions()` — scans JSONL files in the configured log directory
      - `parse_turns()` — parses source/type/content fields, detects model changes via
        `USER_SETTINGS_CHANGE` regex, accumulates context_tokens for cost estimation
      - `count_tokens()` — google-generativeai SDK with SQLite cache and heuristic fallback
      - `get_pricing()` — Flash / Pro tiers from settings
- [x] Implement the **Claude Code** provider:
      - `discover_sessions()` — recursive scan of `{log_dir}/{project-slug}/*.jsonl`
      - `parse_turns()` — typed event parsing; native token counts from `message.usage`;
        cache_creation and cache_read tokens; model from `message.model`
      - `get_pricing()` — Haiku / Sonnet / Opus tiers from settings
- [x] Incremental ingestion: track file hash + last-read line per file; skip unchanged.
- [x] Auto-ingest on startup; manual **Rescan** button per provider + global **Rescan All**.
- [x] Streamlit UI — two-level tab hierarchy:
      - Root tabs: one per configured provider
      - Sub-tabs per provider: **Overview**, **Session Explorer**, **Advice**, **Prompt Auditor**
- [x] Sidebar settings: log directory, Gemini API key, pricing rates per model tier.
- [x] `providers` table seeded on `init_db()` to satisfy sessions FK constraint.
- [x] Local git repo, `.gitignore`, Apache 2.0 `LICENSE`, pushed to GitHub.

### Phase 1 Implementation Notes

- Token counting for Gemini is estimated (SDK call → SQLite cache → heuristic fallback).
  Claude Code token counts are native from log; no API call needed.
- Context accumulation curve in Session Explorer uses `input_tokens` on assistant turns,
  which naturally represents the full context window for both providers.
- Pleasantry detection and context-debt warnings surface inline in the Session Explorer
  transcript as well as on the Advice tab.
- The Advice tab operates on undismissed turns only; dismissal writes `is_dismissed = 1`.

---

## Phase 2: Analytics Depth ✅ Complete

- [x] Heuristic analyzer tuning: split pleasantry patterns into high-confidence
      (`thank you`, `got it`, `sounds good`) and low-confidence (`great`, `sure`, `of course`)
      tiers. Low-confidence only fires on short turns (≤ 300 chars). Removed `please`.
      Role filter: pleasantry detection runs on `user` turns only.
- [x] Provider capability flags: cache token breakdowns render conditionally for providers
      that declare `cache_tokens` (Claude Code, Codex).
- [x] LLM-in-the-loop prompt compression: **✨ Compress with AI** button in Prompt Auditor.
      Uses Claude Haiku (via `anthropic_api_key`) for Claude Code and Codex sessions;
      Gemini 1.5 Flash (via `gemini_api_key`) for Gemini sessions. Result persisted in
      `st.session_state` keyed by source prompt to survive Streamlit rerenders.
- [x] Session efficiency scoring: `output_tokens / input_tokens * 100` stored on sessions.
- [x] Advice tab: three card types in one sorted list with summary banner:
      - ⚠️ Pleasantry — user turns with low-signal phrases
      - 🚨 Context Debt — turns where context exceeds 80% of context window
      - 💸 High Cost — turns with cost > $0.05; shows top 20, total exposure
      Summary banner: `"N opportunities · ⚠️ X pleasantry · 🚨 Y context-debt · 💸 Z high-cost ($total)"`
- [x] Daily trend chart: session-count annotations rendered above each bar.
- [x] Sidebar: Anthropic API key input (password field) under Claude Code section.
- [x] Bug fix: `created_at` column was empty on all sessions because the
      `ON CONFLICT DO UPDATE SET` in `_upsert_session_aggregates` was missing
      `created_at = excluded.created_at`. Fixed; existing rows backfilled.

---

## Phase 3: Cross-Provider Compare Tab ✅ Complete

- [x] Root-level **⚖️ Compare** tab — auto-appears when 2+ providers have ingested data;
      auto-hides when ≤ 1 provider has data.
- [x] **At a Glance** summary table: sessions, cost, tokens, turns, avg cost/session,
      output ratio — one row per provider.
- [x] **Total Spend** horizontal bar chart (USD).
- [x] **Token Volume** grouped bar chart: input vs. output tokens per provider.
- [x] **Daily Cost Trends** multi-line overlay: one line per provider on a shared x-axis.
- [x] **Efficiency Leaderboard** table: output/input%, cost/1K output tokens,
      avg cost/session, avg cost/turn — plus a horizontal bar chart with annotation.
- [x] **Donut pies**: Sessions by Provider | Spend by Provider.
- [x] `_PROVIDER_COLORS` constant: consistent color assignment across all Compare charts.

---

## Phase 4: Additional Providers 🔄 In Progress

- [x] Research OpenAI Codex Desktop log format; implement **CodexProvider**:
      - Log path: `~/.codex/sessions/{year}/{month}/{day}/*.jsonl`
      - Format: typed JSONL events; turns bracketed by `task_started` / `task_complete`
      - Token counts: native from `event_msg/token_count` — `total_token_usage` (cumulative per turn)
      - User content: `event_msg/user_message.payload.message`
      - Assistant content: `task_complete.last_agent_message`
      - Cache tokens: `cached_input_tokens` → `cache_read_tokens`
      - Model: `gpt-5.5` or `gpt-5.4-mini` from `turn_context` event
      - Pricing: $0 defaults; configurable in sidebar when OpenAI publishes rates
- [x] Stub **DevinProvider** for Windsurf IDE / DevinAI:
      - Log path: `%APPDATA%/Devin/logs/{YYYYMMDDTHHMMSS}/`
      - Structure: VS Code-fork Electron app; AI logs under `window1/exthost/codeium.windsurf/`
      - Candidate file: `window1/output_{timestamp}/agentSessionsOutput.log`
      - `discover_sessions()` functional; `parse_turns()` no-op until format is known
      - All log files were 0 KB at time of investigation (2026-06-19)
- [ ] Flesh out DevinProvider once log files contain real session data.
- [ ] Research and document Cursor log format and storage location.
- [ ] Implement Cursor provider plugin.
- [ ] Provider auto-detection: scan known default paths and suggest configuration in sidebar.

---

## Key Target User Value

- **Cost visibility**: See exactly what each AI tool costs per project, per session, per day.
- **Prompt efficiency**: Identify bloated prompts, pleasantries, and context debt before they compound.
- **Cross-tool comparison**: Understand whether Claude Code or Gemini is more token-efficient
  for your specific workflow.
- **No vendor lock-in**: Adding a new AI tool requires only a new provider plugin — no
  changes to the dashboard, database, or analytics engine.
