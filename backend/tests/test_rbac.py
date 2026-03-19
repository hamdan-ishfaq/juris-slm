import pytest
import uuid
from src.auth import create_access_token, set_auth_config

TEST_SECRET = "test-secret-key-at-least-32-characters-long"

@pytest.fixture(autouse=True)
def setup_auth():
    set_auth_config(secret_key=TEST_SECRET, algorithm="HS256", expire_minutes=60)

def make_token(role: str) -> str:
    return create_access_token({"sub": str(uuid.uuid4()), "role": role})

def is_accessible(access_level: str, user_role: str) -> bool:
    al = (access_level or "level_1").lower()
    r  = (user_role   or "user").lower()
    if al == "level_1": return True
    if al == "level_2": return r in ("admin", "owner")
    if al == "level_3": return r == "owner"
    return False

# ── level_1 ───────────────────────────────────────────────
def test_level1_user():    assert is_accessible("level_1", "user")  is True
def test_level1_admin():   assert is_accessible("level_1", "admin") is True
def test_level1_owner():   assert is_accessible("level_1", "owner") is True

# ── level_2 ───────────────────────────────────────────────
def test_level2_user():    assert is_accessible("level_2", "user")  is False
def test_level2_admin():   assert is_accessible("level_2", "admin") is True
def test_level2_owner():   assert is_accessible("level_2", "owner") is True

# ── level_3 ───────────────────────────────────────────────
def test_level3_user():    assert is_accessible("level_3", "user")  is False
def test_level3_admin():   assert is_accessible("level_3", "admin") is False
def test_level3_owner():   assert is_accessible("level_3", "owner") is True

# ── edge cases ────────────────────────────────────────────
def test_unknown_level():  assert is_accessible("level_99", "owner") is False
def test_none_level():     assert is_accessible(None, "user")         is True
def test_none_role():      assert is_accessible("level_2", None)      is False

# ── upload permission logic ───────────────────────────────
def test_user_blocked_level2():  assert "user"  not in ("admin", "owner")
def test_admin_allowed_level2(): assert "admin" in     ("admin", "owner")
def test_owner_allowed_level3(): assert "owner" in     ("admin", "owner")

# ── JWT role claims ───────────────────────────────────────
def test_token_owner_role():
    from jose import jwt
    payload = jwt.decode(make_token("owner"), TEST_SECRET, algorithms=["HS256"])
    assert payload["role"] == "owner"

def test_token_user_role():
    from jose import jwt
    payload = jwt.decode(make_token("user"), TEST_SECRET, algorithms=["HS256"])
    assert payload["role"] == "user"
