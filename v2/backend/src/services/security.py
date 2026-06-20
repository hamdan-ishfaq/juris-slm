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
    InjectionPattern("ignore_instructions_de", r"ignoriere\s+(alle\s+)?(vorherigen\s+)?anweisungen"),
    InjectionPattern("system_prompt", r"(print|show|reveal|dump|output)\s+(your\s+)?(system\s+)?prompt"),
    InjectionPattern("jailbreak_dan", r"\bDAN\b|\bdo\s+anything\s+now\b"),
    InjectionPattern("role_override", r"you\s+are\s+now\s+(a|an)\s+"),
    InjectionPattern("roleplay_admin", r"roleplay\s+as\s+admin|act\s+as\s+admin"),
    InjectionPattern("bypass_security", r"bypass\s+(security|safety|filter|guard)"),
    InjectionPattern("developer_mode", r"developer\s+mode|god\s+mode|admin\s+mode"),
    InjectionPattern("delimiter_injection", r"<\s*/?\s*(system|assistant|user)\s*>"),
    InjectionPattern("system_delimiter", r"(^|\n)\s*---\s*\n\s*SYSTEM\s*:"),
    InjectionPattern("markdown_system", r"```\s*system"),
    InjectionPattern("base64_inject", r"decode\s+and\s+execute|base64"),
    InjectionPattern("json_inject", r'"instruction"\s*:\s*"ignore'),
    InjectionPattern("hypothetical_override", r"hypothetically,?\s+if\s+you\s+had\s+no\s+rules"),
    InjectionPattern("export_emails", r"export\s+all\s+user\s+emails"),
    InjectionPattern("credentials", r"database\s+credentials|show\s+secrets"),
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


# L3 — lightweight heuristic beyond regex (no ML model required)
_L3_SUSPICIOUS = (
    "sudo ",
    "exec(",
    "eval(",
    "<script",
    "javascript:",
    "union select",
    "drop table",
)


def check_injection_l3(text: str) -> dict:
    """Layer 3 sentinel — additional patterns for portfolio completeness."""
    lower = (text or "").lower()
    hits = [h for h in _L3_SUSPICIOUS if h in lower]
    if hits:
        return {"blocked": True, "tags": [f"l3:{h}" for h in hits]}
    return {"blocked": False, "tags": []}


def check_injection_full(text: str) -> dict:
    l2 = check_injection(text)
    if l2["blocked"]:
        return l2
    return check_injection_l3(text)
