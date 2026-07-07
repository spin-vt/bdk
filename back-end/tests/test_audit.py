"""Audit logging tests.

Unit-tests log_action (writes a row in its own session; never raises) and
checks that the key lifecycle actions append the right audit rows through the
real routes: login (success/failed), logout, org create. Admin-side actions
(impersonation, password resets, role changes, org delete) are exercised with
the admin API tests.
"""

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


def _rows(action=None):
    from database.models import audit_log
    from database.sessions import Session

    s = Session()
    try:
        q = s.query(audit_log)
        if action is not None:
            q = q.filter(audit_log.action == action)
        return q.all()
    finally:
        s.close()


# --- unit -------------------------------------------------------------------


def test_log_action_writes_row(db_session):
    from services.audit import log_action

    log_action(
        "unit_test_action",
        user_id=7,
        resource_type="user",
        resource_id=7,
        details={"k": "v"},
    )
    rows = _rows("unit_test_action")
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == 7
    assert row.resource_type == "user"
    assert row.resource_id == 7
    assert row.details == {"k": "v"}
    assert row.ts is not None


def test_log_action_never_raises(db_session, monkeypatch):
    # Even if the write blows up, the audited action must not be affected.
    import services.audit as audit

    class _BoomSession:
        def add(self, *a, **k):
            raise RuntimeError("db down")

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(audit, "Session", lambda: _BoomSession())
    # Should swallow the error, not propagate.
    audit.log_action("will_fail")


# --- integration through the routes -----------------------------------------


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


def _register(client, email, password="Password123!"):
    resp = client.post("/auth/register", data={"email": email, "password": password})
    assert resp.status_code == 302, resp.get_data(as_text=True)
    return resp


def _verify(email):
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        u = s.query(user).filter(user.email == email).one()
        u.verified = True
        s.commit()
        return u.id
    finally:
        s.close()


def test_login_logout_audited(client):
    _register(client, "log@example.com")
    client.post("/auth/login", data={"email": "log@example.com", "password": "Password123!"})
    client.post("/auth/login", data={"email": "log@example.com", "password": "WRONG"})
    client.post("/auth/logout")

    assert len(_rows("login")) == 1
    assert len(_rows("login_failed")) == 1
    assert len(_rows("logout")) == 1
    # The failed login records the attempted email but no user_id leak guarantee.
    assert _rows("login_failed")[0].details.get("email") == "log@example.com"


def test_org_create_audited(client):
    _register(client, "orgadmin@example.com")
    _verify("orgadmin@example.com")
    client.post("/org/create", data={"name": "Audit ISP"})
    assert len(_rows("org_create")) == 1
    assert _rows("org_create")[0].details.get("name") == "Audit ISP"
