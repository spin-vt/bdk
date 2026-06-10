"""Per-point edit markers persisted with editfiles.

An exclusion edit knows exactly which locations were excluded from which
coverage files (the markers). Historically only the drawn polygon was
persisted, so any recompute (e.g. after deleting a different editfile)
re-applied edits *geometrically* — polygon ∩ linked coverage — which is
broader than the original per-point picks (a multi-coverage partial pick
became a blanket exclusion). Markers are now stored on the editfile and the
recompute honors them exactly; editfiles without markers (all pre-existing
data) keep the geometric behavior.
"""

import geopandas as gpd
from shapely.geometry import Point

from tests import conftest_helpers as H

POLYGON = {
    "type": "Feature",
    "properties": {},
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [[-80.01, 37.27], [-80.0, 37.27], [-80.0, 37.28], [-80.01, 37.28], [-80.01, 37.27]]
        ],
    },
}


# three fabric points, all INSIDE the polygon above
def _points_gdf():
    return gpd.GeoDataFrame(
        {"location_id": [1, 2, 3]},
        geometry=[Point(-80.005, 37.275), Point(-80.004, 37.274), Point(-80.003, 37.273)],
        crs="EPSG:4326",
    )


def _seed(s, markers):
    import json

    from controllers.database_controller import editfile_ops, file_editfile_link_ops

    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    cov = H.seed_coverage(s, folder.id, b"stub", "cov.kml", "wired", 50)
    ef = editfile_ops.create_editfile(
        filename="edit_at_test",
        content=json.dumps(POLYGON).encode("utf-8"),
        folderid=folder.id,
        session=s,
        markers=markers,
    )
    s.commit()
    file_editfile_link_ops.link_file_and_editfile(cov.id, ef.id, s)
    s.commit()
    return folder, cov, ef


def test_filter_honors_markers_exactly(db_session):
    """With markers, only the marked locations are excluded — and only for the
    coverage files the marker names. Unmarked points inside the polygon stay."""
    from controllers.database_controller import kml_ops

    s = db_session
    _, cov, _ = _seed(
        s,
        markers=[
            {"id": 1, "editedFile": ["cov.kml"]},
            {"id": 2, "editedFile": ["other.geojson"]},  # excluded from a DIFFERENT file
        ],
    )
    out = kml_ops.filter_points_within_editfile_polygons(_points_gdf(), cov, s)
    assert set(out["location_id"]) == {2, 3}


def test_filter_without_markers_stays_geometric(db_session):
    """Editfiles with no markers (all pre-existing data) keep the legacy
    behavior: every point inside the polygon is excluded."""
    from controllers.database_controller import kml_ops

    s = db_session
    _, cov, _ = _seed(s, markers=None)
    out = kml_ops.filter_points_within_editfile_polygons(_points_gdf(), cov, s)
    assert set(out["location_id"]) == set()


def test_apply_edit_changes_stores_markers(db_session, monkeypatch):
    from controllers.celery_controller import celery_tasks as ct
    from database.models import editfile, kml_data

    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    cov = H.seed_coverage(s, folder.id, b"stub", "cov.kml", "wired", 50)
    s.add(kml_data(location_id=1, served=True, file_id=cov.id, longitude=-80.005, latitude=37.275))
    s.commit()

    markers = [[{"id": 1, "editedFile": ["cov.kml"]}]]
    ct.apply_edit_changes.apply_async(args=[markers, folder.id, [POLYGON]]).get()

    s.expire_all()
    ef = s.query(editfile).filter(editfile.folder_id == folder.id).one()
    assert ef.markers == markers[0]


def test_editfile_copy_preserves_markers(db_session):
    s = db_session
    _, _, ef = _seed(s, markers=[{"id": 1, "editedFile": ["cov.kml"]}])
    org2 = H.make_org(s, name="Org2", provider_id=999999)
    folder2 = H.make_folder(s, org2.id)
    clone = ef.copy(session=s, new_folder_id=folder2.id)
    s.commit()
    assert clone.markers == ef.markers
