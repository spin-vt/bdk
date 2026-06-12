"""The server-rendered auth pages (/auth/*).

Pins the full round-trip on the new shell: register → cookie session →
/setup; login (wrong creds stay on the page, right creds set the `token`
cookie and land on /map); the reset request never reveals whether an email
exists; the tokened reset sets a new password that then logs in; logout
clears the cookies; unauthenticated app pages 302 to /auth/login. The SPA's
/api auth endpoints stay untouched and in parallel until cutover.
"""

import pytest

from tests.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    mail = app.extensions.get("mail")
    prev = getattr(mail, "suppress", None)
    if mail:
        mail.suppress = True
    with app.test_client() as c:
        yield c
    if mail and prev is not None:
        mail.suppress = prev


def test_pages_render(client):
    for path, marker in [
        ("/auth/login", "Sign in"),
        ("/auth/register", "Create an account"),
        ("/auth/reset", "Reset your password"),
    ]:
        html = client.get(path).get_data(as_text=True)
        assert marker in html
        assert "bdk.css" in html  # the new shell, not the SPA


def test_auth_pages_carry_the_design_tokens(client, db_session):
    """bdk.css scopes every design token to body.app — an auth page without
    that class renders token-less (transparent card, fallback fonts). The
    body must be class="app" and follow the admin-picked site theme."""
    from controllers.database_controller import setting_ops

    html = client.get("/auth/login").get_data(as_text=True)
    assert '<body class="app">' in html

    setting_ops.set_setting("site_theme", "civic-vt", db_session)
    try:
        html = client.get("/auth/login").get_data(as_text=True)
        assert '<body class="app theme-civic-vt">' in html
    finally:
        setting_ops.set_setting("site_theme", "civic-light", db_session)


def test_register_logs_in_and_lands_on_setup(client, db_session):
    resp = client.post(
        "/auth/register",
        data={"email": "authpage1@example.com", "password": "Password123!"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/setup"
    cookies = resp.headers.getlist("Set-Cookie")
    assert any(c.startswith("token=") for c in cookies)

    # Duplicate registration re-renders with the error.
    resp = client.post(
        "/auth/register",
        data={"email": "authpage1@example.com", "password": "Password123!"},
    )
    assert resp.status_code == 200
    assert "already exists" in resp.get_data(as_text=True)


def test_login_round_trip_and_bad_creds(client, db_session):
    client.post(
        "/auth/register", data={"email": "authpage2@example.com", "password": "Password123!"}
    )
    client.post("/auth/logout")

    resp = client.post("/auth/login", data={"email": "authpage2@example.com", "password": "wrong"})
    assert resp.status_code == 200
    assert "Invalid credentials" in resp.get_data(as_text=True)

    resp = client.post(
        "/auth/login", data={"email": "authpage2@example.com", "password": "Password123!"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/map"
    # The session works on an app page now.
    assert client.get("/org").status_code == 200


def test_logout_clears_the_session(client, db_session):
    client.post(
        "/auth/register", data={"email": "authpage3@example.com", "password": "Password123!"}
    )
    assert client.get("/org").status_code == 200
    resp = client.post("/auth/logout")
    assert resp.status_code == 302
    resp = client.get("/org")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/auth/login")


def test_reset_request_never_reveals_accounts(client, db_session):
    html = client.post("/auth/reset", data={"email": "nobody-here@example.com"}).get_data(
        as_text=True
    )
    assert "on its way" in html  # same copy whether or not the account exists


def test_tokened_reset_sets_a_usable_password(client, db_session):
    from routes._email import create_email_token

    client.post(
        "/auth/register", data={"email": "authpage4@example.com", "password": "OldPass123!"}
    )
    client.post("/auth/logout")
    from database.models import user as user_model

    u = db_session.query(user_model).filter_by(email="authpage4@example.com").one()
    token = create_email_token(userid=u.id, email=u.email, operation="reset_password")

    html = client.get(f"/auth/reset/{token}").get_data(as_text=True)
    assert "Set a new password" in html
    resp = client.post(f"/auth/reset/{token}", data={"password": "NewPass456!"})
    assert resp.status_code == 302 and resp.headers["Location"] == "/auth/login"

    resp = client.post(
        "/auth/login", data={"email": "authpage4@example.com", "password": "NewPass456!"}
    )
    assert resp.status_code == 302

    # Garbage token: a plain-words error, no 500.
    resp = client.post("/auth/reset/not-a-token", data={"password": "x"})
    assert "is not valid" in resp.get_data(as_text=True)


def test_unauthenticated_app_pages_bounce_to_new_login(client):
    for path in ("/org", "/files", "/map", "/submissions", "/setup"):
        resp = client.get(path)
        assert resp.status_code == 302
        assert resp.headers["Location"].startswith("/auth/login"), path


def test_self_registration_verification_round_trip(client, db_session):
    """The complete self-serve flow: register sends a verification email with
    a clickable /auth/verify link; an unverified session wears the header
    banner (with resend); clicking the link verifies and the banner clears."""
    from routes._email import create_email_token

    resp = client.post(
        "/auth/register", data={"email": "selfreg@example.com", "password": "Password123!"}
    )
    assert resp.status_code == 302
    from database.models import user as user_model

    u = db_session.query(user_model).filter_by(email="selfreg@example.com").one()
    assert u.verified in (False, None)

    # Unverified: the banner (with resend) is on every page.
    html = client.get("/org").get_data(as_text=True)
    assert "verify your email" in html and "/auth/verify/resend" in html

    # Resend works from the banner.
    resp = client.post("/auth/verify/resend")
    assert resp.status_code == 302

    # The emailed link verifies.
    token = create_email_token(userid=u.id, email=u.email, operation="email_address_verification")
    html = client.get(f"/auth/verify/{token}").get_data(as_text=True)
    assert "Email verified ✓" in html
    db_session.expire_all()
    assert db_session.query(user_model).filter_by(email="selfreg@example.com").one().verified

    html = client.get("/org").get_data(as_text=True)
    assert "verify your email" not in html

    # A reset token can't masquerade as a verify token.
    bad = create_email_token(userid=u.id, email=u.email, operation="reset_password")
    html = client.get(f"/auth/verify/{bad}").get_data(as_text=True)
    assert "is not valid" in html
