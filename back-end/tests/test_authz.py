"""Authorization enforcement on existing app routes.

Two concrete gaps closed:
  * a `disabled` user must not be able to log in;
  * `delete_organization` must require an org admin (today any *member* of an
    org can delete the whole org — it only checks the org name matches).

Org-scoped read/write routes (filings/files/edit/export) are intentionally left
open to any org member — that's the current product behavior and gating them
would break non-admin members.
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
    return client.post("/api/register", json={"email": email, "password": password})


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


# --- disabled blocks login --------------------------------------------------


def test_disabled_user_cannot_login(client):
    _register(client, "disabled@example.com")
    _set_flags("disabled@example.com", disabled=True)
    resp = client.post(
        "/api/login", json={"email": "disabled@example.com", "password": "Password123!"}
    )
    body = resp.get_json()
    assert body["status"] == "error"
    # Correct password but disabled -> not authenticated, no fresh token issued.
    assert (
        "token=" not in resp.headers.get("Set-Cookie", "") or "disabled" in body["message"].lower()
    )


def test_enabled_user_can_still_login(client):
    _register(client, "enabled@example.com")
    resp = client.post(
        "/api/login", json={"email": "enabled@example.com", "password": "Password123!"}
    )
    assert resp.get_json()["status"] == "success"


# --- delete_organization requires org admin ---------------------------------


def test_non_admin_member_cannot_delete_org(client):
    # Admin creates the org.
    _register(client, "owner@example.com")
    _set_flags("owner@example.com", verified=True)
    assert client.post("/api/create_organization", json={"orgName": "Acme ISP"}).status_code == 200

    # A second user is a *member* of the same org but not an admin.
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        org_id = s.query(user).filter(user.email == "owner@example.com").one().organization_id
    finally:
        s.close()

    from utils.flask_app import app

    with H.CsrfFlaskClient(app) as member:
        member.post(
            "/api/register", json={"email": "member@example.com", "password": "Password123!"}
        )
        _set_flags("member@example.com", verified=True, organization_id=org_id, is_admin=False)
        resp = member.delete("/api/delete_organization", json={"organizationName": "Acme ISP"})
        assert resp.status_code == 403, resp.get_json()
        assert resp.get_json()["status"] == "error"


def test_org_admin_can_delete_own_org(client):
    _register(client, "boss@example.com")
    _set_flags("boss@example.com", verified=True)
    assert client.post("/api/create_organization", json={"orgName": "Boss ISP"}).status_code == 200
    # The creator is an org admin -> passes the guard (async delete runs eagerly).
    resp = client.delete("/api/delete_organization", json={"organizationName": "Boss ISP"})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "success"
