"""The setup page (/setup) — the funnel.

Pins: a fresh org's first visit starts its window's filing and shows the two
doors; the network door uploads through the real op-1 chain (eager) and
enables "Let's get started!"; the fabric door runs intake v2 with the
overridable vintage warning; a carried filing missing only its fabric gets
the welcome-back card; a running job shows "Building your map…"; a fully
set-up filing redirects to the map (the returning-filer landing).
"""

import io
import json

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session, make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

LINES_GEOJSON = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-80.00, 37.28], [-79.95, 37.28]],
                },
            }
        ],
    }
).encode()

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
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
    from controllers.celery_controller import celery_tasks as ct

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")


def _get_user(session, email):
    from database.models import user as user_model

    return session.query(user_model).filter(user_model.email == email).one()


def _login_with_org(client, db_session, email):
    login_page_session(client, email=email)
    org = H.make_org(db_session, name=f"org-{email}")
    u = _get_user(db_session, email)
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    return org, u


def test_setup_without_org_points_at_org_page(client, db_session):
    login_page_session(client, email="setup-noorg@example.com")
    html = client.get("/setup").get_data(as_text=True)
    assert "First, your organization" in html


def test_setup_first_visit_starts_filing_and_shows_doors(client, db_session):
    from database.models import folder as folder_model

    org, u = _login_with_org(client, db_session, "setup-fresh@example.com")
    html = client.get("/setup").get_data(as_text=True)
    assert "Let's get your network on the map" in html
    assert "Your network" in html and "The FCC fabric" in html
    assert "CostQuest" in html
    db_session.expire_all()
    # The window's filing now exists (empty, explicit start path).
    assert (
        db_session.query(folder_model).filter_by(organization_id=org.id, type="upload").count() == 1
    )
    # A second visit doesn't start another.
    client.get("/setup")
    db_session.expire_all()
    assert (
        db_session.query(folder_model).filter_by(organization_id=org.id, type="upload").count() == 1
    )


def test_setup_network_door_uploads_and_enables_continue(client, db_session, no_tiles):
    from database.models import file as file_model

    org, u = _login_with_org(client, db_session, "setup-net@example.com")
    client.get("/setup")  # starts the filing
    resp = client.post(
        "/setup/network",
        data={"network_files": [(io.BytesIO(LINES_GEOJSON), "route.geojson")]},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    db_session.expire_all()
    f = db_session.query(file_model).filter_by(type="wired").one()
    assert f.techType == 50  # geometry guess applied
    assert "route.geojson" in html
    assert 'href="/map"' in html  # Let's get started! is live
    assert "No fabric yet" in html  # network-only works, with the caveat


def test_setup_fabric_door_vintage_warning_then_override(client, db_session, no_tiles):
    from database.models import fabric_data

    org, u = _login_with_org(client, db_session, "setup-fab@example.com")
    client.get("/setup")
    csv_bytes = make_active_fabric_csv(FABRIC_ROWS)
    # A vintage that can't match the filing's window: warn, ingest nothing.
    resp = client.post(
        "/setup/fabric",
        data={"fabric_file": (io.BytesIO(csv_bytes), "FCC_Active_BSL_12312023_ver6.csv")},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert "use it anyway" in html
    db_session.expire_all()
    assert db_session.query(fabric_data).count() == 0

    resp = client.post(
        "/setup/fabric",
        data={
            "fabric_file": (io.BytesIO(csv_bytes), "FCC_Active_BSL_12312023_ver6.csv"),
            "override": "1",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.query(fabric_data).count() == 1


def test_setup_carried_filing_welcomes_back(client, db_session):
    org, u = _login_with_org(client, db_session, "setup-carry@example.com")
    prev = H.make_folder(db_session, org.id, name="prev")
    folder = H.make_folder(db_session, org.id, name="next")
    folder.source_folder_id = prev.id
    db_session.commit()
    H.seed_coverage(
        db_session,
        folder.id,
        LINES_GEOJSON,
        filename="route.geojson",
        filetype="wired",
        techType=50,
    )
    client.set_cookie("bdk_filing", str(folder.id))
    html = client.get("/setup").get_data(as_text=True)
    assert "Welcome back — we kept everything" in html
    assert "1 thing needed" in html and "new</b> fabric" in html
    assert "Look around first" in html


def test_setup_building_card_while_job_runs(client, db_session):
    from controllers.database_controller import celerytaskinfo_ops

    org, u = _login_with_org(client, db_session, "setup-busy@example.com")
    folder = H.make_folder(db_session, org.id)
    client.set_cookie("bdk_filing", str(folder.id))
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id="setup-busy-task",
        status="PENDING",
        operation_type="Upload",
        operation_detail="Added more files to a filing",
        user_email=u.email,
        organization_id=org.id,
        folder_deadline=folder.deadline,
        session=db_session,
    )
    html = client.get("/setup").get_data(as_text=True)
    assert "Building your map…" in html
    assert "/setup/stage" in html  # polls itself


def test_setup_complete_filing_redirects_to_map(client, db_session):
    org, u = _login_with_org(client, db_session, "setup-done@example.com")
    folder = H.make_folder(db_session, org.id)
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    H.seed_coverage(
        db_session,
        folder.id,
        LINES_GEOJSON,
        filename="route.geojson",
        filetype="wired",
        techType=50,
    )
    client.set_cookie("bdk_filing", str(folder.id))
    resp = client.get("/setup")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/map"
