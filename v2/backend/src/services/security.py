"""Layered prompt-injection defense — L2 regex (ported from V1 security.py patterns)."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionPattern:
    name: str
    pattern: str
    flags: int = re.IGNORECASE


INJECTION_PATTERNS: tuple[InjectionPattern, ...] = (
    InjectionPattern("ignore_instructions", r"ignore\s+(all\s+)?previous\s+instructions"),
    InjectionPattern("system_prompt", r"(print|show|reveal|dump|output)\s+(your\s+)?(system\s+)?prompt"),
    InjectionPattern("jailbreak_dan", r"\bDAN\b|\bdo\s+anything\s+now\b"),
    InjectionPattern("role_override", r"you\s+are\s+now\s+(a|an)\s+"),
    InjectionPattern("bypass_security", r"bypass\s+(security|safety|filter|guard)"),
    InjectionPattern("developer_mode", r"developer\s+mode|god\s+mode|admin\s+mode"),
    InjectionPattern("delimiter_injection", r"<\s*/?\s*(system|assistant|user)\s*>"),
)

_COMPILED = [(re.compile(p.pattern, p.flags), p.name) for p in INJECTION_PATTERNS]


def check_injection(text: str) -> dict:
    """Return match tags; non-empty tags mean the query should be rejected."""
    tags: list[str] = []
    for regex, name in _COMPILED:
        if regex.search(text or ""):
            tags.append(name)
    return {"blocked": bool(tags), "tags": tags}
