# Project Goals & Scope

This document defines the phases and scope for the **AI Usage Dashboard (v1)**.

## Vision

A single, locally-running dashboard that ingests conversation logs from any supported
AI coding tool, normalizes them into a unified data model, and surfaces token usage,
cost, and prompt efficiency insights — per provider and in aggregate.

The dashboard is purely analytical. It reads logs and presents data. It does not alter,
intercept, or influence the behavior of any AI tool it monitors.

---

## Phase 1: Multi-Provider Foundation

- [ ] Define and implement the canonical database schema (sessions, turns, providers).
- [ ] Implement the `LogProvider` base class and `ProviderRegistry` auto-loader.
- [ ] Implement the **Antigravity/Gemini** provider (ported from GeminiLogDashboard_v1).
- [ ] Implement the **Claude Code** provider (parses `~/.claude/projects/**/*.jsonl`).
- [ ] Incremental ingestion: track file hash + last-read line per file, skip unchanged files.
- [ ] Auto-ingest on startup; manual rescan button per provider.
- [ ] Streamlit UI: top-level provider tabs + per-provider sub-tabs (Overview, Explorer, Advice, Playground).
- [ ] Settings screen: configure log directory and pricing rates per provider.

## Phase 2: Analytics Depth

- [ ] Heuristic analyzer: pleasantry detection, context debt warnings (per-provider tuning).
- [ ] Provider capability flags: conditionally render cache token breakdowns for Claude,
      model-switching timeline for Gemini, etc.
- [ ] LLM-in-the-loop prompt compression audit (Flash for Gemini sessions, Haiku for Claude sessions).
- [ ] Session efficiency scoring: output/input ratio, context growth curve, cost-per-turn.
- [ ] Advice tab: actionable per-session recommendations, dismissible cards.
- [ ] Prompt Playground: paste a prompt, see token estimate, pleasantry flags, and optimized rewrite.

## Phase 3: Cross-Provider Compare Tab

- [ ] Root-level **Compare** tab showing aggregate metrics across all providers.
- [ ] Total spend, token volume, and session count by provider (bar/pie charts).
- [ ] Efficiency leaderboard: which provider/project produces the best output-per-token ratio.
- [ ] Daily/weekly cost trend lines overlaid across providers.
- [ ] No session content shown in Compare — metrics only, no provider mixing in Explorer.

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
