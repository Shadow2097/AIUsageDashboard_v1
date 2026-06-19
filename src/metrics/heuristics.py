"""
Heuristics — provider-agnostic prompt analysis.

Detects low-value patterns (pleasantries, context debt) in turn content.
Individual checks can be extended or tuned per provider in the future.
"""

import re

PLEASANTRY_PATTERNS = [
    r"\bplease\b", r"\bthank you\b", r"\bthanks\b", r"\bthank\b",
    r"\bgreat\b", r"\bawesome\b", r"\bperfect\b", r"\bwonderful\b",
    r"\bexcellent\b", r"\bsounds good\b", r"\bgot it\b", r"\bsure\b",
    r"\bof course\b", r"\bcertainly\b", r"\babsolutely\b", r"\bhello\b",
    r"\bhi\b", r"\bhey\b",
]

_PLEASANTRY_RE = re.compile("|".join(PLEASANTRY_PATTERNS), re.IGNORECASE)

CONTEXT_DEBT_RATIO_THRESHOLD = 15.0   # input/output ratio above this = debt warning
CONTEXT_DEBT_ABSOLUTE_THRESHOLD = 40_000  # input tokens above this = debt warning


def detect_pleasantries(content: str) -> list[str]:
    """Returns a list of matched pleasantry phrases found in content."""
    return list({m.group(0).lower() for m in _PLEASANTRY_RE.finditer(content)})


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
