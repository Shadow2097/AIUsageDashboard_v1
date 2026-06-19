# AI Usage Dashboard

A locally-running dashboard that ingests conversation logs from AI coding tools,
normalizes them into a unified data model, and surfaces token usage, cost, and
prompt efficiency insights — per provider and in aggregate.

## Supported Providers

| Provider | Status | Log Format |
| :--- | :--- | :--- |
| Antigravity / Gemini CLI | ✅ Implemented | JSONL, one file per session |
| Claude Code | ✅ Implemented | JSONL, typed events, native token counts |
| OpenAI Codex Desktop | ✅ Implemented | JSONL, task_started/task_complete events |
| Devin (Windsurf IDE) | 🔧 Stub | Log format TBD — all files currently 0 KB |
| Cursor | 🔬 Research needed | Likely LevelDB or SQLite |

## Phase Status

| Phase | Status | Summary |
| :--- | :--- | :--- |
| **Phase 1** — Multi-Provider Foundation | ✅ Complete | Schema, two providers, incremental ingestion, full four-tab UI |
| **Phase 2** — Analytics Depth | ✅ Complete | Heuristic tuning, Advice cards, LLM compression, daily annotations |
| **Phase 3** — Cross-Provider Compare Tab | ✅ Complete | Aggregate charts, efficiency leaderboard, donut pies |
| **Phase 4** — Additional Providers | 🔄 In Progress | Codex ✅, Devin stub 🔧, Cursor 🔬 |

## Quick Start

```bash
cd AIUsageDashboard_v1
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
streamlit run app.py
```

On first run, set a log directory for each provider in the sidebar and click **Rescan**.

### Default Log Paths

| Provider | Default Log Path |
| :--- | :--- |
| Claude Code | `C:\Users\{user}\.claude\projects\` |
| Antigravity / Gemini | `~\.gemini\antigravity\brain\` |
| OpenAI Codex Desktop | `C:\Users\{user}\.codex\sessions\` |
| Devin (Windsurf IDE) | `C:\Users\{user}\AppData\Roaming\Devin\logs\` |

## UI Overview

```
[ Gemini ]  [ Claude Code ]  [ Codex ]  [ Devin ]  [ ⚖️ Compare ]
    ├── 📈 Overview          Metric tiles, daily cost/token trend, session table
    ├── 💬 Session Explorer  Session picker, context growth chart, transcript
    ├── 💡 Advice            Pleasantry, context-debt, and high-cost cards (dismissible)
    └── 🔍 Prompt Auditor    Token estimate, pleasantry check, LLM compression
```

The **⚖️ Compare** tab appears automatically when two or more providers have ingested data.

### Advice Tab — Card Types

| Card | Trigger | Color |
| :--- | :--- | :--- |
| ⚠️ Pleasantry | User turn with low-signal phrases ("thanks", "sounds good") | Amber |
| 🚨 Context Debt | Assistant turn with context > 80% of model context window | Red |
| 💸 High Cost | Turn cost > $0.05 | Purple |

### Prompt Auditor

Paste any prompt to get a token count, pleasantry scan, and cost projection. If an
Anthropic API key is configured, the **✨ Compress with AI** button rewrites the prompt
with Claude Haiku and shows before/after token savings.

## Project Docs

- [`project_goals.md`](project_goals.md) — Phase scope and feature checklist
- [`architecture.md`](architecture.md) — Tech stack, data model, provider plugin system
- [`providers.md`](providers.md) — Provider research, prioritization, and format notes
