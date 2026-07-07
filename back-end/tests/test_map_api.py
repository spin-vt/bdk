"""Contract tests for the endpoints the studio map (/map) builds on.

The tile-serving route (validation, ownership, gzip/protobuf headers, the
TMS y-flip), regenerate_map, and the edit-geojson centroid lookup.
"""

import gzip
import json

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session, make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),  # inside coverage
    (1002, "2 ELM AVE", "TRUE", 37.50, -79.95, "51161", "VA"),  # outside coverage
]

POLYGON_GEOJSON = b"""{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},
"geometry":{"type":"Polygon","coordinates":[[[-80.01,37.27],[-79.90,37.27],[-79.90,37.31],
[-80.01,37.31],[-80.01,37.27]]]}}]}"""

EDIT_POLYGON = {
    "type": "Feature",
    "properties": {},
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [-79.96, 37.275],
                [-79.94, 37.275],
                [-79.94, 37.285],
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
    return org, folder, cov


def _seed_tile(db_session, folder_id, zoom=9, x=143, y_tms=312, payload=b"fake-mvt"):
    """A stored vector tile (the DB rows tippecanoe ingestion produces)."""
    from datetime import datetime

    from database.models import mbtiles, vector_tiles

    mb = mbtiles(folder_id=folder_id, filename="t.mbtiles", timestamp=datetime.now())
    db_session.add(mb)
    db_session.flush()
    gz = gzip.compress(payload)
    db_session.add(
        vector_tiles(zoom_level=zoom, tile_column=x, tile_row=y_tms, tile_data=gz, mbtiles_id=mb.id)
    )
    db_session.commit()
    return gz


# ------------------------------------------------------------------ tiles


def test_tile_route_validation_404s(client, db_session):
    _login_with_computed_filing(client, db_session, "tile1@example.com")
    assert client.get("/api/tiles/abc/9/143/199.pbf").status_code == 404
    assert client.get("/api/tiles/-1/9/143/199.pbf").status_code == 404


def test_tile_route_is_org_scoped(client, db_session):
    _login_with_computed_filing(client, db_session, "tile2@example.com")
    other = H.make_org(db_session, name="tile2-other")
    their_folder = H.make_folder(db_session, other.id)
    assert client.get(f"/api/tiles/{their_folder.id}/9/143/199.pbf").status_code == 400


def test_tile_route_serves_gzipped_protobuf_with_tms_flip(client, db_session):
    org, folder, _ = _login_with_computed_filing(client, db_session, "tile3@example.com")
    zoom, x, y_xyz = 9, 143, 199
    y_tms = (2**zoom - 1) - y_xyz  # the route flips XYZ -> TMS before lookup
    gz = _seed_tile(db_session, folder.id, zoom=zoom, x=x, y_tms=y_tms)

    resp = client.get(f"/api/tiles/{folder.id}/{zoom}/{x}/{y_xyz}.pbf")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/x-protobuf"
    assert resp.headers["Content-Encoding"] == "gzip"
    assert resp.data == gz

    # An empty spot is a 404, not an empty 200.
    assert client.get(f"/api/tiles/{folder.id}/{zoom}/{x}/{y_xyz + 1}.pbf").status_code == 404


# ------------------------------------------------------------- regenerate_map


def test_regenerate_map_other_org_400(client, db_session):
    _login_with_computed_filing(client, db_session, "regen1@example.com")
    other = H.make_org(db_session, name="regen1-other")
    their_folder = H.make_folder(db_session, other.id)
    resp = client.post("/api/regenerate_map", json={"folderID": their_folder.id})
    assert resp.status_code == 400


def test_regenerate_map_dispatches_and_records(client, db_session, no_tiles):
    from database.models import celerytaskinfo

    org, folder, _ = _login_with_computed_filing(client, db_session, "regen2@example.com")
    resp = client.post("/api/regenerate_map", json={"folderID": folder.id})
    assert resp.status_code == 200, resp.get_json()
    db_session.expire_all()
    info = db_session.query(celerytaskinfo).filter_by(operation_detail="Regenerate Map").one()
    assert info.organization_id == org.id


# ------------------------------------------------------------- edit geojson


def _make_editfile(db_session, folder_id):
    from controllers.database_controller import editfile_ops

    ef = editfile_ops.create_editfile(
        filename="edit_1",
        content=json.dumps(EDIT_POLYGON).encode(),
        folderid=folder_id,
        session=db_session,
    )
    db_session.commit()
    return ef


def test_get_edit_geojson_centroid_and_ownership(client, db_session):
    org, folder, _ = _login_with_computed_filing(client, db_session, "ej2@example.com")
    ef = _make_editfile(db_session, folder.id)
    resp = client.get(f"/api/get-edit-geojson-centroid/{ef.id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert abs(data["latitude"] - 37.28) < 0.01
    assert abs(data["longitude"] - (-79.95)) < 0.01

    import routes  # noqa: F401
    from utils.flask_app import app

    with H.CsrfFlaskClient(app) as other:
        login_page_session(other, email="ej2-other@example.com")
        other_org = H.make_org(db_session, name="ej2-other-org")
        u = _get_user(db_session, "ej2-other@example.com")
        u.organization_id = other_org.id
        u.verified = True
        db_session.commit()
        assert other.get(f"/api/get-edit-geojson-centroid/{ef.id}").status_code == 400
