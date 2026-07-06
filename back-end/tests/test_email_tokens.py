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


def _user_id(email):
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        return s.query(user).filter(user.email == email).one().id
    finally:
        s.close()


def test_reset_token_is_single_use(client):
    from routes._email import create_email_token

    _register(client, "once@example.com")
    uid = _user_id("once@example.com")
    token = create_email_token(userid=uid, email="once@example.com", operation="reset_password")

    first = client.post("/api/reset_password", json={"token": token, "newPassword": "FirstNew1!"})
    assert first.status_code == 200

    replay = client.post(
        "/api/reset_password", json={"token": token, "newPassword": "AttackerPick1!"}
    )
    assert replay.status_code == 400

    # The replay changed nothing: the first new password still logs in.
    login = client.post("/api/login", json={"email": "once@example.com", "password": "FirstNew1!"})
    assert login.get_json()["status"] == "success"


def test_verify_token_is_single_use(client):
    from routes._email import create_email_token

    _register(client, "onceverify@example.com")
    uid = _user_id("onceverify@example.com")
    token = create_email_token(
        userid=uid, email="onceverify@example.com", operation="email_address_verification"
    )

    assert client.post("/api/verify_token", json={"token": token}).status_code == 200
    assert client.post("/api/verify_token", json={"token": token}).status_code == 400


def test_reset_page_token_is_single_use(client):
    from routes._email import create_email_token

    _register(client, "oncepage@example.com")
    uid = _user_id("oncepage@example.com")
    token = create_email_token(userid=uid, email="oncepage@example.com", operation="reset_password")

    first = client.post(f"/auth/reset/{token}", data={"password": "FirstNew1!"})
    assert first.status_code == 302  # success redirects to the login page

    replay = client.post(f"/auth/reset/{token}", data={"password": "AttackerPick1!"})
    assert replay.status_code == 200
    assert "already been used" in replay.get_data(as_text=True)

    login = client.post(
        "/api/login", json={"email": "oncepage@example.com", "password": "FirstNew1!"}
    )
    assert login.get_json()["status"] == "success"


def test_verify_link_replay_reads_as_verified(client):
    """Mail scanners prefetch GET links and users re-click them; once the
    account is verified, a replayed verify link should read as success, not
    as a scary invalid-link page."""
    from routes._email import create_email_token

    _register(client, "reclick@example.com")
    uid = _user_id("reclick@example.com")
    token = create_email_token(
        userid=uid, email="reclick@example.com", operation="email_address_verification"
    )

    for _ in range(2):
        html = client.get(f"/auth/verify/{token}").get_data(as_text=True)
        assert "not valid" not in html


def test_token_without_jti_rejected(client):
    """Tokens minted before one-time-use stamping carry no jti; they can't be
    tracked, so they are refused rather than replayable forever."""
    from datetime import UTC, datetime, timedelta

    import jwt as pyjwt

    from routes._email import EMAIL_TOKEN_AUDIENCE
    from utils.flask_app import app

    _register(client, "nojti@example.com")
    uid = _user_id("nojti@example.com")
    token = pyjwt.encode(
        {
            "sub": {
                "id": uid,
                "email": "nojti@example.com",
                "operation": "reset_password",
                "org_id": -1,
            },
            "exp": datetime.now(UTC) + timedelta(minutes=60),
            "aud": EMAIL_TOKEN_AUDIENCE,
        },
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    resp = client.post("/api/reset_password", json={"token": token, "newPassword": "Sneaky1!"})
    assert resp.status_code == 400
