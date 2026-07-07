"""Authorization enforcement on the auth routes.

A `disabled` user must not be able to log in — even with the correct
password, no fresh session is issued. (Org deletion is admin-panel-only now;
its guard is exercised by the admin API tests.)
"""

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401  (registers endpoints on utils.flask_app.app)
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


def _register(client, email, password="Password123!"):
    resp = client.post("/auth/register", data={"email": email, "password": password})
    assert resp.status_code == 302, resp.get_data(as_text=True)
    return resp


def _set_flags(email, **flags):
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        u = s.query(user).filter(user.email == email).one()
        for k, v in flags.items():
            setattr(u, k, v)
        s.commit()
        return u.id
    finally:
        s.close()


def test_disabled_user_cannot_login(client):
    _register(client, "disabled@example.com")
    _set_flags("disabled@example.com", disabled=True)
    client.post("/auth/logout")
    resp = client.post(
        "/auth/login", data={"email": "disabled@example.com", "password": "Password123!"}
    )
    # Correct password but disabled -> the page re-renders, no fresh token.
    assert resp.status_code == 200
    assert "disabled" in resp.get_data(as_text=True).lower()
    assert not any(
        c.startswith("token=") and "token=;" not in c for c in resp.headers.getlist("Set-Cookie")
    )


def test_enabled_user_can_still_login(client):
    _register(client, "enabled@example.com")
    client.post("/auth/logout")
    resp = client.post(
        "/auth/login", data={"email": "enabled@example.com", "password": "Password123!"}
    )
    assert resp.status_code == 302
    assert any(c.startswith("token=") for c in resp.headers.getlist("Set-Cookie"))
