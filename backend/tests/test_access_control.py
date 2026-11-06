import pytest

from services.access_control import (
    admin_role_at_least,
    can_access_confidentiality,
    can_upload_confidentiality,
    matter_role_at_least,
)


@pytest.mark.parametrize(
    "role,level,expected",
    [
        ("member", "internal", True),
        ("member", "restricted", False),
        ("member", "privileged", False),
        ("matter_lead", "restricted", True),
        ("matter_lead", "privileged", False),
        ("org_admin", "privileged", True),
        ("owner", "privileged", True),
    ],
)
def test_can_access_confidentiality(role, level, expected):
    assert can_access_confidentiality(role, level) is expected


@pytest.mark.parametrize(
    "role,level,expected",
    [
        ("member", "internal", True),
        ("member", "restricted", False),
        ("member", "privileged", False),
        ("matter_lead", "restricted", True),
        ("org_admin", "privileged", True),
    ],
)
def test_can_upload_confidentiality(role, level, expected):
    assert can_upload_confidentiality(role, level) is expected


def test_matter_role_hierarchy():
    assert matter_role_at_least("owner", "editor")
    assert matter_role_at_least("editor", "viewer")
    assert not matter_role_at_least("viewer", "editor")


def test_admin_role_hierarchy():
    assert admin_role_at_least("owner", "org_admin")
    assert not admin_role_at_least("member", "org_admin")
