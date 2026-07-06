"""Regression: email/reset tokens use a dict `sub`, which PyJWT >= 2.10 rejects
by default ("sub must be a string"). The reset_password / verify_token routes
must decode with verify_sub=False, otherwise every password reset and email
verification silently fails with "Invalid token".
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
    with app.test_client() as c:
        yield c


def _register(client, email, password="Password123!"):
    return client.post("/api/register", json={"email": email, "password": password})


def test_reset_password_round_trip(client):
    _register(client, "reset@example.com")
    from database.models import user
    from database.sessions import Session
    from routes._email import create_email_token

    s = Session()
    try:
        uid = s.query(user).filter(user.email == "reset@example.com").one().id
    finally:
        s.close()

    token = create_email_token(userid=uid, email="reset@example.com", operation="reset_password")
    resp = client.post(
        "/api/reset_password", json={"token": token, "newPassword": "BrandNewPass1!"}
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "success"

    # The new password actually works.
    login = client.post(
        "/api/login", json={"email": "reset@example.com", "password": "BrandNewPass1!"}
    )
    assert login.get_json()["status"] == "success"


def test_verify_email_token(client):
    _register(client, "verifyme@example.com")
    from database.models import user
    from database.sessions import Session
    from routes._email import create_email_token

    s = Session()
    try:
        uid = s.query(user).filter(user.email == "verifyme@example.com").one().id
    finally:
        s.close()

    token = create_email_token(
        userid=uid, email="verifyme@example.com", operation="email_address_verification"
    )
    resp = client.post("/api/verify_token", json={"token": token})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "success"

    s = Session()
    try:
        assert s.query(user).filter(user.email == "verifyme@example.com").one().verified is True
    finally:
        s.close()


def test_email_token_lifetime_is_an_hour(client):
    """Users often come back to a verify/reset email well after it arrives;
    15 minutes read as "broken link". Pin the intended 60-minute lifetime."""
    import time

    import jwt as pyjwt

    from routes._email import EMAIL_TOKEN_AUDIENCE, create_email_token
    from utils.flask_app import app

    token = create_email_token(userid=1, email="ttl@example.com", operation="reset_password")
    decoded = pyjwt.decode(
        token,
        app.config["JWT_SECRET_KEY"],
        algorithms=["HS256"],
        audience=EMAIL_TOKEN_AUDIENCE,
        options={"verify_sub": False},
    )
    lifetime = decoded["exp"] - time.time()
    assert 59 * 60 < lifetime <= 60 * 60
