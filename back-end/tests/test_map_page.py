"""The studio map page (/map) — the island's server side.

Pins:
  - the server-provided initial state (the boundary contract): filing, tile
    URL, layers grouped by technology with fixed colors, plans for the
    inspector verbs, bounds, persisted edits;
  - the filing card's ABSOLUTE served count (never a ratio) and the edits
    list with plain-words summaries (incl. set-plan edits);
  - read-only contexts: a filed filing and a snapshot view (?folder=) hide
    the draw affordances server-side; foreign folders bounce;
  - POST /map/edit (the real edit flow, returning the task id) and the
    short-lived per-task SSE stream (org-scoped);
  - /map/exclusions server truth.
"""

import json

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session, make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
    (1002, "2 ELM AVE", "TRUE", 37.281, -79.94, "51161", "VA"),
    (1003, "3 OAK LN", "TRUE", 37.50, -79.95, "51161", "VA"),
]

POLYGON_GEOJSON = b"""{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},
"geometry":{"type":"Polygon","coordinates":[[[-80.01,37.27],[-79.90,37.27],[-79.90,37.31],
[-80.01,37.31],[-80.01,37.27]]]}}]}"""

EDIT_AREA = {
    "type": "Feature",
    "properties": {},
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [-79.96, 37.275],
                [-79.93, 37.275],
                [-79.93, 37.285],
                [-79.96, 37.285],
                [-79.96, 37.275],
            ]
        ],
    },
}


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


def _login_ready(client, db_session, email):
    from services import plan_service

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
    plan = plan_service.save_plan(
        folder.id,
        name="AirLink 100",
        tech_code=70,
        max_download=100,
        max_upload=20,
        session=db_session,
        is_default=True,
    )
    return org, folder, cov, plan


def _config(html):
    start = html.index('id="bdk-map-config">') + len('id="bdk-map-config">')
    end = html.index("</script>", start)
    return json.loads(html[start:end])


# -------------------------------------------------------------- rendering


def test_map_unauthenticated_redirects(client):
    resp = client.get("/map")
    assert resp.status_code == 302


def test_map_without_filing_explains(client, db_session):
    login_page_session(client, email="nomapfiling@example.com")
    html = client.get("/map").get_data(as_text=True)
    assert "No filing yet" in html


def test_map_config_blob_carries_the_contract(client, db_session):
    org, folder, cov, plan = _login_ready(client, db_session, "mapcfg@example.com")
    html = client.get("/map").get_data(as_text=True)
    cfg = _config(html)
    assert cfg["folderId"] == folder.id
    assert cfg["tileUrl"] == f"/api/tiles/{folder.id}/{{z}}/{{x}}/{{y}}.pbf"
    assert cfg["layers"] == [{"name": "sector.geojson", "type": "wireless", "tech": 70}]
    assert cfg["techNames"]["70"] == "Unlicensed FW"
    assert cfg["plansByTech"]["70"][0]["name"] == "AirLink 100"
    assert cfg["bounds"] is not None
    assert cfg["readOnly"] is False
    assert cfg["hasFabric"] is True
    # The popup's plan lines come from /map/location/<id> alone (one source
    # of truth) — the config no longer ships a file-level guess to flash.
    assert "planByFile" not in cfg


def test_map_filing_card_absolute_count_and_chrome(client, db_session):
    org, folder, cov, plan = _login_ready(client, db_session, "mapcard@example.com")
    html = client.get("/map").get_data(as_text=True)
    assert "2 served" in html  # absolute count, never a "2/3"-style ratio
    assert "Unlicensed FW" in html
    assert "Draw an edit" in html
    assert "Find an address…" in html
    assert "maplibre-gl.js" in html


def test_map_no_fabric_nudge(client, db_session):
    login_page_session(client, email="mapnofab@example.com")
    org = H.make_org(db_session, name="mapnofab-org")
    u = _get_user(db_session, "mapnofab@example.com")
    u.organization_id = org.id
    db_session.commit()
    folder = H.make_folder(db_session, org.id)
    H.seed_coverage(
        db_session,
        folder.id,
        POLYGON_GEOJSON,
        filename="sector.geojson",
        filetype="wireless",
        techType=70,
    )
    html = client.get("/map").get_data(as_text=True)
    assert "Locations stay dark until the fabric is in" in html
    assert "Search needs the fabric" in html


def test_map_filed_is_read_only(client, db_session):
    org, folder, cov, plan = _login_ready(client, db_session, "mapfiled@example.com")
    folder.status = "filed"
    db_session.commit()
    html = client.get("/map").get_data(as_text=True)
    assert "Draw an edit" not in html  # mutating affordances hidden
    assert "marked as filed" in html and "Reopen for edits" in html
    assert _config(html)["readOnly"] is True


def test_map_snapshot_view_is_read_only_and_scoped(client, db_session, no_tiles):

    org, folder, cov, plan = _login_ready(client, db_session, "mapsnap@example.com")
    snap = folder.copy(
        name="snap", type="export", deadline=folder.deadline, export=True, session=db_session
    )
    db_session.commit()

    html = client.get(f"/map?folder={snap.id}").get_data(as_text=True)
    assert "read-only" in html and "Back to working filing" in html
    assert "Draw an edit" not in html

    # A foreign folder bounces back to the working filing.
    other = H.make_org(db_session, name="mapsnap-other")
    their = H.make_folder(db_session, other.id)
    assert client.get(f"/map?folder={their.id}").status_code == 302


def test_map_edits_list_summarizes_set_plan_edits(client, db_session, no_tiles):
    from services import edit_service

    org, folder, cov, plan = _login_ready(client, db_session, "mapedits@example.com")
    u = _get_user(db_session, "mapedits@example.com")
    edit_service.apply_edit(
        user_id=u.id,
        folderid=folder.id,
        markers=[
            [
                {"id": 1001, "editedFile": [cov.name], "plan_id": plan.id},
                {"id": 1002, "editedFile": [cov.name]},
            ]
        ],
        polygonfeatures=[EDIT_AREA],
        session=db_session,
    )
    html = client.get("/map").get_data(as_text=True)
    assert "set AirLink 100 on Unlicensed FW" in html
    assert "excluded Unlicensed FW" in html
    assert "undo" in html


# -------------------------------------------------------------- endpoints


def test_map_edit_applies_and_returns_task_id(client, db_session, no_tiles):
    from database.models import kml_data

    org, folder, cov, plan = _login_ready(client, db_session, "mapedit2@example.com")
    resp = client.post(
        "/map/edit",
        json={
            "folderid": folder.id,
            "markers": [[{"id": 1001, "editedFile": [cov.name], "plan_id": plan.id}]],
            "polygonfeatures": [EDIT_AREA],
        },
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["task_id"]
    db_session.expire_all()
    row = (
        db_session.query(kml_data)
        .filter(kml_data.file_id == cov.id, kml_data.location_id == 1001)
        .one()
    )
    assert row.maxDownloadSpeed == 100  # the plan's value stamped


def test_map_location_detail_resolves_governing_plan(client, db_session, no_tiles):
    """The point popup's truth endpoint: per covering file, the kml row's
    stamped speeds + the governing plan's NAME — area-edit marker > file
    assignment > tech default. A plan edit reflects immediately (write-through),
    and an area edit that sets a different plan names THAT plan."""
    from services import edit_service, plan_service

    org, folder, cov, plan = _login_ready(client, db_session, "locdetail@example.com")
    u = _get_user(db_session, "locdetail@example.com")

    d = client.get("/map/location/1001").get_json()
    assert d["status"] == "success"
    assert d["services"] == [
        {"file": cov.name, "tech": 70, "plan": "AirLink 100", "down": 100, "up": 20}
    ]

    # Editing the default plan's speeds shows up immediately.
    plan_service.save_plan(
        folder.id, "AirLink 100", 70, 250, 25, db_session, plan_id=plan.id, is_default=True
    )
    d = client.get("/map/location/1001").get_json()
    assert d["services"][0]["down"] == 250

    # An area edit setting another plan overrides the default — by name too.
    lite = plan_service.save_plan(folder.id, "AirLink Lite", 70, 25, 5, db_session)
    edit_service.apply_edit(
        user_id=u.id,
        folderid=folder.id,
        markers=[[{"id": 1001, "editedFile": [cov.name], "plan_id": lite.id}]],
        polygonfeatures=[EDIT_AREA],
        session=db_session,
    )
    d = client.get("/map/location/1001").get_json()
    assert d["services"] == [
        {"file": cov.name, "tech": 70, "plan": "AirLink Lite", "down": 25, "up": 5}
    ]


def test_map_location_detail_scopes_to_requested_folder(client, db_session, no_tiles):
    """The popup is the DB's single source of truth, so it must read the
    folder being VIEWED: ?folder= scopes the lookup (org-checked), and a
    snapshot keeps its stamped speeds even after the working filing moves on."""
    from services import plan_service

    org, folder, cov, plan = _login_ready(client, db_session, "locscope@example.com")
    snap = folder.copy(
        name="snap", type="export", deadline=folder.deadline, export=True, session=db_session
    )
    db_session.commit()

    # Speeds diverge after the snapshot: the working filing moves to 250/25.
    plan_service.save_plan(
        folder.id, "AirLink 100", 70, 250, 25, db_session, plan_id=plan.id, is_default=True
    )

    d = client.get(f"/map/location/1001?folder={snap.id}").get_json()
    assert d["services"][0]["down"] == 100  # the snapshot's stamped value
    d = client.get("/map/location/1001").get_json()
    assert d["services"][0]["down"] == 250  # default: the working filing

    # A foreign folder is invisible.
    other = H.make_org(db_session, name="locscope-other")
    their = H.make_folder(db_session, other.id)
    assert client.get(f"/map/location/1001?folder={their.id}").status_code == 404


def test_edit_detail_and_replace_roundtrip(client, db_session, no_tiles):
    """The edit-an-edit flow: GET /map/edit/<id> hands back the saved shape +
    per-point picks; POST /map/edit/<id>/replace updates them IN PLACE (one
    editfile before and after) and the op-4 recompute applies the new picks."""
    from database.models import editfile as editfile_model
    from database.models import kml_data
    from services import edit_service

    org, folder, cov, plan = _login_ready(client, db_session, "editedit@example.com")
    u = _get_user(db_session, "editedit@example.com")
    edit_service.apply_edit(
        user_id=u.id,
        folderid=folder.id,
        markers=[[{"id": 1001, "editedFile": [cov.name]}]],  # exclude 1001
        polygonfeatures=[EDIT_AREA],
        session=db_session,
    )
    db_session.expire_all()
    ef = db_session.query(editfile_model).filter_by(folder_id=folder.id).one()
    assert (
        db_session.query(kml_data).filter_by(file_id=cov.id, location_id=1001).count() == 0
    )  # excluded

    d = client.get(f"/map/edit/{ef.id}").get_json()
    assert d["status"] == "success"
    assert d["markers"] == [{"id": 1001, "editedFile": [cov.name]}]
    assert d["feature"]["geometry"]["type"] == "Polygon"
    assert d["name"] == ef.name

    # Replace: same shape, but the pick becomes set-plan instead of exclude.
    resp = client.post(
        f"/map/edit/{ef.id}/replace",
        json={
            "markers": [{"id": 1001, "editedFile": [cov.name], "plan_id": plan.id}],
            "polygonfeature": EDIT_AREA,
        },
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["task_id"]
    db_session.expire_all()
    # The point is back (recomputed) wearing the plan's values...
    row = db_session.query(kml_data).filter_by(file_id=cov.id, location_id=1001).one()
    assert row.maxDownloadSpeed == 100
    # ...and it's still ONE edit — replaced, not added.
    assert db_session.query(editfile_model).filter_by(folder_id=folder.id).count() == 1
    db_session.refresh(ef)
    assert ef.markers[0]["plan_id"] == plan.id


def test_edit_detail_and_replace_are_org_scoped(client, db_session, no_tiles):
    """Another org's edit is invisible to both endpoints."""
    from controllers.database_controller import editfile_ops

    _login_ready(client, db_session, "editscope@example.com")
    other = H.make_org(db_session, name="editscope-other")
    their_folder = H.make_folder(db_session, other.id)
    their_ef = editfile_ops.create_editfile(
        filename="their_edit",
        content=b'{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[]}}',
        folderid=their_folder.id,
        session=db_session,
        markers=[{"id": 1, "editedFile": ["x.geojson"]}],
    )
    db_session.commit()

    assert client.get(f"/map/edit/{their_ef.id}").status_code == 404
    resp = client.post(
        f"/map/edit/{their_ef.id}/replace",
        json={"markers": [{"id": 1, "editedFile": ["x.geojson"]}], "polygonfeature": EDIT_AREA},
    )
    assert resp.status_code in (400, 404)


def test_map_edit_foreign_folder_400(client, db_session):
    _login_ready(client, db_session, "mapedit3@example.com")
    other = H.make_org(db_session, name="mapedit3-other")
    their = H.make_folder(db_session, other.id)
    resp = client.post(
        "/map/edit",
        json={
            "folderid": their.id,
            "markers": [[{"id": 1, "editedFile": ["x"]}]],
            "polygonfeatures": [EDIT_AREA],
        },
    )
    assert resp.status_code == 400


def test_map_exclusions_lists_editfile_features(client, db_session, no_tiles):
    from services import edit_service

    org, folder, cov, plan = _login_ready(client, db_session, "mapexcl@example.com")
    u = _get_user(db_session, "mapexcl@example.com")
    edit_service.apply_edit(
        user_id=u.id,
        folderid=folder.id,
        markers=[[{"id": 1001, "editedFile": [cov.name]}]],
        polygonfeatures=[EDIT_AREA],
        session=db_session,
    )
    data = client.get("/map/exclusions").get_json()
    assert data["status"] == "success"
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["editfileId"]


def test_map_edit_events_is_org_scoped(client, db_session, no_tiles):
    from utils.flask_app import app

    org, folder, cov, plan = _login_ready(client, db_session, "mapsse@example.com")
    resp = client.post(
        "/map/edit",
        json={
            "folderid": folder.id,
            "markers": [[{"id": 1001, "editedFile": [cov.name]}]],
            "polygonfeatures": [EDIT_AREA],
        },
    )
    task_id = resp.get_json()["task_id"]

    app.config["MAP_TASK_SSE_MAX_TICKS"] = 3
    app.config["JOBS_SSE_POLL_SECONDS"] = 0
    try:
        sse = client.get(f"/map/edit-events/{task_id}")
        assert sse.status_code == 200
        assert sse.mimetype == "text/event-stream"
        body = sse.get_data(as_text=True)
        assert "event: done" in body and "SUCCESS" in body  # eager celery: already finished

        with H.CsrfFlaskClient(app) as other:
            login_page_session(other, email="mapsse-other@example.com")
            other_org = H.make_org(db_session, name="mapsse-other-org")
            u = _get_user(db_session, "mapsse-other@example.com")
            u.organization_id = other_org.id
            db_session.commit()
            assert other.get(f"/map/edit-events/{task_id}").status_code == 403
    finally:
        app.config.pop("MAP_TASK_SSE_MAX_TICKS", None)
        app.config.pop("JOBS_SSE_POLL_SECONDS", None)
