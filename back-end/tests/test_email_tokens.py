"""Email token behavior through the server-rendered auth flows.

Regression: email/reset tokens use a dict `sub`, which PyJWT >= 2.10 rejects
by default ("sub must be a string") — the consuming routes must decode with
verify_sub=False or every password reset and email verification silently
fails. Also pins the 60-minute token lifetime and one-time use (a consumed
or pre-jti token can never reset a password again).
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
    resp = client.post("/auth/register", data={"email": email, "password": password})
    assert resp.status_code == 302, resp.get_data(as_text=True)
    return resp


def _user_id(email):
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        return s.query(user).filter(user.email == email).one().id
    finally:
        s.close()


def _login_status(client, email, password):
    """302 = credentials accepted; 200 = the login page re-rendered an error."""
    return client.post("/auth/login", data={"email": email, "password": password}).status_code


def test_reset_password_round_trip(client):
    from routes._email import create_email_token

    _register(client, "reset@example.com")
    uid = _user_id("reset@example.com")

    token = create_email_token(userid=uid, email="reset@example.com", operation="reset_password")
    resp = client.post(f"/auth/reset/{token}", data={"password": "BrandNewPass1!"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/auth/login"

    # The new password actually works.
    assert _login_status(client, "reset@example.com", "BrandNewPass1!") == 302


def test_verify_email_token(client):
    from database.models import user
    from database.sessions import Session
    from routes._email import create_email_token

    _register(client, "verifyme@example.com")
    uid = _user_id("verifyme@example.com")

    token = create_email_token(
        userid=uid, email="verifyme@example.com", operation="email_address_verification"
    )
    html = client.get(f"/auth/verify/{token}").get_data(as_text=True)
    assert "not valid" not in html

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

    # The replay changed nothing: the first new password still logs in.
    assert _login_status(client, "oncepage@example.com", "FirstNew1!") == 302
    assert _login_status(client, "oncepage@example.com", "AttackerPick1!") == 200


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
    tracked, so the reset form refuses them rather than allow forever-replay."""
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
    resp = client.post(f"/auth/reset/{token}", data={"password": "Sneaky1!"})
    assert resp.status_code == 200  # the error page, not the login redirect
    assert _login_status(client, "nojti@example.com", "Sneaky1!") == 200  # unchanged
