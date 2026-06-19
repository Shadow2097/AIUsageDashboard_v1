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

## Quick Start

```bash
cd AIUsageDashboard_v1
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
streamlit run app.py
```

Configure log directories for each provider in the Settings panel on first run.

## Project Docs

- [`project_goals.md`](project_goals.md) — Phase scope and feature checklist
- [`architecture.md`](architecture.md) — Tech stack, data model, provider plugin system
- [`providers.md`](providers.md) — Provider research, prioritization, and format notes
