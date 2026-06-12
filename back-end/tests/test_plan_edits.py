"""Set-plan area edits — the studio map's third verb (leave / exclude / set plan).

A drawn-area edit's markers can now carry a plan_id alongside editedFile:
  {"id": <location>, "editedFile": [coverage names], "plan_id": <plan>}
Markers WITHOUT plan_id keep today's exclude semantics byte-for-byte (the
golden filings replay unchanged). A plan marker stamps the plan's values onto
the location's kml rows instead of deleting them — and the recompute re-applies
both kinds exactly, so the edit survives any later full recompute and the
export CSV reflects it.
"""

import json

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),  # inside coverage
    (1002, "2 ELM AVE", "TRUE", 37.281, -79.94, "51161", "VA"),  # inside coverage
    (1003, "3 OAK LN", "TRUE", 37.50, -79.95, "51161", "VA"),  # outside coverage
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
def no_tiles(monkeypatch):
    from controllers.celery_controller import celery_tasks as ct

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")


def _seed(db_session):
    """Org + filing + fabric + one computed wireless coverage + a default plan
    and an extra plan."""
    from services import plan_service

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="planedit@example.com")
    user.verified = True
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
        maxDownloadSpeed=100,
        maxUploadSpeed=20,
    )
    H.compute_coverage(db_session, folder.id, cov)
    default = plan_service.save_plan(
        folder.id,
        name="AirLink 100",
        tech_code=70,
        max_download=100,
        max_upload=20,
        session=db_session,
        is_default=True,
    )
    extra = plan_service.save_plan(
        folder.id,
        name="AirLink Lite",
        tech_code=70,
        max_download=25,
        max_upload=5,
        session=db_session,
        low_latency=False,
        category="R",
    )
    return user, folder, cov, default, extra


def _kml_row(session, cov_id, loc_id):
    from database.models import kml_data

    return (
        session.query(kml_data)
        .filter(kml_data.file_id == cov_id, kml_data.location_id == loc_id)
        .one_or_none()
    )


def _apply(db_session, user, folder, markers):
    from services import edit_service

    return edit_service.apply_edit(
        user_id=user.id,
        folderid=folder.id,
        markers=[markers],
        polygonfeatures=[EDIT_AREA],
        session=db_session,
    )


def test_plan_marker_stamps_instead_of_deleting(db_session, no_tiles):
    user, folder, cov, default, extra = _seed(db_session)
    _apply(
        db_session,
        user,
        folder,
        [
            {"id": 1001, "editedFile": [cov.name], "plan_id": extra.id},
        ],
    )
    db_session.expire_all()
    row = _kml_row(db_session, cov.id, 1001)
    assert row is not None  # NOT deleted
    assert row.maxDownloadSpeed == 25 and row.maxUploadSpeed == 5
    assert row.latency == 0 and row.category == "R"
    # the untouched location keeps the file's values
    other = _kml_row(db_session, cov.id, 1002)
    assert other.maxDownloadSpeed == 100


def test_mixed_markers_exclude_and_plan_in_one_area(db_session, no_tiles):
    user, folder, cov, default, extra = _seed(db_session)
    _apply(
        db_session,
        user,
        folder,
        [
            {"id": 1001, "editedFile": [cov.name], "plan_id": extra.id},
            {"id": 1002, "editedFile": [cov.name]},  # no plan_id -> exclude
        ],
    )
    db_session.expire_all()
    assert _kml_row(db_session, cov.id, 1001).maxDownloadSpeed == 25
    assert _kml_row(db_session, cov.id, 1002) is None


def test_recompute_reapplies_plan_and_exclude_markers_exactly(db_session, no_tiles):
    from controllers.celery_controller.celery_tasks import process_data

    user, folder, cov, default, extra = _seed(db_session)
    _apply(
        db_session,
        user,
        folder,
        [
            {"id": 1001, "editedFile": [cov.name], "plan_id": extra.id},
            {"id": 1002, "editedFile": [cov.name]},
        ],
    )
    process_data.apply(args=[folder.id, 4])  # full recompute (eager)
    db_session.expire_all()
    row = _kml_row(db_session, cov.id, 1001)
    assert row is not None and row.maxDownloadSpeed == 25 and row.category == "R"
    assert _kml_row(db_session, cov.id, 1002) is None  # exclusion survived too


def test_set_plan_edit_exports_correctly(db_session, no_tiles):
    from services import export_service

    user, folder, cov, default, extra = _seed(db_session)
    _apply(
        db_session,
        user,
        folder,
        [
            {"id": 1001, "editedFile": [cov.name], "plan_id": extra.id},
        ],
    )
    csv_out, _ = export_service.export_filing(
        user_id=user.id, folderid=folder.id, session=db_session
    )
    body = csv_out.getvalue().decode()
    rows = {r.split(",")[2]: r for r in body.strip().splitlines()[1:]}
    assert rows["1001"].split(",")[4:8] == ["25", "5", "0", "R"]
    # 1002 wears the DEFAULT plan's values (category X) — defaults write
    # through to unassigned files now, superseding the file's own columns.
    assert rows["1002"].split(",")[4:8] == ["100", "20", "1", "X"]


def test_marker_with_missing_plan_acts_as_leave(db_session, no_tiles):
    user, folder, cov, default, extra = _seed(db_session)
    _apply(
        db_session,
        user,
        folder,
        [
            {"id": 1001, "editedFile": [cov.name], "plan_id": 999999},
        ],
    )
    db_session.expire_all()
    row = _kml_row(db_session, cov.id, 1001)
    assert row is not None and row.maxDownloadSpeed == 100  # untouched


def test_folder_copy_remaps_marker_plan_ids(db_session, no_tiles):
    from database.models import editfile as editfile_model
    from database.models import service_plan

    user, folder, cov, default, extra = _seed(db_session)
    _apply(
        db_session,
        user,
        folder,
        [
            {"id": 1001, "editedFile": [cov.name], "plan_id": extra.id},
        ],
    )
    db_session.expire_all()

    new_folder = folder.copy(
        name="copied", type="upload", deadline=folder.deadline, export=False, session=db_session
    )
    db_session.commit()

    copied_plans = {
        p.name: p
        for p in db_session.query(service_plan).filter(service_plan.folder_id == new_folder.id)
    }
    copied_ef = (
        db_session.query(editfile_model).filter(editfile_model.folder_id == new_folder.id).one()
    )
    assert copied_ef.markers[0]["plan_id"] == copied_plans["AirLink Lite"].id
    assert copied_ef.markers[0]["plan_id"] != extra.id  # remapped, not the original


def test_exclude_only_markers_unchanged(db_session, no_tiles):
    """The legacy marker shape (no plan_id) behaves exactly as before."""
    user, folder, cov, default, extra = _seed(db_session)
    _apply(
        db_session,
        user,
        folder,
        [
            {"id": 1001, "editedFile": [cov.name]},
        ],
    )
    db_session.expire_all()
    assert _kml_row(db_session, cov.id, 1001) is None
    assert _kml_row(db_session, cov.id, 1002) is not None


def test_edit_geojson_still_roundtrips_with_plan_markers(db_session, no_tiles):
    """The stored editfile data stays the plain polygon feature (markers live
    in their own column), so the map's exclusion-boxes layer keeps working."""
    from database.models import editfile as editfile_model

    user, folder, cov, default, extra = _seed(db_session)
    _apply(
        db_session,
        user,
        folder,
        [
            {"id": 1001, "editedFile": [cov.name], "plan_id": extra.id},
        ],
    )
    db_session.expire_all()
    ef = db_session.query(editfile_model).filter(editfile_model.folder_id == folder.id).one()
    assert json.loads(ef.data.decode())["geometry"]["type"] == "Polygon"
    assert ef.markers[0]["plan_id"] == extra.id
