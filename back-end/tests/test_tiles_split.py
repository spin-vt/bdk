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

    calls = {"create_tiles": [], "delete_mbtiles": [], "splice": [], "splice_result": True}
    monkeypatch.setattr(
        ct.vt_ops, "create_tiles", lambda gj, fid, s: calls["create_tiles"].append(fid)
    )
    monkeypatch.setattr(
        ct.mbtiles_ops, "delete_mbtiles", lambda fid, s: calls["delete_mbtiles"].append(fid)
    )

    def fake_splice(fid, bboxes, s):
        calls["splice"].append((fid, bboxes))
        return calls["splice_result"]

    monkeypatch.setattr(ct.vt_ops, "splice_tiles", fake_splice)
    # read_kml/read_geojson return flat feature LISTS (one ldjson line each).
    monkeypatch.setattr(ct.vt_ops, "read_kml", lambda fid, s: [])
    monkeypatch.setattr(ct.vt_ops, "read_geojson", lambda fid, s: [])
    return ct, calls


def _b(value):
    return value.encode() if isinstance(value, str) else value


class _StubPipeline:
    """Queues commands like redis-py's transactional pipeline."""

    def __init__(self, stub):
        self.stub = stub
        self.ops = []

    def lrange(self, key, start, end):
        self.ops.append(lambda: self.stub.lrange(key, start, end))

    def get(self, key):
        self.ops.append(lambda: self.stub.get(key))

    def delete(self, key):
        self.ops.append(lambda: self.stub.delete(key))

    def execute(self):
        return [op() for op in self.ops]


class _StubRedis:
    """Just enough of the redis interface for the dirty/lock/settle flags.
    Returns bytes like redis-py does."""

    def __init__(self):
        self.store = {}
        self.sets = []  # every key ever set, for asserting the lock was taken

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        self.sets.append(key)
        return True

    def get(self, key):
        return _b(self.store.get(key))

    def delete(self, key):
        self.store.pop(key, None)

    def rpush(self, key, value):
        self.store.setdefault(key, []).append(value)
        self.sets.append(key)

    def lrange(self, key, start, end):
        assert (start, end) == (0, -1)
        return [_b(v) for v in self.store.get(key, [])]

    def scan_iter(self, match):
        import fnmatch

        return [_b(k) for k in list(self.store) if fnmatch.fnmatch(k, match)]

    def pipeline(self, transaction=True):
        return _StubPipeline(self)


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


def test_regenerate_tiles_coalesces_and_splices(db_session, tasks, monkeypatch):
    """With redis flags: a refresh only runs if the folder is dirty, and
    edit-scoped (bbox) dirt is SPLICED — only the edited region's tiles are
    regenerated, no full rebuild — leaving a settle flag for the stale
    overview zooms."""
    ct, calls = tasks
    s = db_session
    _, _, folder, _ = _seed_edit_fixture(s)
    stub = _StubRedis()
    monkeypatch.setattr(ct, "_tiles_redis", lambda: stub)

    # not dirty -> tiles already cover current truth -> no refresh
    res = ct.regenerate_tiles.apply_async(args=[folder.id]).get()
    assert calls["create_tiles"] == []
    assert "fresh" in res

    # the apply phase records the edit's bbox -> next regenerate splices
    markers = [[{"id": 123, "editedFile": ["cov.kml"]}]]
    ct.apply_edit_changes.apply_async(args=[markers, folder.id, [POLYGON]]).get()
    assert stub.get(f"bdk:tiles-dirty:{folder.id}") == b"bbox"
    res = ct.regenerate_tiles.apply_async(args=[folder.id]).get()
    assert "spliced" in res
    assert calls["create_tiles"] == []  # no full rebuild
    assert calls["splice"] == [(folder.id, [[-80.01, 37.27, -80.0, 37.28]])]
    assert stub.get(f"bdk:tiles-dirty:{folder.id}") is None
    assert stub.get(f"bdk:tiles-dirty-bbox:{folder.id}") is None
    assert stub.get(f"bdk:tiles-settle:{folder.id}") is not None  # z0-8 stale
    assert stub.get(f"bdk:tiles-lock:{folder.id}") is None  # lock released


def test_splice_failure_falls_back_to_full_rebuild(db_session, tasks, monkeypatch):
    ct, calls = tasks
    s = db_session
    _, _, folder, _ = _seed_edit_fixture(s)
    stub = _StubRedis()
    monkeypatch.setattr(ct, "_tiles_redis", lambda: stub)
    calls["splice_result"] = False  # e.g. no tileset to splice into

    markers = [[{"id": 123, "editedFile": ["cov.kml"]}]]
    ct.apply_edit_changes.apply_async(args=[markers, folder.id, [POLYGON]]).get()
    res = ct.regenerate_tiles.apply_async(args=[folder.id]).get()
    assert "rebuilt" in res
    assert calls["splice"] != []  # tried
    assert calls["create_tiles"] == [folder.id]  # fell back
    assert stub.get(f"bdk:tiles-settle:{folder.id}") is None  # full = settled


def test_full_dirt_wins_over_bboxes(db_session, tasks, monkeypatch):
    """A whole-tileset change (upload, recompute) coalescing with an edit must
    full-rebuild — splicing only the edit's region would miss the rest."""
    ct, calls = tasks
    s = db_session
    _, _, folder, _ = _seed_edit_fixture(s)
    stub = _StubRedis()
    monkeypatch.setattr(ct, "_tiles_redis", lambda: stub)

    ct._mark_tiles_dirty(folder.id)  # process_data style: everything stale
    ct._mark_tiles_dirty(folder.id, bbox=[-80.01, 37.27, -80.0, 37.28])
    assert stub.get(f"bdk:tiles-dirty:{folder.id}") == b"full"  # bbox didn't downgrade

    res = ct.regenerate_tiles.apply_async(args=[folder.id]).get()
    assert "rebuilt" in res
    assert calls["splice"] == []
    assert calls["create_tiles"] == [folder.id]


def test_settle_task_rebuilds_quiet_folders(db_session, tasks, monkeypatch):
    import time as time_mod

    ct, calls = tasks
    s = db_session
    _, _, folder, _ = _seed_edit_fixture(s)
    stub = _StubRedis()
    monkeypatch.setattr(ct, "_tiles_redis", lambda: stub)
    dispatched = []
    monkeypatch.setattr(ct.regenerate_tiles, "apply_async", lambda args: dispatched.append(args[0]))

    # A folder spliced moments ago: still in its quiet window -> left alone.
    stub.set(f"bdk:tiles-settle:{folder.id}", str(time_mod.time()))
    ct.settle_stale_tiles.run()
    assert dispatched == []

    # Quiet long enough -> one full rebuild dispatched, flag consumed.
    stub.set(f"bdk:tiles-settle:{folder.id}", str(time_mod.time() - ct.TILES_SETTLE_QUIET - 1))
    ct.settle_stale_tiles.run()
    assert dispatched == [folder.id]
    assert stub.get(f"bdk:tiles-settle:{folder.id}") is None
    assert stub.get(f"bdk:tiles-dirty:{folder.id}") == b"full"


def test_process_data_uses_coalesced_rebuild(db_session, tasks, monkeypatch):
    """process_data's tile step goes through the same per-folder lock +
    dirty-flag path as edit retiles, so upload/delete/regenerate rebuilds
    coalesce with edit rebuilds instead of racing them."""
    ct, calls = tasks
    s = db_session
    _, _, folder, _ = _seed_edit_fixture(s)
    stub = _StubRedis()
    monkeypatch.setattr(ct, "_tiles_redis", lambda: stub)
    # stub the heavy coverage compute; we're testing the tile-step plumbing
    monkeypatch.setattr(ct.kml_ops, "add_network_data", lambda *a, **k: None)

    ct.process_data.apply_async(args=[folder.id, 1]).get()

    assert calls["create_tiles"] == [folder.id]
    assert any(k == f"bdk:tiles-lock:{folder.id}" for k in stub.sets)  # lock taken
    assert stub.get(f"bdk:tiles-dirty:{folder.id}") is None  # marked + consumed
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
