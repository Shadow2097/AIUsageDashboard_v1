"""
Devin (Windsurf IDE / DevinAI) log provider — STUB.

Log path: %APPDATA%/Devin/logs/
  (C:\\Users\\<user>\\AppData\\Roaming\\Devin\\logs)

Directory structure observed (all files 0 KB as of 2026-06-19 — format TBD):

  logs/
    {YYYYMMDDTHHMMSS}/                         ← one folder per app launch
      main.log
      telemetry.log
      window1/
        exthost/
          codeium.windsurf/
            Devin.log                           ← likely: main extension log
            Devin ACP.log                       ← likely: Agent Communication Protocol
            Devin ACP devin-cli.log
            Devin ACP devin-cloud.log
            Devin ACP summary-agent.log
            Devin (Lifeguard).log
        output_{YYYYMMDDTHHMMSS}/
          agentSessionsOutput.log               ← likely: conversation/session output
          tasks.log

Candidate files to parse (priority order):
  1. agentSessionsOutput.log  — name suggests conversation content
  2. Devin ACP.log            — Agent Communication Protocol; may carry turn data
  3. Devin.log                — general extension log; may include request/response pairs

Implementation status: STUB
  discover_sessions() — identifies candidate files from the directory tree
  parse_turns()       — returns [] until format is reverse-engineered from real data

Next steps when log files contain data:
  1. Inspect agentSessionsOutput.log and Devin ACP.log for format (JSON, plain text, etc.)
  2. Identify turn boundaries, user/assistant roles, token counts (if present)
  3. Implement parse_turns() and update capabilities accordingly
"""

import os
import re

from ..base import LogProvider, SessionMeta, CanonicalTurn, PricingRate
from src.database.schema import get_setting


# Folder name format: YYYYMMDDTHHMMSS
_LAUNCH_DIR_RE = re.compile(r"^\d{8}T\d{6}$")

# Candidate log files that are most likely to contain conversation data,
# in preference order. Update once real format is known.
_CANDIDATE_LOGS = [
    # relative to the launch-session root
    os.path.join("window1", "output_*", "agentSessionsOutput.log"),
    os.path.join("window1", "exthost", "codeium.windsurf", "Devin ACP.log"),
    os.path.join("window1", "exthost", "codeium.windsurf", "Devin.log"),
]


def _find_candidate_file(launch_dir: str) -> str | None:
    """
    Returns the path to the best candidate log file inside a launch session
    directory, or None if nothing is found.

    Preference order matches _CANDIDATE_LOGS. Glob-style '*' in path segments
    is resolved by scanning the directory.
    """
    for pattern in _CANDIDATE_LOGS:
        parts = pattern.split(os.sep)
        current = [launch_dir]
        for part in parts:
            if "*" in part:
                next_current = []
                for base in current:
                    try:
                        for entry in os.scandir(base):
                            if entry.name.startswith(part.replace("*", "")):
                                next_current.append(entry.path)
                    except OSError:
                        pass
                current = next_current
            else:
                current = [os.path.join(b, part) for b in current]

        for candidate in current:
            if os.path.isfile(candidate):
                return candidate

    return None


class DevinProvider(LogProvider):
    """
    STUB provider for Devin (Windsurf IDE / DevinAI).

    discover_sessions() is functional — it walks the log tree and surfaces
    candidate files. parse_turns() is a no-op until the log format is known.
    """

    provider_id = "devin"
    display_name = "Devin"

    # Capabilities will be updated once format is confirmed.
    # Windsurf/Codeium models likely include SWE-1, SWE-1-lite, and pass-through
    # models like claude-sonnet, gpt-4o, etc.
    capabilities: set[str] = set()

    def discover_sessions(self, log_dir: str) -> list[SessionMeta]:
        """
        Walks log_dir for launch-session folders (YYYYMMDDTHHMMSS) and returns
        one SessionMeta per folder that contains at least one candidate log file.
        """
        sessions = []
        if not log_dir or not os.path.isdir(log_dir):
            return sessions

        try:
            entries = sorted(os.scandir(log_dir), key=lambda e: e.name)
        except OSError:
            return sessions

        for entry in entries:
            if not entry.is_dir():
                continue
            if not _LAUNCH_DIR_RE.match(entry.name):
                continue

            candidate = _find_candidate_file(entry.path)
            if candidate is None:
                # No recognised log file in this launch dir; skip for now
                continue

            try:
                stat = os.stat(candidate)
            except OSError:
                continue

            # Use the launch-dir timestamp as session_id (unique per launch)
            session_id = entry.name

            sessions.append(SessionMeta(
                session_id=session_id,
                file_path=candidate,
                project_path=entry.path,  # launch-session root
                file_size=stat.st_size,
                last_modified=stat.st_mtime,
            ))

        return sessions

    def parse_turns(self, session_meta: SessionMeta, start_line: int) -> list[CanonicalTurn]:
        """
        STUB — returns empty list until log format is reverse-engineered.

        Once agentSessionsOutput.log or Devin ACP.log contain real data,
        implement parsing here and update 'capabilities' accordingly.
        """
        # Log file is currently 0 KB on all observed installations.
        # Return early; the loader will track the (empty) file state so it
        # won't re-attempt until the file grows.
        if session_meta.file_size == 0:
            return []

        # TODO: implement once format is known
        print(
            f"[DevinProvider] Non-empty log detected at {session_meta.file_path} "
            f"({session_meta.file_size} bytes) — parse_turns() not yet implemented."
        )
        return []

    def get_pricing(self, model_name: str) -> PricingRate:
        """
        Devin pricing is session/task-based (not token-based) and not yet
        mapped to per-token rates. Returns configurable rates defaulting to $0.
        """
        return PricingRate(
            input_rate=float(get_setting("devin_input_rate", "0.0")),
            output_rate=float(get_setting("devin_output_rate", "0.0")),
        )
