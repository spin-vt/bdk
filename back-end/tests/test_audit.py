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


# ------------------------------------------------------------------- uploads


@pytest.fixture()
def no_tiles(monkeypatch):
    from controllers.celery_controller import celery_tasks as ct

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")


POLYGON_GEOJSON = b"""{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},
"geometry":{"type":"Polygon","coordinates":[[[-80.01,37.27],[-79.90,37.27],[-79.90,37.31],
[-80.01,37.31],[-80.01,37.27]]]}}]}"""

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
    (1002, "2 ELM AVE", "TRUE", 37.50, -79.95, "51161", "VA"),
]


def _login_with_filing(client, db_session, email):
    from datetime import date

    _register(client, email)
    uid = _verify(email)
    org = H.make_org(db_session, name=f"audit-org-{email}")
    from database.models import user

    u = db_session.query(user).filter(user.id == uid).one()
    u.organization_id = org.id
    db_session.commit()
    folder = H.make_folder(db_session, org.id, deadline=date(2025, 9, 1))
    return org, folder


def test_coverage_upload_audited(client, db_session, no_tiles):
    """Every ingest of provider data must land in the audit trail — this is
    an FCC-filing system. Regression: the server-rendered upload paths
    originally wrote no audit rows at all."""
    import io

    from tests.conftest_helpers import make_active_fabric_csv

    org, folder = _login_with_filing(client, db_session, "covaudit@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))

    resp = client.post(
        "/files/coverage/upload",
        data={"network_files": [(io.BytesIO(POLYGON_GEOJSON), "sector.geojson")]},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    rows = _rows("upload")
    assert len(rows) == 1
    assert rows[0].resource_type == "folder"
    assert rows[0].resource_id == folder.id
    assert rows[0].details.get("kind") == "coverage"
    assert rows[0].details.get("files") == ["sector.geojson"]
    assert rows[0].details.get("task_id")


def test_fabric_upload_audited(client, db_session, no_tiles):
    import io

    from tests.conftest_helpers import make_active_fabric_csv

    org, folder = _login_with_filing(client, db_session, "fabaudit@example.com")
    csv_bytes = make_active_fabric_csv(FABRIC_ROWS)

    resp = client.post(
        "/files/fabric/upload",
        data={"fabric_file": (io.BytesIO(csv_bytes), "FCC_Active_BSL_06302025_ver7.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    rows = _rows("upload")
    assert len(rows) == 1
    assert rows[0].resource_type == "folder"
    assert rows[0].resource_id == folder.id
    assert rows[0].details.get("kind") == "fabric"
    assert rows[0].details.get("files") == ["FCC_Active_BSL_06302025_ver7.csv"]
    assert rows[0].details.get("task_id")
