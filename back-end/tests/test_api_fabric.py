"""Contract tests for the fabric v2 endpoints (routes/fabric.py).

POST /api/fabric/<folderid>        — upload a CostQuest delivery (zip or CSV)
GET  /api/fabric/<folderid>        — the fabric card: files + vintage + stats
GET  /api/address-search/<folderid> — fabric-powered autocomplete

Response shapes follow the app convention: {"status": "error", "message": ...}
on expected failures, with the vintage hard-warning as a 409 the client can
override (form field override=true).
"""

import io
import zipfile
from datetime import date

import pytest

from tests import conftest_helpers as H
from tests.conftest_helpers import make_active_fabric_csv, make_supplemental_csv

ACTIVE_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
    (1002, "2 ELM AVE", "TRUE", 37.50, -79.95, "51161", "VA"),
]
SUPP_ROWS = [(1001, "S", "ONE MAIN STREET REAR UNIT")]


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401  (decorators attach routes to utils.flask_app.app)
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


@pytest.fixture()
def filing(client, db_session, monkeypatch):
    """A registered+verified user in an org with an open December-2025 filing
    (expects fabric v8), logged in on the client. Tile rebuilds stubbed."""
    from controllers.celery_controller import celery_tasks as ct
    from database.models import user as user_model

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")

    s = db_session
    resp = client.post(
        "/api/register", json={"email": "fab@example.com", "password": "Password123!"}
    )
    assert resp.status_code == 200
    org = H.make_org(s)
    u = s.query(user_model).filter_by(email="fab@example.com").one()
    u.verified = True
    u.organization_id = org.id
    folder = H.make_folder(s, org.id, deadline=date(2026, 3, 2))
    s.commit()
    return folder


def _zip_v8():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("FCC_Active_BSL_12312025_rel_8.csv", make_active_fabric_csv(ACTIVE_ROWS))
        zf.writestr("FCC_Supplemental_12312025_rel_8.csv", make_supplemental_csv(SUPP_ROWS))
    return buf.getvalue()


def test_fabric_endpoints_require_auth(client, db_session):
    assert client.get("/api/fabric/1").status_code == 401
    assert client.post("/api/fabric/1").status_code == 401
    assert client.get("/api/address-search/1?query=main").status_code == 401


def test_intake_then_status_and_search(client, filing):
    resp = client.post(
        f"/api/fabric/{filing.id}",
        data={"file": (io.BytesIO(_zip_v8()), "H5PKFG71-OPAQUE.zip")},
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    assert resp.status_code == 200, body
    assert body["status"] == "success"
    assert body["task_id"]
    assert sorted(body["roles"]) == ["active", "supplemental"]
    assert body["vintage"]["matches"] is True

    resp = client.get(f"/api/fabric/{filing.id}")
    body = resp.get_json()
    assert resp.status_code == 200
    assert {f["role"] for f in body["files"]} == {"active", "supplemental"}
    assert body["stats"]["locations"] == 2
    assert body["stats"]["supplemental_addresses"] == 1

    resp = client.get(f"/api/address-search/{filing.id}?query=main")
    body = resp.get_json()
    assert resp.status_code == 200
    addresses = {r["address"] for r in body["results"]}
    assert "1 MAIN ST" in addresses
    assert all("served" in r and "bsl" in r for r in body["results"])


def test_intake_vintage_mismatch_409_then_override(client, filing):
    v6 = make_active_fabric_csv(ACTIVE_ROWS)
    resp = client.post(
        f"/api/fabric/{filing.id}",
        data={"file": (io.BytesIO(v6), "FCC_Active_BSL_12312024_rel_6.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 409
    assert "version 8" in resp.get_json()["message"]

    resp = client.post(
        f"/api/fabric/{filing.id}",
        data={"file": (io.BytesIO(v6), "FCC_Active_BSL_12312024_rel_6.csv"), "override": "true"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["vintage"]["matches"] is False


def test_intake_requires_a_file_and_org_membership(client, filing, db_session):
    resp = client.post(f"/api/fabric/{filing.id}", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400

    s = db_session
    other_org = H.make_org(s, name="OtherOrg", provider_id=999)
    other_folder = H.make_folder(s, other_org.id, deadline=date(2026, 3, 2))
    resp = client.post(
        f"/api/fabric/{other_folder.id}",
        data={"file": (io.BytesIO(b"x"), "FCC_Active_BSL_12312025_rel_8.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["status"] == "error"


def test_address_search_empty_without_fabric(client, filing):
    resp = client.get(f"/api/address-search/{filing.id}?query=main")
    assert resp.status_code == 200
    assert resp.get_json()["results"] == []
