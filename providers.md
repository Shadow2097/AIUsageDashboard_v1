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

## Tier 1 — Implemented

### Antigravity / Gemini CLI ✅
- **Status**: Implemented (`GeminiProvider`)
- **Log path**: `~/.gemini/antigravity/brain/`
- **Format**: JSONL; one file per session; fields: `source`, `type`, `content`, `created_at`, `step_index`
- **Token counts**: Not in log — requires `google-generativeai` SDK `count_tokens()` call;
  results cached in `token_cache` table
- **Model detection**: Regex on USER turn content for `USER_SETTINGS_CHANGE` events
- **Session title**: Derived from first USER turn content
- **Capabilities**: `model_switching`
- **Pricing settings**: `gemini_flash_input_rate`, `gemini_flash_output_rate`,
  `gemini_pro_input_rate`, `gemini_pro_output_rate`

### Claude Code ✅
- **Status**: Implemented (`ClaudeCodeProvider`)
- **Log path**: `~/.claude/projects/**/*.jsonl` (Windows: `C:\Users\{user}\.claude\projects\`)
- **Format**: JSONL; typed events per line; session UUID as filename; nested by project slug
- **Token counts**: Native — `message.usage` in every `assistant` event
- **Model detection**: `message.model` field on `assistant` events
- **Session title**: Native `ai-title` event; no derivation needed
- **Project path**: `cwd` field on every event
- **Git branch**: `gitBranch` field on every event
- **Capabilities**: `native_token_counts`, `native_title`, `cache_tokens`, `tool_use_tracking`, `git_branch`
- **Key event types parsed**:
  - `user` — prompt text in `message.content`
  - `assistant` — response; `message.usage` has input/output/cache tokens
  - `ai-title` — auto-generated session title
  - Skipped: `attachment`, `file-history-snapshot`, `mode`, `permission-mode`, `summary`
- **Pricing settings**: `claude_haiku_input_rate`, `claude_haiku_output_rate`,
  `claude_sonnet_input_rate`, `claude_sonnet_output_rate`,
  `claude_opus_input_rate`, `claude_opus_output_rate`

### OpenAI Codex Desktop ✅
- **Status**: Implemented (`CodexProvider`)
- **Log path**: `~/.codex/sessions/{year}/{month}/{day}/` (Windows: `C:\Users\{user}\.codex\sessions\`)
- **Filename**: `rollout-{ISO-timestamp}-{uuid}.jsonl`
- **Format**: JSONL; typed event objects; one session per file; turns bounded by
  `task_started` / `task_complete` pairs
- **Token counts**: Native — `event_msg/token_count` events fire after every API round-trip;
  the last one before `task_complete` carries cumulative `total_token_usage` for the full turn
  (including all tool-call iterations billed as separate API calls)
- **Key token fields**: `input_tokens`, `cached_input_tokens`, `output_tokens`,
  `reasoning_output_tokens`, `total_tokens`
- **Model detection**: `turn_context` event, `model` field (`gpt-5.5`, `gpt-5.4-mini`)
- **User content**: `event_msg/user_message.payload.message` (cleanest source)
- **Assistant content**: `task_complete.last_agent_message`
- **Cache tokens**: `cached_input_tokens` → `cache_read_tokens` (automatic prompt caching;
  no explicit write event like Claude)
- **Session title**: Derived from first user message (no native title event)
- **Capabilities**: `native_token_counts`, `cache_tokens`
- **Key event types parsed**:
  - `session_meta` — session ID, cwd, model_provider
  - `event_msg/task_started` — turn open; yields `turn_id`, `started_at`
  - `turn_context` — model name, cwd, approval policy
  - `event_msg/user_message` — user prompt text
  - `event_msg/token_count` — cumulative token usage (kept as last-seen per turn)
  - `event_msg/task_complete` — turn close; assistant response text, timestamps
  - Skipped: `response_item/reasoning` (encrypted), `response_item/function_call`,
    `response_item/function_call_output`, `event_msg/agent_message` (interim commentary)
- **Pricing settings**: `codex_input_rate`, `codex_output_rate` (gpt-5.5),
  `codex_mini_input_rate`, `codex_mini_output_rate` (gpt-5.4-mini); all default $0
  pending OpenAI's published Codex pricing

### Devin (Windsurf IDE / DevinAI) 🔧 Stub
- **Status**: Stub implemented (`DevinProvider`) — `discover_sessions()` functional,
  `parse_turns()` is a documented no-op
- **Log path**: `%APPDATA%\Devin\logs\` (Windows: `C:\Users\{user}\AppData\Roaming\Devin\logs\`)
- **Directory structure** (observed 2026-06-19):
  ```
  logs/
    {YYYYMMDDTHHMMSS}/             ← one folder per app launch
      main.log
      telemetry.log
      window1/
        exthost/
          codeium.windsurf/
            Devin.log              ← likely: main extension log
            Devin ACP.log          ← likely: Agent Communication Protocol
            Devin ACP devin-cli.log
            Devin ACP devin-cloud.log
            Devin ACP summary-agent.log
            Devin (Lifeguard).log
        output_{YYYYMMDDTHHMMSS}/
          agentSessionsOutput.log  ← primary candidate for conversation content
          tasks.log
  ```
- **Format**: Unknown — all log files were 0 KB at time of investigation.
  Underlying IDE is a VS Code fork (Electron). AI extension is `codeium.windsurf`.
- **Candidate files** (priority order):
  1. `window1/output_{ts}/agentSessionsOutput.log` — name suggests conversation content
  2. `window1/exthost/codeium.windsurf/Devin ACP.log` — Agent Communication Protocol
  3. `window1/exthost/codeium.windsurf/Devin.log` — general extension log
- **Token counts**: Unknown — Devin uses a mix of models (SWE-1, SWE-1-lite, and
  pass-through models like claude-sonnet, gpt-4o); billing may be task-based
- **Capabilities**: None declared (stub)
- **Pricing settings**: `devin_input_rate`, `devin_output_rate`; default $0
- **Next steps**: When log files contain real data, inspect `agentSessionsOutput.log`
  and `Devin ACP.log` for format, then implement `parse_turns()` and update capabilities

---

## Tier 2 — High Value, Research Needed

### Cursor
- **Status**: 🔬 Research needed
- **Likely log path**: `%APPDATA%\Cursor\` or `%LOCALAPPDATA%\cursor-updater\`
- **Format**: Unknown — likely LevelDB (Electron/Chromium IndexedDB) or SQLite;
  JSONL possible for conversation exports. Cursor is open source — source code could
  reveal storage format definitively.
- **Token counts**: Unknown — Cursor uses the Anthropic API internally for Claude models
  and the OpenAI API for GPT models; usage may surface in logs
- **User base**: Very large; one of the most popular AI coding editors
- **Cost visibility value**: High — Cursor Pro has token/request limits that users hit
- **Notes**: Priority target for next phase. Check both `%APPDATA%\Cursor\` and
  `%LOCALAPPDATA%\Cursor\` for readable files. Search for `.db`, `.sqlite`, `.jsonl`.
  Also check if the Cursor CLI companion tool has its own log format.

### Aider
- **Status**: 🔬 Research needed
- **Likely log path**: `.aider.chat.history.md` in each project directory
- **Format**: Markdown chat history — human-readable but requires custom parser
- **Token counts**: Aider prints token usage to stdout; may be captured in logs
- **User base**: Popular open-source coding assistant
- **Notes**: Markdown format is unusual but parseable. Could be a quick win if
  token data is included in the history file. Open source — format is fully documented.

### Continue.dev (VS Code / JetBrains extension)
- **Status**: 🔬 Research needed
- **Likely log path**: `~/.continue/` — Continue stores history locally
- **Format**: Likely JSON or SQLite — Continue is open source and history
  persistence is a documented feature
- **Token counts**: Unknown
- **Notes**: Open source means format is documentable from source code.

---

## Tier 3 — Lower Priority or Known Blockers

### Claude Desktop
- **Status**: ⚠️ Known blocker — binary log format
- **Log path**: `%APPDATA%\Claude\IndexedDB\https_claude.ai_0.indexeddb.leveldb\`
- **Format**: LevelDB (Chromium IndexedDB) — binary, not human-readable without
  a LevelDB reader library
- **Token counts**: Not in local storage — conversation data is server-side
- **Notes**: Would require `plyvel` or similar Python LevelDB library. The
  `local-agent-mode-sessions/` directory does contain `audit.jsonl` files for
  Cowork sessions — this subset may be parseable and is worth revisiting.

### GitHub Copilot (VS Code extension)
- **Status**: 🔬 Research needed
- **Likely log path**: `%APPDATA%\Code\logs\` or via VS Code "Developer: Open Extension Logs Folder"
- **Format**: Unknown — VS Code logs are typically plain text or JSON
- **Token counts**: Unlikely to be in local logs — Copilot is subscription-based with
  no per-token billing visible to users
- **Cost visibility value**: Low for individuals (flat subscription); medium for
  enterprise (seat cost allocation)
- **Notes**: More useful for usage pattern analytics than cost tracking.

### Amazon Q Developer
- **Status**: 🔬 Research needed
- **Token counts**: AWS subscription model — no per-token billing for individuals
- **Cost visibility value**: Low for individual users
- **Notes**: Low priority unless enterprise seat-cost tracking becomes a use case.

---

## Investigation Checklist for New Electron-Based Tools

When investigating a new Electron-based AI coding tool:

1. Check `%APPDATA%\{ToolName}\` and `%LOCALAPPDATA%\{ToolName}\` for any `.jsonl`,
   `.json`, `.db`, or `.sqlite` files
2. Look for a `logs\` subdirectory — Electron apps often write plaintext logs there
3. Check `IndexedDB\` and `Local Storage\leveldb\` — if present, it's binary LevelDB
4. Search for SQLite files: `*.db`, `*.sqlite`, `*.sqlite3`
5. Check if the tool is open source — source code reveals storage format definitively
6. Look for any CLI companion tools that might have their own, cleaner log format
7. Check the extension host logs if it's a VS Code fork:
   `window1/exthost/{publisher}.{extension-name}/`

When a new provider is confirmed ready, implement the plugin and update this document.
