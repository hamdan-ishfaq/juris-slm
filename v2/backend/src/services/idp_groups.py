"""Phase 9C — IdP group → JurisGuard role mapping."""
from __future__ import annotations

DEFAULT_GROUP_ROLE_MAP = {
    "jurisguard-admins": "org_admin",
    "jurisguard-owners": "owner",
    "jurisguard-leads": "matter_lead",
    "jurisguard-users": "member",
}


def map_groups_to_role(groups: list[str] | None, org_settings: dict | None) -> str:
    """Map IdP/SCIM groups to a JurisGuard org role."""
    settings = org_settings or {}
    mapping: dict[str, str] = {**DEFAULT_GROUP_ROLE_MAP, **(settings.get("idp_group_role_map") or {})}
    rank = {"member": 1, "matter_lead": 2, "org_admin": 3, "owner": 4}
    best = "member"
    for group in groups or []:
        role = mapping.get(str(group).lower()) or mapping.get(str(group))
        if role and rank.get(role, 0) > rank.get(best, 0):
            best = role
    return best
