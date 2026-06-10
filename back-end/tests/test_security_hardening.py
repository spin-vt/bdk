"""Security hardening of the existing app's auth surface.

Pins: email tokens are purpose-bound (aud) and UTC-expiring; tokens of one
type can't be replayed as another; profile/registration input is validated
(notably: a missing JSON field must never coerce to the string "None");
the session cookie is HttpOnly even in dev; a disabled user's outstanding
token stops working immediately; prod refuses a weak JWT secret.
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
    resp = client.post("/api/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
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

    resp = client.post("/api/verify_token", json={"token": token})
    assert resp.status_code == 200, resp.get_json()
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

    resp = client.post("/api/verify_token", json={"token": app_token})
    assert resp.status_code == 400
    resp = client.post(
        "/api/reset_password", json={"token": app_token, "newPassword": "NewPass123!"}
    )
    assert resp.status_code == 400


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
    resp = client.get("/api/user")
    # 422 = flask-jwt-extended's "wrong audience" rejection; 401 = no/invalid
    # token. Either way: not authenticated.
    assert resp.status_code in (401, 422)


# --- profile update input validation -----------------------------------------


def _setup_profile_user(client, db_session):
    from database.models import organization

    _register(client)
    s = db_session
    u = _user(s)
    org = organization(name="SecOrg", provider_id=330054, brand_name="SecBrand")
    s.add(org)
    s.commit()
    u.organization_id = org.id
    u.verified = True
    s.commit()
    return u, org


def test_update_profile_empty_body_changes_nothing(client, db_session):
    """A missing field must never coerce to the literal string 'None'."""
    u, org = _setup_profile_user(client, db_session)
    resp = client.post("/api/update_profile", json={})
    assert resp.status_code == 200, resp.get_json()
    db_session.expire_all()
    assert u.email == "sec@example.com"
    assert u.verified is True
    assert org.brand_name == "SecBrand"
    assert org.name == "SecOrg"


def test_update_profile_rejects_invalid_email(client, db_session):
    u, _ = _setup_profile_user(client, db_session)
    resp = client.post("/api/update_profile", json={"email": "not-an-email"})
    assert resp.status_code == 400
    db_session.expire_all()
    assert u.email == "sec@example.com"


def test_update_profile_rejects_taken_email(client, db_session):
    u, _ = _setup_profile_user(client, db_session)
    from controllers.database_controller import user_ops

    user_ops.create_user_in_db("other@example.com", "Password123!", db_session)
    db_session.commit()
    resp = client.post("/api/update_profile", json={"email": "other@example.com"})
    assert resp.status_code == 400
    db_session.expire_all()
    assert u.email == "sec@example.com"


def test_update_profile_valid_changes_apply(client, db_session):
    u, org = _setup_profile_user(client, db_session)
    resp = client.post(
        "/api/update_profile",
        json={"email": "new@example.com", "brandName": "NewBrand", "organizationName": "NewOrg"},
    )
    assert resp.status_code == 200, resp.get_json()
    db_session.expire_all()
    assert u.email == "new@example.com"
    assert u.verified is False  # changed email needs re-verification
    assert org.brand_name == "NewBrand"
    assert org.name == "NewOrg"


# --- registration input validation --------------------------------------------


def test_register_rejects_invalid_email(client):
    resp = client.post("/api/register", json={"email": "nope", "password": "Password123!"})
    assert resp.status_code == 400


def test_register_rejects_empty_password(client):
    resp = client.post("/api/register", json={"email": "ok@example.com", "password": ""})
    assert resp.status_code == 400


# --- cookie flags ---------------------------------------------------------------


def test_login_cookie_is_httponly_even_in_dev(client, db_session):
    _register(client)
    resp = client.post("/api/login", json={"email": "sec@example.com", "password": "Password123!"})
    cookie_headers = [h for h in resp.headers.getlist("Set-Cookie") if h.startswith("token=")]
    assert cookie_headers, "login should set the token cookie"
    assert "HttpOnly" in cookie_headers[0]


# --- disabled users lose access immediately -------------------------------------


def test_disabled_user_token_rejected_immediately(client, db_session):
    _register(client)
    resp = client.get("/api/user")
    assert resp.status_code == 200  # the registration cookie works

    u = _user(db_session)
    u.disabled = True
    db_session.commit()

    resp = client.get("/api/user")
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
