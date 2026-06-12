"""Contract tests for routes/files.py — the files & plans page's backend.

The whole blueprint previously had zero tests. These pin, before the page is
built on top of them:
  - GET /api/files & /api/editfiles (listing, non-int 400, org-ownership 400);
  - GET /api/networkfiles/<folder_id> (the coverage-tab table shape:
    extension-stripped name + the per-file speed/tech/latency/category);
  - POST /api/updateNetworkFile/<file_id> (validation, attribute-only changes
    update file+kml_data without a recompute, name/type changes dispatch the
    op-4 recompute and record an Update task-info row);
  - DELETE /api/delfiles (verified/org gates, per-id ownership, the
    delete→recompute chain + Delete task-info row);
  - GET /api/download-kmlfile/<name> (byte round-trip, 404).

The tippecanoe tile rebuild is stubbed (no_tiles); eager celery runs the real
delete/recompute chains inline against seeded fabric + coverage.
"""

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session, make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

COVERAGE_POLYGON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-80.01, 37.27],
                        [-79.90, 37.27],
                        [-79.90, 37.31],
                        [-80.01, 37.31],
                        [-80.01, 37.27],
                    ]
                ],
            },
        }
    ],
}

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),  # inside coverage
    (1002, "2 ELM AVE", "TRUE", 37.50, -79.95, "51161", "VA"),  # outside coverage
]


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


@pytest.fixture()
def no_tiles(monkeypatch):
    """Keep tippecanoe out: the recompute chains run, the retile is stubbed."""
    from controllers.celery_controller import celery_tasks as ct

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")


def _get_user(session, email):
    from database.models import user as user_model

    return session.query(user_model).filter(user_model.email == email).one()


def _login(client, db_session, email, org_name="FilesOrg"):
    login_page_session(client, email=email)
    org = H.make_org(db_session, name=org_name)
    u = _get_user(db_session, email)
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    return org


def _seed_filing(db_session, org, geojson=COVERAGE_POLYGON, filetype="wireless", tech=70):
    """An upload filing with seeded fabric + one computed coverage file."""
    import json

    folder = H.make_folder(db_session, org.id, name="F1")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    cov = H.seed_coverage(
        db_session,
        folder.id,
        json.dumps(geojson).encode(),
        filename="coverage.geojson",
        filetype=filetype,
        techType=tech,
    )
    H.compute_coverage(db_session, folder.id, cov)
    return folder, cov


def _other_orgs_folder_and_file(db_session):
    import json

    other = H.make_org(db_session, name="NotMyOrg")
    folder = H.make_folder(db_session, other.id, name="theirs")
    cov = H.seed_coverage(
        db_session,
        folder.id,
        json.dumps(COVERAGE_POLYGON).encode(),
        filename="their_coverage.geojson",
        filetype="wireless",
        techType=70,
    )
    return folder, cov


# ------------------------------------------------------------ list endpoints


def test_files_requires_auth(client):
    assert client.get("/api/files?folder_ID=1").status_code == 401


def test_files_non_int_folder_400(client, db_session):
    _login(client, db_session, "files1@example.com")
    resp = client.get("/api/files?folder_ID=abc")
    assert resp.status_code == 400
    assert "integer" in resp.get_json()["message"]


def test_files_other_org_400(client, db_session):
    _login(client, db_session, "files2@example.com")
    folder, _ = _other_orgs_folder_and_file(db_session)
    resp = client.get(f"/api/files?folder_ID={folder.id}")
    assert resp.status_code == 400


def test_files_lists_folder_files(client, db_session):
    org = _login(client, db_session, "files3@example.com")
    folder, cov = _seed_filing(db_session, org)
    resp = client.get(f"/api/files?folder_ID={folder.id}")
    assert resp.status_code == 200
    names = {f["name"] for f in resp.get_json()}
    assert "coverage.geojson" in names and "test_fabric.csv" in names


def test_editfiles_non_int_folder_400(client, db_session):
    _login(client, db_session, "edits1@example.com")
    resp = client.get("/api/editfiles?folder_ID=abc")
    assert resp.status_code == 400


def test_editfiles_other_org_400_and_own_empty(client, db_session):
    org = _login(client, db_session, "edits2@example.com")
    their_folder, _ = _other_orgs_folder_and_file(db_session)
    assert client.get(f"/api/editfiles?folder_ID={their_folder.id}").status_code == 400

    mine = H.make_folder(db_session, org.id, name="mine")
    resp = client.get(f"/api/editfiles?folder_ID={mine.id}")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_networkfiles_other_org_400(client, db_session):
    _login(client, db_session, "net1@example.com")
    folder, _ = _other_orgs_folder_and_file(db_session)
    assert client.get(f"/api/networkfiles/{folder.id}").status_code == 400


def test_networkfiles_table_shape(client, db_session):
    org = _login(client, db_session, "net2@example.com")
    folder, cov = _seed_filing(db_session, org)
    resp = client.get(f"/api/networkfiles/{folder.id}")
    assert resp.status_code == 200
    rows = resp.get_json()["files_data"]
    row = next(r for r in rows if r["id"] == cov.id)
    assert row["name"] == "coverage"  # extension stripped
    assert row["type"] == "wireless"
    assert row["techType"] == 70
    assert row["maxDownloadSpeed"] == 100
    assert {"maxUploadSpeed", "latency", "category"} <= set(row)


# ------------------------------------------------------ updateNetworkFile


def _update_payload(name="coverage", ftype="wireless", **over):
    payload = {
        "name": name,
        "type": ftype,
        "maxDownloadSpeed": 200,
        "maxUploadSpeed": 50,
        "techType": 70,
        "latency": 1,
        "category": "R",
    }
    payload.update(over)
    return payload


def test_update_network_file_other_org_400(client, db_session):
    _login(client, db_session, "upd1@example.com")
    _, their_cov = _other_orgs_folder_and_file(db_session)
    resp = client.post(f"/api/updateNetworkFile/{their_cov.id}", json=_update_payload())
    assert resp.status_code == 400


def test_update_network_file_invalid_type_400(client, db_session):
    org = _login(client, db_session, "upd2@example.com")
    _, cov = _seed_filing(db_session, org)
    resp = client.post(f"/api/updateNetworkFile/{cov.id}", json=_update_payload(ftype="satellite"))
    assert resp.status_code == 400
    assert "valid type" in resp.get_json()["message"].lower()


def test_update_network_file_non_int_speed_400(client, db_session):
    org = _login(client, db_session, "upd3@example.com")
    _, cov = _seed_filing(db_session, org)
    resp = client.post(
        f"/api/updateNetworkFile/{cov.id}", json=_update_payload(maxDownloadSpeed="fast")
    )
    assert resp.status_code == 400


def test_update_attributes_only_writes_through_without_recompute(client, db_session):
    """Speed/latency/category edits stamp the file AND its kml_data rows but
    must not dispatch a recompute (no new task-info row)."""
    from database.models import celerytaskinfo, kml_data

    org = _login(client, db_session, "upd4@example.com")
    folder, cov = _seed_filing(db_session, org)
    before = db_session.query(celerytaskinfo).count()

    resp = client.post(f"/api/updateNetworkFile/{cov.id}", json=_update_payload())
    assert resp.status_code == 200, resp.get_json()

    db_session.expire_all()
    assert cov.maxDownloadSpeed == 200
    kml_rows = db_session.query(kml_data).filter(kml_data.file_id == cov.id).all()
    assert kml_rows and all(r.maxDownloadSpeed == 200 for r in kml_rows)
    assert db_session.query(celerytaskinfo).count() == before


def test_update_rename_dispatches_recompute(client, db_session, no_tiles):
    """A name (or type) change reruns the op-4 recompute and records an
    Update task-info row; the kml data survives the round-trip."""
    from database.models import celerytaskinfo, kml_data

    org = _login(client, db_session, "upd5@example.com")
    folder, cov = _seed_filing(db_session, org)

    resp = client.post(f"/api/updateNetworkFile/{cov.id}", json=_update_payload(name="renamed"))
    assert resp.status_code == 200, resp.get_json()

    db_session.expire_all()
    assert cov.name == "renamed.geojson"  # original extension kept
    info = db_session.query(celerytaskinfo).filter(celerytaskinfo.operation_type == "Update").one()
    assert info.organization_id == org.id
    # Eager celery already ran the recompute: served rows exist for the file.
    assert db_session.query(kml_data).filter(kml_data.file_id == cov.id).count() > 0


# ------------------------------------------------------------- delfiles


def test_delfiles_empty_selection_400(client, db_session):
    _login(client, db_session, "del1@example.com")
    resp = client.delete("/api/delfiles", json={"file_ids": [], "editfile_ids": []})
    assert resp.status_code == 400


def test_delfiles_requires_verified_email(client, db_session):
    _login(client, db_session, "del2@example.com")
    u = _get_user(db_session, "del2@example.com")
    u.verified = False
    db_session.commit()
    resp = client.delete("/api/delfiles", json={"file_ids": [1], "editfile_ids": []})
    assert resp.status_code == 400
    assert "verify" in resp.get_json()["message"].lower()


def test_delfiles_requires_an_organization(client, db_session):
    login_page_session(client, email="del3@example.com")
    u = _get_user(db_session, "del3@example.com")
    u.verified = True
    db_session.commit()
    resp = client.delete("/api/delfiles", json={"file_ids": [1], "editfile_ids": []})
    assert resp.status_code == 400
    assert "organization" in resp.get_json()["message"].lower()


def test_delfiles_other_org_file_400(client, db_session):
    _login(client, db_session, "del4@example.com")
    _, their_cov = _other_orgs_folder_and_file(db_session)
    resp = client.delete("/api/delfiles", json={"file_ids": [their_cov.id], "editfile_ids": []})
    assert resp.status_code == 400


def test_delfiles_deletes_and_recomputes(client, db_session, no_tiles):
    from database.models import celerytaskinfo
    from database.models import file as file_model

    org = _login(client, db_session, "del5@example.com")
    folder, cov = _seed_filing(db_session, org)
    cov_id = cov.id

    resp = client.delete("/api/delfiles", json={"file_ids": [cov_id], "editfile_ids": []})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["task_id"]

    db_session.expire_all()
    assert db_session.query(file_model).filter(file_model.id == cov_id).first() is None
    info = db_session.query(celerytaskinfo).filter(celerytaskinfo.operation_type == "Delete").one()
    assert "coverage.geojson" in info.files_changed


# ------------------------------------------------------- download-kmlfile


def test_download_kmlfile_404_for_unknown_name(client, db_session):
    org = _login(client, db_session, "down1@example.com")
    H.make_folder(db_session, org.id, name="up")  # an upload folder must exist
    resp = client.get("/api/download-kmlfile/nope.kml")
    assert resp.status_code == 404


def test_download_kmlfile_roundtrips_bytes(client, db_session):
    import json

    org = _login(client, db_session, "down2@example.com")
    folder, cov = _seed_filing(db_session, org)
    resp = client.get(f"/api/download-kmlfile/{cov.name}")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    assert json.loads(resp.data) == COVERAGE_POLYGON
