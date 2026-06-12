"""Contract tests for the export routes the submissions page builds on.

The export_service is well covered, but the routes were not —
the CSV response itself, the snapshot list, the snapshot download (which must
be byte-stable: it serves stored bytes, never a rebuild), and snapshot delete.
"""

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session, make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
    (1002, "2 ELM AVE", "TRUE", 37.50, -79.95, "51161", "VA"),
]

POLYGON_GEOJSON = b"""{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},
"geometry":{"type":"Polygon","coordinates":[[[-80.01,37.27],[-79.90,37.27],[-79.90,37.31],
[-80.01,37.31],[-80.01,37.27]]]}}]}"""


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


def _get_user(session, email):
    from database.models import user as user_model

    return session.query(user_model).filter(user_model.email == email).one()


def _login_with_computed_filing(client, db_session, email):
    login_page_session(client, email=email)
    org = H.make_org(db_session, name=f"org-{email}")
    u = _get_user(db_session, email)
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    folder = H.make_folder(db_session, org.id)
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    cov = H.seed_coverage(
        db_session,
        folder.id,
        POLYGON_GEOJSON,
        filename="sector.geojson",
        filetype="wireless",
        techType=70,
    )
    H.compute_coverage(db_session, folder.id, cov)
    return org, folder


def test_export_filing_returns_attached_csv(client, db_session):
    org, folder = _login_with_computed_filing(client, db_session, "exp1@example.com")
    resp = client.get(f"/api/exportFiling/{folder.id}")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    body = resp.get_data(as_text=True)
    assert "location_id" in body and "1001" in body


def test_export_filing_requires_provider_and_brand(client, db_session):
    org, folder = _login_with_computed_filing(client, db_session, "exp2@example.com")
    org.provider_id = None
    db_session.commit()
    resp = client.get(f"/api/exportFiling/{folder.id}")
    assert resp.status_code == 400
    assert "provider" in resp.get_json()["message"].lower()


def test_export_list_is_org_scoped(client, db_session):
    org, folder = _login_with_computed_filing(client, db_session, "exp3@example.com")
    client.get(f"/api/exportFiling/{folder.id}")  # creates a snapshot (eager)

    rows = client.get("/api/export").get_json()
    assert len(rows) == 1
    assert rows[0]["type"] == "export"

    # A second user in another org sees none of it.
    import routes  # noqa: F401
    from utils.flask_app import app

    with H.CsrfFlaskClient(app) as other:
        login_page_session(other, email="exp3-other@example.com")
        other_org = H.make_org(db_session, name="exp3-other-org")
        u = _get_user(db_session, "exp3-other@example.com")
        u.organization_id = other_org.id
        db_session.commit()
        assert other.get("/api/export").get_json() == []


def test_download_export_is_byte_stable(client, db_session):
    org, folder = _login_with_computed_filing(client, db_session, "exp4@example.com")
    csv_now = client.get(f"/api/exportFiling/{folder.id}").data
    rows = client.get("/api/export").get_json()
    fid = rows[0]["id"]

    first = client.get(f"/api/downloadexport/{fid}")
    assert first.status_code == 200
    assert first.data == csv_now
    assert client.get(f"/api/downloadexport/{fid}").data == first.data


def test_download_export_ownership_and_404(client, db_session):
    org, folder = _login_with_computed_filing(client, db_session, "exp5@example.com")
    client.get(f"/api/exportFiling/{folder.id}")
    fid = client.get("/api/export").get_json()[0]["id"]

    import routes  # noqa: F401
    from utils.flask_app import app

    with H.CsrfFlaskClient(app) as other:
        login_page_session(other, email="exp5-other@example.com")
        other_org = H.make_org(db_session, name="exp5-other-org")
        u = _get_user(db_session, "exp5-other@example.com")
        u.organization_id = other_org.id
        db_session.commit()
        assert other.get(f"/api/downloadexport/{fid}").status_code == 400


def test_delete_export_removes_the_snapshot(client, db_session):
    from database.models import folder as folder_model

    org, folder = _login_with_computed_filing(client, db_session, "exp6@example.com")
    client.get(f"/api/exportFiling/{folder.id}")
    row = client.get("/api/export").get_json()[0]

    resp = client.delete(f"/api/delexport/{row['id']}")
    assert resp.status_code == 200
    db_session.expire_all()
    assert (
        db_session.query(folder_model).filter(folder_model.id == row["folder_id"]).first() is None
    )
    assert client.get("/api/export").get_json() == []
