"""Reject chat input that plainly addresses the model's instructions, or is too long to be a question."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionPattern:
    name: str
    pattern: str
    flags: int = re.IGNORECASE


# Only wording aimed at the model itself. Topic words such as "base64", "bypass", "credentials" or the name "Dan" also appear in
# ordinary legal questions and blocked 11 of 20 of them, so they are not here. See docs/DECISIONS.md, D-013.
INJECTION_PATTERNS: tuple[InjectionPattern, ...] = (
    InjectionPattern("ignore_instructions", r"ignore\s+(all\s+)?previous\s+instructions"),
    InjectionPattern("ignore_instructions_de", r"ignoriere\s+(alle\s+)?(vorherigen\s+)?anweisungen"),
    InjectionPattern("system_prompt", r"(print|show|reveal|dump|output)\s+(your\s+)?(system\s+)?(prompt|instructions)"),
    InjectionPattern("jailbreak_dan", r"\bdo\s+anything\s+now\b"),
    InjectionPattern("delimiter_injection", r"<\s*/?\s*(system|assistant|user)\s*>"),
    InjectionPattern("system_delimiter", r"(^|\n)\s*---\s*\n\s*SYSTEM\s*:"),
    InjectionPattern("markdown_system", r"```\s*system"),
    InjectionPattern("json_inject", r'"instruction"\s*:\s*"ignore'),
)

_COMPILED = [(re.compile(p.pattern, p.flags), p.name) for p in INJECTION_PATTERNS]


def check_injection(text: str) -> dict:
    """Return match tags; non-empty tags mean the query should be rejected."""
    tags: list[str] = []
    raw = text or ""
    if len(raw) > 2000:
        tags.append("excessive_length")
    # Flooding: repeated ignore instructions
    if raw.lower().count("ignore") >= 20:
        tags.append("instruction_flooding")
    for regex, name in _COMPILED:
        if regex.search(raw):
            tags.append(name)
    return {"blocked": bool(tags), "tags": tags}

