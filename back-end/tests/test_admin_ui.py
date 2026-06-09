"""Server-rendered admin UI (/admin/*): login flow, auth redirects, page
renders, and the htmx user-filter partial.
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


def _login(client, email="op@example.com", password="Password123!"):
    return client.post("/admin/login", data={"email": email, "password": password})


# --- login / auth -----------------------------------------------------------


def test_login_page_renders(client):
    resp = client.get("/admin/login")
    assert resp.status_code == 200
    assert b"Sign in" in resp.data


def test_pages_redirect_anonymous(client):
    for path in ("/admin/", "/admin/users", "/admin/organizations", "/admin/tasks"):
        resp = client.get(path)
        assert resp.status_code in (301, 302), path
        assert "/admin/login" in resp.headers.get("Location", "")


def test_login_rejects_non_platform_admin(client):
    _make_user("regular@example.com")
    resp = _login(client, "regular@example.com")
    assert resp.status_code == 401
    assert "admin_session=" not in resp.headers.get("Set-Cookie", "")


def test_login_success_sets_cookie_and_dashboard_renders(client):
    _make_user("op@example.com", is_platform_admin=True, verified=True)
    resp = _login(client)
    assert resp.status_code in (301, 302)
    assert "/admin/" in resp.headers.get("Location", "")
    assert "admin_session=" in resp.headers.get("Set-Cookie", "")

    # The session cookie (now in the jar) lets us load the dashboard.
    dash = client.get("/admin/")
    assert dash.status_code == 200
    assert b"Dashboard" in dash.data


def test_disabled_platform_admin_cannot_log_in(client):
    _make_user("dis@example.com", is_platform_admin=True, disabled=True, verified=True)
    resp = _login(client, "dis@example.com")
    assert resp.status_code == 401


# --- pages ------------------------------------------------------------------


def test_users_and_orgs_pages_render(client):
    _make_user("op@example.com", is_platform_admin=True, verified=True)
    _make_user("someone@example.com")
    _login(client)

    users = client.get("/admin/users")
    assert users.status_code == 200
    assert b"someone@example.com" in users.data

    orgs = client.get("/admin/organizations")
    assert orgs.status_code == 200


def test_users_htmx_partial_filter(client):
    _make_user("op@example.com", is_platform_admin=True, verified=True)
    _make_user("alice@example.com")
    _make_user("bob@example.com")
    _login(client)

    # Partial request returns just the rows, filtered.
    resp = client.get("/admin/users?partial=1&q=alice", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert b"alice@example.com" in resp.data
    assert b"bob@example.com" not in resp.data
    # Fragment, not the full page chrome.
    assert b"<html" not in resp.data


def test_admin_pages_send_security_headers(client):
    _make_user("op@example.com", is_platform_admin=True, verified=True)
    _login(client)
    resp = client.get("/admin/")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'self'" in csp
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_logout_clears_cookie(client):
    # Logout is a CSRF-protected POST; the real form carries the csrf_token
    # hidden field, so mint a session whose csrf we know and submit it.
    from utils.admin_auth import mint_admin_session
    from utils.flask_app import app

    uid = _make_user("op@example.com", is_platform_admin=True, verified=True)
    with app.test_request_context():
        token, csrf = mint_admin_session(uid)
    client.set_cookie("admin_session", token)

    resp = client.post("/admin/logout", data={"csrf_token": csrf})
    assert resp.status_code in (301, 302)
    # Cookie deletion is an expired Set-Cookie for admin_session.
    assert "admin_session=" in resp.headers.get("Set-Cookie", "")
