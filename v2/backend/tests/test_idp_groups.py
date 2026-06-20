"""Phase 9C — IdP group mapping unit tests."""
from services.idp_groups import map_groups_to_role


def test_map_groups_prefers_highest_role():
    role = map_groups_to_role(["jurisguard-users", "jurisguard-admins"], {})
    assert role == "org_admin"


def test_org_custom_map_overrides_default():
    role = map_groups_to_role(
        ["custom-leads"],
        {"idp_group_role_map": {"custom-leads": "matter_lead"}},
    )
    assert role == "matter_lead"


def test_empty_groups_default_member():
    assert map_groups_to_role([], {}) == "member"
