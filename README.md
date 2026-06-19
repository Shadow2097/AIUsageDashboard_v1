# AI Usage Dashboard

A locally-running dashboard that ingests conversation logs from AI coding tools,
normalizes them into a unified data model, and surfaces token usage, cost, and
prompt efficiency insights — per provider and in aggregate.

## Supported Providers

| Provider | Status |
| :--- | :--- |
| Antigravity / Gemini CLI | ✅ Phase 1 |
| Claude Code | ✅ Phase 1 |
| Cursor | 🔬 Phase 4 (research needed) |
| Windsurf | 🔬 Phase 4 (research needed) |

## Phase Status

| Phase | Status | Summary |
| :--- | :--- | :--- |
| **Phase 1** — Multi-Provider Foundation | ✅ Complete | Schema, providers, ingestion, full UI |
| **Phase 2** — Analytics Depth | 🔲 Not started | Heuristic tuning, LLM compression audit, efficiency scoring |
| **Phase 3** — Cross-Provider Compare Tab | 🔲 Not started | Aggregate cross-provider charts |
| **Phase 4** — Additional Providers | 🔬 Research | Cursor, Windsurf format investigation |

## Quick Start

```bash
cd AIUsageDashboard_v1
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
streamlit run app.py
```

On first run, set a log directory for each provider in the sidebar and click **Rescan**.

### Log Paths (defaults)

| Provider | Default Log Path |
| :--- | :--- |
| Claude Code | `C:\Users\{user}\.claude\projects\` |
| Antigravity / Gemini | `~\.gemini\antigravity\brain\` |

## UI Overview

```
[ Claude Code ]  [ Antigravity / Gemini ]        ← Root provider tabs
    ├── 📈 Overview          Metric tiles, daily cost/token trend, session table
    ├── 💬 Session Explorer  Session picker, context growth chart, transcript
    ├── 💡 Advice            Pleasantry & context-debt cards (dismissible)
    └── 🔍 Prompt Auditor    Token estimate, pleasantry check, cost projection
```

## Project Docs

- [`project_goals.md`](project_goals.md) — Phase scope and feature checklist
- [`architecture.md`](architecture.md) — Tech stack, data model, provider plugin system
- [`providers.md`](providers.md) — Provider research, prioritization, and format notes
