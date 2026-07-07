"""Contract tests for routes/files.py — DELETE /api/delfiles, the one
files endpoint the server-rendered app still uses (the map page's delete
flow): verified/org gates, per-id ownership, and the delete-then-recompute
chain with its Delete task-info row. The tippecanoe tile rebuild is stubbed
(no_tiles); eager celery runs the real delete/recompute chains inline against
seeded fabric + coverage.
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
