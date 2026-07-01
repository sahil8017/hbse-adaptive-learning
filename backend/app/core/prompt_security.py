import re
import unicodedata
from typing import Any, Dict, List


PROMPT_INJECTION_PATTERNS = [
    # Canonical ignore/override attempts
    r"ignore (all|any|the|your|previous|earlier) (instructions|rules|guardrails)",
    r"override (all|any|the|your|previous|earlier) (instructions|rules|guardrails)",
    # Forget-instructions variants: allow filler words between "forget" and the target
    r"forget .{0,20}(instructions|rules|guardrails)",
    # Reveal-prompt variants: allow filler words between "reveal" and the target
    r"reveal .{0,30}(prompt|instructions)",
    # Persona/role hijacks
    r"(act|pretend) as (a|an|the)? ?(different|another|unrestricted|developer|system)",
    r"you are now",
    # Exploitation keywords (allow spacing evasion via \s*)
    r"developer\s*mode",
    r"jail\s*break",
    r"bypass (safety|guardrails|filters|rules)",
    r"tool\s*call",
    r"function\s*call",
    r"chain of thought",
    r"prompt\s*injection",
]


def _normalize_for_detection(text: str) -> str:
    """Normalize Unicode and collapse whitespace so lookalike-character and
    zero-width-padding evasions don't slip past the pattern match.

    NFKC folds homoglyphs/compatibility forms (e.g. fullwidth, Cyrillic 'е'
    decompositions) toward their ASCII equivalents; the whitespace pass
    collapses runs and strips zero-width joiners/spaces and the BOM.
    """
    normalized = unicodedata.normalize("NFKC", text or "")
    # \s plus the zero-width joiners/non-joiners/space and BOM that NFKC leaves intact.
    normalized = re.sub("[\\s​‌‍﻿]+", " ", normalized)
    return normalized.lower().strip()


def contains_prompt_injection(text: str) -> bool:
    normalized = _normalize_for_detection(text)
    if not normalized:
        return False
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in PROMPT_INJECTION_PATTERNS)


def sanitize_history(history: List[Dict[str, Any]], max_turns: int = 8, max_chars: int = 600) -> List[Dict[str, str]]:
    cleaned: List[Dict[str, str]] = []
    for turn in history[-max_turns:]:
        role = str(turn.get("role") or turn.get("sender") or "user").lower()
        if role not in {"user", "assistant", "student"}:
            role = "user"
        content = str(turn.get("content") or turn.get("message") or "").strip()
        if not content:
            continue
        cleaned.append({
            "role": "user" if role in {"user", "student"} else "assistant",
            "content": content[:max_chars],
        })
    return cleaned
