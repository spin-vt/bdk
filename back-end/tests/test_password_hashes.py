"""Legacy password-hash handling at the login endpoints.

Accounts created on the old stack store werkzeug's legacy salted format
(``sha256$<salt>$<hexdigest>``). werkzeug 3.x removed that method name, so a
raw ``check_password_hash`` raises ValueError and the login 500s instead of
logging the user in. The fix (utils/passwords.py) verifies legacy hashes with
the stdlib, never raises on malformed/None hashes, and transparently re-hashes
the account to pbkdf2:sha256 on the next successful login. Covers all three
login handlers: /auth/login and /admin/login.
"""

import hashlib
import hmac

import pytest

from tests.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


def _legacy_sha256_hash(password, salt="abc123DEF456ghi7"):
    """A stored hash exactly as old werkzeug (2.2.x ``method='sha256'``) wrote
    it: ``sha256$salt$HMAC(key=salt, msg=password, sha256).hexdigest()``.
    Verified against real werkzeug 2.2.3 output."""
    digest = hmac.new(salt.encode("utf-8"), password.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256${salt}${digest}"


# --- unit: verify_password / needs_rehash (no DB) ---------------------------


def test_verify_password_legacy_roundtrip():
    from utils.passwords import verify_password

    stored = _legacy_sha256_hash("correct horse")
    assert verify_password(stored, "correct horse") is True
    assert verify_password(stored, "wrong") is False


def test_verify_password_current_pbkdf2():
    from werkzeug.security import generate_password_hash

    from utils.passwords import verify_password

    stored = generate_password_hash("Password123!", method="pbkdf2:sha256")
    assert verify_password(stored, "Password123!") is True
    assert verify_password(stored, "nope") is False


def test_verify_password_never_raises_on_bad_input():
    from utils.passwords import verify_password

    assert verify_password(None, "anything") is False
    assert verify_password("", "anything") is False
    assert verify_password("sha256$onlyonepart", "anything") is False
    assert verify_password("total garbage", "anything") is False
    assert verify_password("md5$salt$deadbeef", "anything") is False
    assert verify_password(_legacy_sha256_hash("pw"), None) is False


def test_needs_rehash():
    from werkzeug.security import generate_password_hash

    from utils.passwords import needs_rehash

    assert needs_rehash(_legacy_sha256_hash("pw")) is True
    assert needs_rehash(generate_password_hash("pw", method="pbkdf2:sha256")) is False
    assert needs_rehash(None) is False
    assert needs_rehash("") is False


# --- integration: the three login handlers ----------------------------------


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_user(email, password_hash, **flags):
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        u = user(email=email, password=password_hash, **flags)
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


def _stored_hash(user_id):
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        return s.query(user).filter(user.id == user_id).one().password
    finally:
        s.close()


def test_auth_login_migrates_legacy_hash(client):
    uid = _make_user("legacy1@example.com", _legacy_sha256_hash("Password123!"))

    resp = client.post(
        "/auth/login", data={"email": "legacy1@example.com", "password": "Password123!"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/map"
    assert any(c.startswith("token=") for c in resp.headers.getlist("Set-Cookie"))

    # The stored hash was transparently upgraded, and the password still works.
    assert _stored_hash(uid).startswith("pbkdf2:")
    resp = client.post(
        "/auth/login", data={"email": "legacy1@example.com", "password": "Password123!"}
    )
    assert resp.status_code == 302


def test_admin_login_migrates_legacy_hash(client):
    uid = _make_user(
        "legacyadmin@example.com",
        _legacy_sha256_hash("Password123!"),
        is_platform_admin=True,
    )

    resp = client.post(
        "/admin/login", data={"email": "legacyadmin@example.com", "password": "Password123!"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/admin/"
    assert _stored_hash(uid).startswith("pbkdf2:")


def test_legacy_hash_wrong_password_rejected_not_migrated(client):
    uid = _make_user("legacy3@example.com", _legacy_sha256_hash("Password123!"))

    resp = client.post("/auth/login", data={"email": "legacy3@example.com", "password": "wrong"})
    assert resp.status_code == 200
    assert "Invalid credentials" in resp.get_data(as_text=True)
    assert _stored_hash(uid).startswith("sha256$")  # untouched on failure


def test_malformed_hash_is_invalid_credentials_not_500(client):
    # The reported bug: an unverifiable stored hash must read as bad
    # credentials on every login door, never a server error.
    _make_user("broken1@example.com", "sha256$onlyonepart")
    _make_user("broken2@example.com", None)

    for email in ("broken1@example.com", "broken2@example.com"):
        resp = client.post("/auth/login", data={"email": email, "password": "whatever"})
        assert resp.status_code == 200, email
        assert "Invalid credentials" in resp.get_data(as_text=True)

        resp = client.post("/admin/login", data={"email": email, "password": "whatever"})
        assert resp.status_code == 401, email
