"""Platform-admin model fields + the require_platform_admin guard.

The guard is the security core of the admin panel: a separate admin session
cookie (`admin_session`), distinct from the app's `token` cookie, validated by
manually decoding a JWT (NOT via flask-jwt-extended, which owns the single
`token` access cookie). These tests pin its behavior without a database by
stubbing the user lookup; full DB-backed coverage rides on the real admin
routes.
"""

import pytest

from utils.flask_app import app

# --- model fields -----------------------------------------------------------


def test_user_model_has_platform_admin_and_disabled_columns():
    from database.models import user

    cols = user.__table__.columns
    assert "is_platform_admin" in cols, "user.is_platform_admin column missing"
    assert "disabled" in cols, "user.disabled column missing"
    # Both default to False and are NOT NULL (server_default backfills old rows).
    assert cols["is_platform_admin"].default.arg is False
    assert cols["disabled"].default.arg is False
    assert cols["is_platform_admin"].nullable is False
    assert cols["disabled"].nullable is False


# --- guard ------------------------------------------------------------------


class _FakeUser:
    def __init__(self, id=1, is_platform_admin=True, disabled=False, email="op@example.com"):
        self.id = id
        self.is_platform_admin = is_platform_admin
        self.disabled = disabled
        self.email = email


@pytest.fixture
def stub_user(monkeypatch):
    """Make the guard's DB lookup return a configurable fake user (no DB)."""
    import utils.admin_auth as admin_auth

    holder = {"user": _FakeUser()}
    monkeypatch.setattr(admin_auth, "get_session", lambda: None)
    monkeypatch.setattr(
        admin_auth.user_ops, "get_user_with_id", lambda uid, session=None: holder["user"]
    )
    return holder


def _probe():
    """A trivial view to wrap with the guard."""
    return "OK"


def _call_guarded(path, method="GET", cookie=None, headers=None):
    """Invoke the guarded probe inside a request context and normalize the
    result to (status_code, body)."""
    from utils.admin_auth import require_platform_admin

    guarded = require_platform_admin(_probe)
    hdrs = dict(headers or {})
    if cookie is not None:
        hdrs["Cookie"] = cookie
    with app.test_request_context(path, method=method, headers=hdrs):
        rv = guarded()
        resp = app.make_response(rv)
        return resp.status_code, resp.get_data(as_text=True)


def _mint(**claims_override):
    with app.test_request_context():
        from utils.admin_auth import mint_admin_session

        token, csrf = mint_admin_session(claims_override.get("user_id", 1))
        return token, csrf


def test_no_cookie_api_path_returns_401():
    code, _ = _call_guarded("/admin/api/probe")
    assert code == 401


def test_no_cookie_ui_path_redirects_to_login():
    code, _ = _call_guarded("/admin/probe")
    assert code in (301, 302)


def test_app_token_cookie_cannot_reach_admin():
    # A valid *app* token (the SPA's `token` cookie) must NOT authenticate to
    # the admin panel — the guard only ever reads `admin_session`.
    code, _ = _call_guarded("/admin/api/probe", cookie="token=anything.app.jwt")
    assert code == 401


def test_valid_admin_token_passes(stub_user):
    token, _ = _mint()
    code, body = _call_guarded("/admin/api/probe", cookie=f"admin_session={token}")
    assert code == 200
    assert body == "OK"


def test_disabled_platform_admin_is_forbidden(stub_user):
    stub_user["user"] = _FakeUser(is_platform_admin=True, disabled=True)
    token, _ = _mint()
    code, _ = _call_guarded("/admin/api/probe", cookie=f"admin_session={token}")
    assert code == 403


def test_revoked_platform_admin_is_forbidden(stub_user):
    # Flag flipped off in the DB after the token was minted -> next request 403
    # (the guard re-reads the user every request; stateless token, live check).
    stub_user["user"] = _FakeUser(is_platform_admin=False)
    token, _ = _mint()
    code, _ = _call_guarded("/admin/api/probe", cookie=f"admin_session={token}")
    assert code == 403


def test_user_lookup_error_string_is_rejected(stub_user):
    # get_user_with_id returns a *string* on DB error — must not be treated as a
    # user object.
    stub_user["user"] = "some db error message"
    token, _ = _mint()
    code, _ = _call_guarded("/admin/api/probe", cookie=f"admin_session={token}")
    assert code in (401, 403)


def test_wrong_typ_claim_is_rejected(stub_user):
    # A token signed with the right key but not minted as an admin session.
    import jwt

    with app.test_request_context():
        from flask import current_app

        bad = jwt.encode(
            {"typ": "email", "sub": {"id": 1}},
            current_app.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
    code, _ = _call_guarded("/admin/api/probe", cookie=f"admin_session={bad}")
    assert code == 401


def test_csrf_required_for_unsafe_methods(stub_user):
    token, csrf = _mint()
    # POST without the CSRF header -> 403
    code, _ = _call_guarded("/admin/api/probe", method="POST", cookie=f"admin_session={token}")
    assert code == 403
    # POST with the matching CSRF header -> passes
    code, _ = _call_guarded(
        "/admin/api/probe",
        method="POST",
        cookie=f"admin_session={token}",
        headers={"X-CSRF-Token": csrf},
    )
    assert code == 200
