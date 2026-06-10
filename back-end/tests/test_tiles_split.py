"""Tests for the edit-apply / tile-regeneration split.

An edit used to be one monolithic celery task (editfile + kml_data changes +
a full tippecanoe retile). It is now a chain: `apply_edit_changes` (fast —
after it, DB truth is correct and exports are right) followed by
`regenerate_tiles` (slow — rebuilds the folder's vector tiles, debounced via
redis dirty/lock flags so rapid edits coalesce into one rebuild).

The heavy tile pipeline (tippecanoe) is stubbed; we test orchestration.
"""

import json

import pytest

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


@pytest.fixture()
def tasks(monkeypatch):
    """celery_tasks with the tile pipeline stubbed; records rebuild calls."""
    from controllers.celery_controller import celery_tasks as ct

    calls = {"create_tiles": [], "delete_mbtiles": []}
    monkeypatch.setattr(
        ct.vt_ops, "create_tiles", lambda gj, fid, s: calls["create_tiles"].append(fid)
    )
    monkeypatch.setattr(
        ct.mbtiles_ops, "delete_mbtiles", lambda fid, s: calls["delete_mbtiles"].append(fid)
    )
    empty = {"type": "FeatureCollection", "features": []}
    monkeypatch.setattr(ct.vt_ops, "read_kml", lambda fid, s: empty)
    monkeypatch.setattr(ct.vt_ops, "read_geojson", lambda fid, s: empty)
    return ct, calls


class _StubRedis:
    """Just enough of the redis interface for the dirty/lock flags."""

    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)


def _seed_edit_fixture(s):
    """Org + folder + one coverage file with one served kml_data location."""
    from database.models import kml_data

    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id, email="editor@example.com")
    folder = H.make_folder(s, org.id)
    cov = H.seed_coverage(s, folder.id, b"stub", "cov.kml", "wired", 50)
    s.add(
        kml_data(location_id=123, served=True, file_id=cov.id, longitude=-80.005, latitude=37.275)
    )
    s.commit()
    return org, user, folder, cov


def test_apply_phase_updates_db_without_retiling(db_session, tasks):
    ct, calls = tasks
    s = db_session
    _, _, folder, cov = _seed_edit_fixture(s)
    from database.models import editfile, file_editfile_link, kml_data

    markers = [[{"id": 123, "editedFile": ["cov.kml"]}]]
    ct.apply_edit_changes.apply_async(args=[markers, folder.id, [POLYGON]]).get()

    s.expire_all()
    assert s.query(kml_data).filter(kml_data.location_id == 123).count() == 0
    efs = s.query(editfile).filter(editfile.folder_id == folder.id).all()
    assert len(efs) == 1
    assert json.loads(bytes(efs[0].data).decode("utf-8")) == POLYGON
    links = s.query(file_editfile_link).filter(file_editfile_link.editfile_id == efs[0].id).all()
    assert [ln.file_id for ln in links] == [cov.id]
    # the whole point of the split: applying the edit does NOT rebuild tiles
    assert calls["create_tiles"] == []
    assert calls["delete_mbtiles"] == []


def test_regenerate_tiles_rebuilds(db_session, tasks):
    ct, calls = tasks
    s = db_session
    _, _, folder, _ = _seed_edit_fixture(s)

    ct.regenerate_tiles.apply_async(args=[folder.id]).get()

    assert calls["delete_mbtiles"] == [folder.id]
    assert calls["create_tiles"] == [folder.id]


def test_regenerate_tiles_coalesces_when_fresh(db_session, tasks, monkeypatch):
    """With redis flags: a rebuild only runs if the folder is dirty, so a
    queued regenerate whose edits were covered by an earlier rebuild no-ops."""
    ct, calls = tasks
    s = db_session
    _, _, folder, _ = _seed_edit_fixture(s)
    stub = _StubRedis()
    monkeypatch.setattr(ct, "_tiles_redis", lambda: stub)

    # not dirty -> tiles already cover current truth -> no rebuild
    res = ct.regenerate_tiles.apply_async(args=[folder.id]).get()
    assert calls["create_tiles"] == []
    assert "fresh" in res

    # the apply phase marks the folder dirty -> next regenerate rebuilds + clears
    markers = [[{"id": 123, "editedFile": ["cov.kml"]}]]
    ct.apply_edit_changes.apply_async(args=[markers, folder.id, [POLYGON]]).get()
    assert stub.get(f"bdk:tiles-dirty:{folder.id}") is not None
    res = ct.regenerate_tiles.apply_async(args=[folder.id]).get()
    assert calls["create_tiles"] == [folder.id]
    assert "rebuilt" in res
    assert stub.get(f"bdk:tiles-dirty:{folder.id}") is None
    assert stub.get(f"bdk:tiles-lock:{folder.id}") is None  # lock released


def test_apply_edit_service_runs_full_chain(db_session, tasks):
    """End-to-end through the service (eager celery): one call applies the DB
    edit AND regenerates tiles, and the recorded task id tracks the chain's
    final (tile) task so 'task done' still means 'tiles done'."""
    ct, calls = tasks
    s = db_session
    _, user, folder, _ = _seed_edit_fixture(s)
    from database.models import celerytaskinfo, kml_data
    from services import edit_service

    task_id = edit_service.apply_edit(
        user_id=user.id,
        folderid=folder.id,
        markers=[[{"id": 123, "editedFile": ["cov.kml"]}]],
        polygonfeatures=[POLYGON],
        session=s,
    )

    s.expire_all()
    assert s.query(kml_data).filter(kml_data.location_id == 123).count() == 0
    assert calls["create_tiles"] == [folder.id]
    info = s.query(celerytaskinfo).filter(celerytaskinfo.task_id == task_id).one()
    assert info.operation_type == "Edit"
    assert info.files_changed == "cov.kml"
