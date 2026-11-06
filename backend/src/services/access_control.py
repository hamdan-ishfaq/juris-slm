"""Access control for document confidentiality — ported from V1 query.py _is_accessible."""
from __future__ import annotations

from typing import Iterable

USER_ROLES = frozenset({"member", "matter_lead", "org_admin", "owner"})
CONFIDENTIALITY_LEVELS = frozenset({"internal", "restricted", "privileged"})
MATTER_MEMBER_ROLES = frozenset({"viewer", "editor", "owner"})

MATTER_ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}


def can_access_confidentiality(user_role: str, confidentiality: str) -> bool:
    """Map V1 level_1/2/3 semantics to V2 internal/restricted/privileged."""
    role = (user_role or "member").lower()
    level = (confidentiality or "internal").lower()
    if level == "internal":
        return True
    if level == "restricted":
        return role in ("matter_lead", "org_admin", "owner")
    if level == "privileged":
        return role in ("org_admin", "owner")
    return False


def can_upload_confidentiality(user_role: str, confidentiality: str) -> bool:
    role = (user_role or "member").lower()
    level = (confidentiality or "internal").lower()
    if level == "internal":
        return True
    if level == "restricted":
        return role in ("matter_lead", "org_admin", "owner")
    if level == "privileged":
        return role in ("org_admin", "owner")
    return False


def filter_documents_by_confidentiality(documents: Iterable, user_role: str) -> list:
    return [d for d in documents if can_access_confidentiality(user_role, getattr(d, "confidentiality", "internal"))]


def matter_role_at_least(member_role: str, minimum: str) -> bool:
    return MATTER_ROLE_RANK.get(member_role, 0) >= MATTER_ROLE_RANK.get(minimum, 99)


def admin_role_at_least(user_role: str, minimum: str) -> bool:
    ranks = {"member": 1, "matter_lead": 2, "org_admin": 3, "owner": 4}
    return ranks.get(user_role, 0) >= ranks.get(minimum, 99)
