"""Security hardening of the app's auth surface.

Pins: email tokens are purpose-bound (aud) and UTC-expiring; tokens of one
type can't be replayed as another; registration input is validated; the
session cookie is HttpOnly even in dev; cookie-auth'd mutating API calls
require the CSRF double-submit header; a disabled user's outstanding token
stops working immediately; prod refuses a weak JWT secret.
"""

from datetime import UTC

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
    with app.test_client() as c:
        yield c


def _register(client, email="sec@example.com", password="Password123!"):
    resp = client.post("/auth/register", data={"email": email, "password": password})
    assert resp.status_code == 302, resp.get_data(as_text=True)
    return resp


def _user(s, email="sec@example.com"):
    from database.models import user

    return s.query(user).filter(user.email == email).one()


# --- email tokens: purpose-bound + UTC expiry --------------------------------


def test_email_token_round_trip_and_claims(client, db_session):
    """The token verifies through the real endpoint (UTC expiry — this fails
    on a non-UTC host if expiry is minted from naive local time), and carries
    a purpose audience."""
    from datetime import datetime

    import jwt as pyjwt

    from routes._email import EMAIL_TOKEN_AUDIENCE, create_email_token

    _register(client)
    uid = _user(db_session).id

    token = create_email_token(
        userid=uid, email="sec@example.com", operation="email_address_verification"
    )
    from utils.flask_app import app

    decoded = pyjwt.decode(
        token,
        app.config["JWT_SECRET_KEY"],
        algorithms=["HS256"],
        audience=EMAIL_TOKEN_AUDIENCE,
        options={"verify_sub": False},
    )
    assert decoded["exp"] > datetime.now(UTC).timestamp()

    html = client.get(f"/auth/verify/{token}").get_data(as_text=True)
    assert "not valid" not in html
    db_session.expire_all()
    assert _user(db_session).verified is True


def test_app_token_rejected_as_email_token(client, db_session):
    """A session cookie JWT (same signing key) must not pass for an email
    verification/reset token."""
    from flask_jwt_extended import create_access_token

    from utils.flask_app import app

    _register(client)
    uid = _user(db_session).id
    with app.app_context():
        app_token = create_access_token(identity={"id": uid})

    html = client.get(f"/auth/verify/{app_token}").get_data(as_text=True)
    assert "not valid" in html

    resp = client.post(f"/auth/reset/{app_token}", data={"password": "NewPass123!"})
    assert resp.status_code == 200  # the error page, not the success redirect
    # The password did not change: the original still logs in.
    client.post("/auth/logout")
    ok = client.post("/auth/login", data={"email": "sec@example.com", "password": "Password123!"})
    assert ok.status_code == 302


def test_email_token_rejected_as_session_cookie(client, db_session):
    """An email token (sent over email, far weaker custody) must not work as
    the app session cookie."""
    from routes._email import create_email_token

    _register(client)
    uid = _user(db_session).id
    token = create_email_token(
        userid=uid, email="sec@example.com", operation="email_address_verification"
    )
    client.set_cookie("token", token)
    # 422 = flask-jwt-extended's "wrong audience" rejection; 401 = no/invalid
    # token. Either way: not authenticated (an authenticated call would 404
    # on the bad tile coordinates instead).
    resp = client.get("/api/tiles/abc/9/143/199.pbf")
    assert resp.status_code in (401, 422)


# --- CSRF: cookie-auth'd mutating requests need the double-submit header -------


def _csrf_headers(client):
    cookie = client.get_cookie("csrf_access_token")
    return {"X-CSRF-TOKEN": cookie.value} if cookie else {}


def test_mutating_request_requires_csrf_header(client, db_session):
    """Registration sets a JS-readable csrf_access_token cookie; mutating API
    calls must echo it in X-CSRF-TOKEN (double-submit), so a cross-site form
    can't ride the session cookie."""
    _register(client)
    assert client.get_cookie("csrf_access_token") is not None

    body = {"file_ids": [], "editfile_ids": []}
    resp = client.delete("/api/delfiles", json=body)  # no header
    assert resp.status_code == 401

    # With the header the CSRF gate passes and the handler's own validation
    # answers instead (empty selection -> 400).
    resp = client.delete("/api/delfiles", json=body, headers=_csrf_headers(client))
    assert resp.status_code == 400


def test_get_requests_do_not_need_csrf(client, db_session):
    _register(client)
    # No X-CSRF-TOKEN header: an authenticated GET must not 401; the bad tile
    # coordinates 404 instead.
    resp = client.get("/api/tiles/abc/9/143/199.pbf")
    assert resp.status_code == 404


# --- registration input validation --------------------------------------------


def test_register_rejects_invalid_email(client, db_session):
    from database.models import user

    resp = client.post("/auth/register", data={"email": "nope", "password": "Password123!"})
    assert resp.status_code == 200
    assert "valid email" in resp.get_data(as_text=True)
    assert db_session.query(user).filter(user.email == "nope").first() is None


def test_register_rejects_empty_password(client, db_session):
    from database.models import user

    resp = client.post("/auth/register", data={"email": "ok@example.com", "password": ""})
    assert resp.status_code == 200
    assert "password" in resp.get_data(as_text=True).lower()
    assert db_session.query(user).filter(user.email == "ok@example.com").first() is None


# --- cookie flags ---------------------------------------------------------------


def test_login_cookie_is_httponly_even_in_dev(client, db_session):
    _register(client)
    client.post("/auth/logout")
    resp = client.post("/auth/login", data={"email": "sec@example.com", "password": "Password123!"})
    cookie_headers = [h for h in resp.headers.getlist("Set-Cookie") if h.startswith("token=")]
    assert cookie_headers, "login should set the token cookie"
    assert "HttpOnly" in cookie_headers[0]


# --- disabled users lose access immediately -------------------------------------


def test_disabled_user_token_rejected_immediately(client, db_session):
    _register(client)
    resp = client.get("/api/tiles/abc/9/143/199.pbf")
    assert resp.status_code == 404  # authenticated: validation answers

    u = _user(db_session)
    u.disabled = True
    db_session.commit()

    resp = client.get("/api/tiles/abc/9/143/199.pbf")
    assert resp.status_code == 401  # same token, now rejected per-request


# --- prod config validation ------------------------------------------------------


def test_prod_refuses_weak_jwt_secret():
    from utils.config import validate_prod_secrets

    validate_prod_secrets(in_production=False, jwt_secret="short")  # dev: fine
    validate_prod_secrets(in_production=True, jwt_secret="x" * 32)  # long enough
    with pytest.raises(RuntimeError):
        validate_prod_secrets(in_production=True, jwt_secret="short")
    with pytest.raises(RuntimeError):
        validate_prod_secrets(in_production=True, jwt_secret=None)
