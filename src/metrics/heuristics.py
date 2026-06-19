"""
Heuristics — provider-agnostic prompt analysis.

Detects low-value patterns (pleasantries, context debt) in turn content.
"""

import re

# Always-flag: genuine pleasantry phrases regardless of message length
_HIGH_CONFIDENCE_PATTERNS = [
    r"\bthank you\b", r"\bthanks\b", r"\bthank\b",
    r"\bsounds good\b", r"\bgot it\b",
    r"\bhello\b", r"\bhey\b",
]

# Only flag in short messages — these words are legitimate in technical text
_LOW_CONFIDENCE_PATTERNS = [
    r"\bgreat\b", r"\bawesome\b", r"\bperfect\b", r"\bwonderful\b",
    r"\bexcellent\b", r"\bsure\b", r"\bof course\b",
    r"\bcertainly\b", r"\babsolutely\b", r"\bhi\b",
]

# "please" omitted — it's a request qualifier, not a pleasantry

_LOW_CONF_MAX_LEN = 300  # chars; skip low-confidence patterns in longer messages

_HIGH_RE = re.compile("|".join(_HIGH_CONFIDENCE_PATTERNS), re.IGNORECASE)
_LOW_RE  = re.compile("|".join(_LOW_CONFIDENCE_PATTERNS),  re.IGNORECASE)

CONTEXT_DEBT_RATIO_THRESHOLD    = 15.0
CONTEXT_DEBT_ABSOLUTE_THRESHOLD = 40_000


def detect_pleasantries(content: str) -> list[str]:
    """Returns a list of matched pleasantry phrases found in content."""
    matches = {m.group(0).lower() for m in _HIGH_RE.finditer(content)}
    if len(content) <= _LOW_CONF_MAX_LEN:
        matches |= {m.group(0).lower() for m in _LOW_RE.finditer(content)}
    return list(matches)


def check_context_debt(input_tokens: int, output_tokens: int) -> dict:
    """
    Returns a dict with debt_heavy (bool) and a human-readable message.
    Flags turns where the model was given far more context than it produced.
    """
    ratio = input_tokens / max(1, output_tokens)
    absolute_heavy = input_tokens > CONTEXT_DEBT_ABSOLUTE_THRESHOLD
    ratio_heavy = ratio > CONTEXT_DEBT_RATIO_THRESHOLD and input_tokens > 8_000

    debt_heavy = absolute_heavy or ratio_heavy
    message = ""
    if debt_heavy:
        message = (
            f"Input context ({input_tokens:,} tokens) is {ratio:.1f}x larger than "
            f"output ({output_tokens:,} tokens). Consider summarizing or compressing "
            f"earlier conversation history."
        )
    return {"debt_heavy": debt_heavy, "ratio": ratio, "message": message}
