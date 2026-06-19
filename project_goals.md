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

## Phase 2: Analytics Depth

- [ ] Heuristic analyzer tuning: per-provider pleasantry thresholds; reduce false positives
      on Claude Code system/tool turns.
- [ ] Provider capability flags: conditionally render cache token breakdowns for Claude
      (cache write/read timeline overlay already present; expand in Phase 2).
- [ ] LLM-in-the-loop prompt compression audit (Flash for Gemini sessions, Haiku for Claude).
- [ ] Session efficiency scoring refinement: context growth rate, cost-per-turn trend.
- [ ] Advice tab: add high-cost turn cards; per-session summary of total savings potential.
- [ ] Prompt Auditor: add LLM-rewrite button with before/after token comparison.
- [ ] Daily trend chart: add session-count third axis or annotation layer.

## Phase 3: Cross-Provider Compare Tab

- [ ] Root-level **Compare** tab (appears when 2+ providers have data).
- [ ] Total spend, token volume, and session count by provider (bar/pie charts).
- [ ] Efficiency leaderboard: output-per-token ratio across providers.
- [ ] Daily/weekly cost trend lines overlaid across providers.
- [ ] No session content in Compare — metrics only.

## Phase 4: Additional Providers

- [ ] Research and document Cursor log format and storage location.
- [ ] Implement Cursor provider plugin.
- [ ] Evaluate and onboard one additional provider (Copilot, Windsurf, Cody, or similar).
- [ ] Provider auto-detection: scan known default paths and suggest configuration.

---

## Key Target User Value

- **Cost visibility**: See exactly what each AI tool costs per project, per session, per day.
- **Prompt efficiency**: Identify bloated prompts, pleasantries, and context debt before they compound.
- **Cross-tool comparison**: Understand whether Claude Code or Gemini is more token-efficient
  for your specific workflow.
- **No vendor lock-in**: Adding a new AI tool requires only a new provider plugin — no
  changes to the dashboard, database, or analytics engine.
