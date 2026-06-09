"""Admin API (/admin/api/*): impersonation, password resets, role/flag
mutations, deletes. All require the admin_session cookie + CSRF; all audited.
"""

import pytest
from werkzeug.security import generate_password_hash

from tests.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_user(email, password="Password123!", **flags):
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        u = user(
            email=email,
            password=generate_password_hash(password, method="pbkdf2:sha256"),
            **flags,
        )
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


def _mint_admin_session(uid):
    from utils.admin_auth import mint_admin_session
    from utils.flask_app import app

    with app.test_request_context():
        return mint_admin_session(uid)


def _operator(client, verified=True):
    """Create a platform-admin operator, install their admin_session cookie on
    the client's cookie jar, and return (operator_id, csrf). Requests then only
    need the X-CSRF-Token header."""
    uid = _make_user("operator@example.com", is_platform_admin=True, verified=verified)
    token, csrf = _mint_admin_session(uid)
    client.set_cookie("admin_session", token)
    return uid, csrf


def _csrf(csrf):
    return {"X-CSRF-Token": csrf}


def _audit(action):
    from database.models import audit_log
    from database.sessions import Session

    s = Session()
    try:
        return s.query(audit_log).filter(audit_log.action == action).all()
    finally:
        s.close()


# --- guard / CSRF on the admin API ------------------------------------------


def test_impersonate_requires_admin_session(client):
    target = _make_user("t1@example.com")
    resp = client.post(f"/admin/api/users/{target}/impersonate")
    assert resp.status_code == 401


def test_admin_api_requires_csrf(client):
    _op, _csrf_tok = _operator(client)
    target = _make_user("t2@example.com")
    # admin_session present but no CSRF header -> 403
    resp = client.post(f"/admin/api/users/{target}/impersonate")
    assert resp.status_code == 403


# --- impersonation ----------------------------------------------------------


def test_impersonate_sets_app_token_keeps_admin_session(client):
    op_id, csrf = _operator(client)
    target = _make_user("victim@example.com", verified=True)

    resp = client.post(f"/admin/api/users/{target}/impersonate", headers=_csrf(csrf))
    assert resp.status_code == 200, resp.get_json()
    assert resp.headers.get("HX-Redirect") == "/"
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "token=" in set_cookie
    # admin_session must NOT be cleared/overwritten by impersonation.
    assert "admin_session=" not in set_cookie

    # The SPA now reports the impersonator (the operator's email) via /api/user.
    me = client.get("/api/user")
    assert me.status_code == 200, me.get_json()
    assert me.get_json()["userinfo"]["impersonator"] == "operator@example.com"

    assert len(_audit("impersonate_start")) == 1

    # "Return to admin" clears the app token (GET, no CSRF) but keeps admin_session.
    stop = client.get("/admin/api/impersonate/stop")
    assert stop.status_code in (301, 302)
    assert len(_audit("impersonate_end")) == 1


def _token_from_set_cookie(resp):
    """Pull the app `token` cookie value out of a Set-Cookie response header."""
    for part in resp.headers.get_all("Set-Cookie"):
        if part.startswith("token="):
            return part.split("token=", 1)[1].split(";", 1)[0]
    return None


def test_impersonation_token_is_short_lived(client):
    import jwt as pyjwt
    from flask import current_app

    _op, csrf = _operator(client)
    target = _make_user("shortlived@example.com", verified=True)
    resp = client.post(f"/admin/api/users/{target}/impersonate", headers=_csrf(csrf))
    assert resp.status_code == 200
    token = _token_from_set_cookie(resp)
    assert token
    with client.application.app_context():
        claims = pyjwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            options={"verify_sub": False},
        )
    # Impersonation tokens live ~30 min, NOT the app default 7 days.
    assert 0 < (claims["exp"] - claims["iat"]) <= 30 * 60 + 5


def test_cannot_impersonate_self_admin_or_disabled(client):
    op_id, csrf = _operator(client)
    # self
    assert (
        client.post(f"/admin/api/users/{op_id}/impersonate", headers=_csrf(csrf)).status_code == 400
    )
    # another platform admin
    other_admin = _make_user("other-admin@example.com", is_platform_admin=True, verified=True)
    assert (
        client.post(f"/admin/api/users/{other_admin}/impersonate", headers=_csrf(csrf)).status_code
        == 400
    )
    # a disabled user
    disabled = _make_user("disabled-target@example.com", disabled=True, verified=True)
    assert (
        client.post(f"/admin/api/users/{disabled}/impersonate", headers=_csrf(csrf)).status_code
        == 400
    )


# --- password reset (both modes) --------------------------------------------


def test_reset_password_temp_returns_working_password(client):
    _op, csrf = _operator(client)
    target = _make_user("needsreset@example.com", verified=True)

    resp = client.post(
        f"/admin/api/users/{target}/reset-password", headers=_csrf(csrf), json={"mode": "temp"}
    )
    assert resp.status_code == 200, resp.get_json()
    temp = resp.get_json()["temp_password"]
    assert temp

    # The temp password actually logs the user in.
    login = client.post("/api/login", json={"email": "needsreset@example.com", "password": temp})
    assert login.get_json()["status"] == "success"

    # The plaintext must never be written to the audit trail.
    rows = _audit("password_reset_temp")
    assert len(rows) == 1
    assert temp not in str(rows[0].details)


def test_reset_password_email(client, monkeypatch):
    import routes._email as email_mod

    sent = {}
    monkeypatch.setattr(email_mod.mail, "send", lambda msg: sent.setdefault("to", msg.recipients))

    _op, csrf = _operator(client)
    target = _make_user("mailme@example.com", verified=True)
    resp = client.post(
        f"/admin/api/users/{target}/reset-password", headers=_csrf(csrf), json={"mode": "email"}
    )
    assert resp.status_code == 200, resp.get_json()
    assert sent.get("to") == ["mailme@example.com"]
    assert len(_audit("password_reset_email")) == 1


# --- flags / roles ----------------------------------------------------------


def test_toggle_verified_and_disabled(client):
    _op, csrf = _operator(client)
    target = _make_user("flags@example.com", verified=False)

    client.post(f"/admin/api/users/{target}/verified", headers=_csrf(csrf), json={"value": "true"})
    client.post(f"/admin/api/users/{target}/disabled", headers=_csrf(csrf), json={"value": "true"})

    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        u = s.query(user).filter(user.id == target).one()
        assert u.verified is True
        assert u.disabled is True
    finally:
        s.close()

    # Disabled now blocks login.
    login = client.post(
        "/api/login", json={"email": "flags@example.com", "password": "Password123!"}
    )
    assert login.status_code == 403


def test_cannot_revoke_own_platform_admin(client):
    op_id, csrf = _operator(client)
    resp = client.post(
        f"/admin/api/users/{op_id}/platform-admin", headers=_csrf(csrf), json={"value": "false"}
    )
    assert resp.status_code == 400
    assert "your own" in resp.get_json()["message"].lower()


def test_grant_platform_admin(client):
    _op, csrf = _operator(client)
    target = _make_user("promote@example.com")
    resp = client.post(
        f"/admin/api/users/{target}/platform-admin", headers=_csrf(csrf), json={"value": "true"}
    )
    assert resp.status_code == 200
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        assert s.query(user).filter(user.id == target).one().is_platform_admin is True
    finally:
        s.close()
    assert len(_audit("set_platform_admin")) == 1


# --- deletes (typed confirmation) -------------------------------------------


def test_delete_user_requires_typed_confirmation(client):
    _op, csrf = _operator(client)
    target = _make_user("deleteme@example.com")

    wrong = client.post(
        f"/admin/api/users/{target}/delete",
        headers=_csrf(csrf),
        json={"confirm_name": "not-the-email"},
    )
    assert wrong.status_code == 400

    ok = client.post(
        f"/admin/api/users/{target}/delete",
        headers=_csrf(csrf),
        json={"confirm_name": "deleteme@example.com"},
    )
    assert ok.status_code == 200

    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        assert s.query(user).filter(user.id == target).first() is None
    finally:
        s.close()
    assert len(_audit("delete_user")) == 1


def test_delete_organization_requires_typed_confirmation(client):
    from database.models import organization
    from database.sessions import Session

    s = Session()
    try:
        org = organization(name="DeleteOrg ISP", provider_id=1, brand_name="x")
        s.add(org)
        s.commit()
        org_id = org.id
    finally:
        s.close()

    _op, csrf = _operator(client)

    wrong = client.post(
        f"/admin/api/organizations/{org_id}/delete",
        headers=_csrf(csrf),
        json={"confirm_name": "wrong"},
    )
    assert wrong.status_code == 400

    ok = client.post(
        f"/admin/api/organizations/{org_id}/delete",
        headers=_csrf(csrf),
        json={"confirm_name": "DeleteOrg ISP"},
    )
    assert ok.status_code == 200
    s = Session()
    try:
        assert s.query(organization).filter(organization.id == org_id).first() is None
    finally:
        s.close()
    assert len(_audit("delete_organization")) == 1


def test_cannot_delete_own_organization(client):
    from database.models import organization, user
    from database.sessions import Session

    op_id, csrf = _operator(client)
    s = Session()
    try:
        org = organization(name="Operators Org", provider_id=2, brand_name="x")
        s.add(org)
        s.flush()
        s.query(user).filter(user.id == op_id).one().organization_id = org.id
        s.commit()
        org_id = org.id
    finally:
        s.close()

    resp = client.post(
        f"/admin/api/organizations/{org_id}/delete",
        headers=_csrf(csrf),
        json={"confirm_name": "Operators Org"},
    )
    assert resp.status_code == 400
    assert "belong" in resp.get_json()["message"].lower()
