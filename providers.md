# Provider Research & Prioritization

This document tracks known AI coding tools, their log formats, and their
implementation status as dashboard providers.

---

## Provider Selection Criteria

When evaluating a new provider for support, score it against these factors:

| Criterion | Weight | Notes |
| :--- | :--- | :--- |
| **Log accessibility** | High | Are logs stored locally in a readable format? Binary/cloud-only = blocker |
| **Log format clarity** | High | Is the format documented or reverse-engineerable? |
| **Token data in log** | Medium | Do logs include token counts, or must we estimate/call an API? |
| **User base size** | Medium | How many developers actively use this tool? |
| **Cost visibility value** | Medium | Does the tool have meaningful per-session cost variance worth tracking? |
| **Installation on this machine** | Low | Can we test against real logs immediately? |

---

## Tier 1 — Implement First (Known Format, Logs Available)

### Antigravity / Gemini CLI
- **Status**: ✅ Implemented in GeminiLogDashboard_v1 — port to provider plugin
- **Log path**: `~/.gemini/antigravity/brain/`
- **Format**: JSONL; one file per session; fields: `source`, `type`, `content`, `created_at`, `step_index`
- **Token counts**: Not in log — requires `google-generativeai` SDK `count_tokens()` call
- **Model detection**: Regex on USER turn content for `USER_SETTINGS_CHANGE` events
- **Session title**: Derived from first USER turn content
- **Capabilities**: `model_switching`
- **Notes**: Token cache in SQLite prevents redundant API calls

### Claude Code
- **Status**: 🔄 Ready to implement — format fully reverse-engineered
- **Log path**: `~/.claude/projects/**/*.jsonl` (Windows: `C:\Users\{user}\.claude\projects\`)
- **Format**: JSONL; typed events per line; session UUID as filename
- **Token counts**: ✅ Native — `message.usage` in every `assistant` event includes
  `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- **Model detection**: `message.model` field on `assistant` events
- **Session title**: Native `ai-title` event type; no derivation needed
- **Project path**: `cwd` field on every event
- **Git branch**: `gitBranch` field on every event
- **Capabilities**: `native_token_counts`, `native_title`, `cache_tokens`, `tool_use_tracking`, `git_branch`
- **Key event types**:
  - `user` — user message; `message.content` is the prompt text
  - `assistant` — model response; contains `message.usage` and `message.content[]`
  - `ai-title` — auto-generated session title
  - `attachment` — tool listings, skill configs (skip for analytics)
  - `file-history-snapshot` — file state (skip for analytics)
  - `mode`, `permission-mode` — session config (skip for analytics)
- **Notes**: Most analytics-friendly format of all known providers; no API call needed

---

## Tier 2 — High Value, Format Research Needed

### Cursor
- **Status**: 🔬 Research needed
- **Likely log path**: `~/.cursor/` or `%APPDATA%\Cursor\` (Electron app)
- **Format**: Unknown — likely LevelDB (Electron) or SQLite; JSONL possible for
  conversation exports
- **Token counts**: Unknown — Cursor uses the Anthropic API internally for Claude models;
  may expose usage in logs
- **User base**: Very large; one of the most popular AI coding editors
- **Cost visibility value**: High — Cursor Pro has token limits that users frequently hit
- **Notes**: Priority target for Phase 4. Check `%APPDATA%\Cursor\` and
  `%LOCALAPPDATA%\Cursor\` for readable log files. Also check for any SQLite DBs
  that might store conversation history.

### GitHub Copilot (VS Code extension)
- **Status**: 🔬 Research needed
- **Likely log path**: VS Code extension logs at
  `%APPDATA%\Code\logs\` or via VS Code's "Developer: Open Extension Logs Folder"
- **Format**: Unknown — VS Code logs are typically plain text or JSON; Copilot may
  have a separate telemetry log
- **Token counts**: Unlikely to be in local logs — Copilot is subscription-based with
  no per-token billing visible to users
- **Cost visibility value**: Low for individuals (flat subscription); medium for
  enterprise (seat cost allocation)
- **Notes**: May be more useful for *usage pattern* analytics than cost tracking.
  Lower priority unless token data surfaces in logs.

### Windsurf (Codeium)
- **Status**: 🔬 Research needed
- **Likely log path**: `%APPDATA%\Windsurf\` (Electron)
- **Format**: Unknown — Electron app, likely LevelDB similar to Claude Desktop
- **Token counts**: Unknown
- **User base**: Growing rapidly; strong alternative to Cursor
- **Cost visibility value**: Medium — Windsurf has a credit-based system ("flows")
  that users track manually
- **Notes**: Credit system makes cost tracking potentially high-value if flow
  consumption is logged locally.

---

## Tier 3 — Lower Priority or Known Blockers

### Claude Desktop (claude.ai web in Electron)
- **Status**: ⚠️ Known blocker — binary log format
- **Log path**: `%APPDATA%\Claude\IndexedDB\https_claude.ai_0.indexeddb.leveldb\`
- **Format**: LevelDB (Chromium IndexedDB) — binary, not human-readable without
  a LevelDB reader library
- **Token counts**: Not in local storage — conversation data is server-side
- **Notes**: Would require `plyvel` or similar Python LevelDB library. May be
  feasible but significantly more complex than JSONL providers. Revisit in Phase 4.
  The `local-agent-mode-sessions/` directory does contain `audit.jsonl` files for
  Cowork sessions — this subset may be parseable sooner.

### Aider
- **Status**: 🔬 Research needed
- **Likely log path**: `.aider.chat.history.md` in each project directory
- **Format**: Markdown chat history — human-readable but requires custom parser
- **Token counts**: Aider prints token usage to stdout; may be captured in logs
- **User base**: Popular open-source coding assistant
- **Notes**: Markdown format is unusual but parseable. Could be a quick win if
  token data is included in the history file.

### Continue.dev (VS Code / JetBrains extension)
- **Status**: 🔬 Research needed
- **Likely log path**: `~/.continue/` — Continue stores history locally
- **Format**: Likely JSON or SQLite — Continue is open source and history
  persistence is a documented feature
- **Token counts**: Unknown
- **Notes**: Open source means format is documentable from source code.
  Check https://github.com/continuedev/continue for storage implementation.

### Amazon Q Developer
- **Status**: 🔬 Research needed
- **Token counts**: AWS subscription model — no per-token billing for individuals
- **Cost visibility value**: Low for individual users
- **Notes**: Low priority unless enterprise seat-cost tracking becomes a use case.

---

## Next Steps for Provider Research

When investigating a new Electron-based tool (Cursor, Windsurf, etc.):

1. Check `%APPDATA%\{ToolName}\` and `%LOCALAPPDATA%\{ToolName}\` for any `.jsonl`,
   `.json`, `.db`, or `.sqlite` files
2. Look for a `logs\` subdirectory — Electron apps often write plaintext logs there
3. Check `IndexedDB\` and `Local Storage\leveldb\` — if present, it's binary LevelDB
4. Search for SQLite files: `*.db`, `*.sqlite`, `*.sqlite3`
5. Check if the tool is open source — source code reveals storage format definitively
6. Look for any CLI companion tools that might have their own log format

When a new provider is confirmed ready, create a dedicated research note at
`src/providers/{provider_name}/RESEARCH.md` before implementing the plugin.
