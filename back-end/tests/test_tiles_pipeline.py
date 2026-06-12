"""Tile-pipeline tests running the REAL create_tiles (tippecanoe, in Docker).

Tiles previously had no correctness gate at all (the goldens assert kml_data
and the export CSV; the map tests assert routing against pre-seeded rows).
These tests pin the storage contract of the build pipeline itself:

- a full build produces ONE tileset: a single mbtiles row whose vector_tiles
  rows span the whole z0-16 pyramid (internally it is two tippecanoe runs -
  overview zooms z0-8 with density dropping, detail zooms z9-16 drop-free -
  merged into that one row set);
- the mbtiles file blob is NOT stored (vector_tiles rows are the only
  serving truth, and nothing ever read the blob back);
- folder.copy snapshots carry the tile rows, not a blob;
- the rebuild path (_rebuild_folder_tiles) replaces the tileset instead of
  accumulating, and serves through retrieve_tiles afterwards.
"""

import gzip
import json
import math

import pytest

from tests import conftest_helpers as H

pytestmark = pytest.mark.tippecanoe


# A small grid of fabric locations around (-80.0, 37.25) with a coverage
# polygon over its middle: enough features for tippecanoe to emit tiles at
# every zoom, small enough to tile in well under a second.
GRID_N = 20
LON0, LAT0, STEP = -80.10, 37.20, 0.01
COV_POLY = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-80.06, 37.24],
                        [-79.96, 37.24],
                        [-79.96, 37.30],
                        [-80.06, 37.30],
                        [-80.06, 37.24],
                    ]
                ],
            },
        }
    ],
}


def lonlat_to_tile(lon, lat, z):
    n = 2**z
    x = int((lon + 180) / 360 * n)
    r = math.radians(lat)
    y = int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)
    return x, y


def seed_tile_folder(s):
    """Org + folder + fabric grid + one coverage polygon with served points."""
    from database.models import fabric_data, kml_data

    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    fab = H.seed_coverage(s, folder.id, b"stub", "fab.csv", "fabric", None)
    cov = H.seed_coverage(s, folder.id, json.dumps(COV_POLY).encode(), "cov.geojson", "wired", 50)

    loc = 1000
    for i in range(GRID_N):
        for j in range(GRID_N):
            lon, lat = LON0 + i * STEP, LAT0 + j * STEP
            s.add(
                fabric_data(
                    file_id=fab.id,
                    location_id=loc,
                    latitude=lat,
                    longitude=lon,
                    address_primary=f"{loc} MAIN ST",
                    bsl_flag="True",
                )
            )
            if -80.06 <= lon <= -79.96 and 37.24 <= lat <= 37.30:
                s.add(
                    kml_data(
                        location_id=loc,
                        served=True,
                        wireless=False,
                        lte=False,
                        coveredLocations="cov.geojson",
                        maxDownloadNetwork="cov.geojson",
                        maxDownloadSpeed=100,
                        maxUploadSpeed=20,
                        techType=50,
                        file_id=cov.id,
                        address_primary=f"{loc} MAIN ST",
                        longitude=lon,
                        latitude=lat,
                    )
                )
            loc += 1
    s.commit()
    return folder, fab, cov


def build_tiles(s, folder, cov):
    from controllers.database_controller import vt_ops

    geojson_array = vt_ops.read_geojson(cov.id, s)
    vt_ops.create_tiles(geojson_array, folder.id, s)


def folder_tilesets(s, folderid):
    from database.models import mbtiles

    return s.query(mbtiles).filter(mbtiles.folder_id == folderid).all()


def tile_rows(s, mbtiles_id):
    from database.models import vector_tiles

    return s.query(vector_tiles).filter(vector_tiles.mbtiles_id == mbtiles_id).all()


def test_full_build_one_tileset_full_pyramid_no_blob(db_session):
    from controllers.database_controller import vt_ops

    folder, fab, cov = seed_tile_folder(db_session)
    build_tiles(db_session, folder, cov)
    db_session.expire_all()

    sets = folder_tilesets(db_session, folder.id)
    assert len(sets) == 1
    assert sets[0].tile_data is None  # blob is dead weight; rows are the truth

    rows = tile_rows(db_session, sets[0].id)
    zooms = {r.zoom_level for r in rows}
    assert zooms == set(range(17))  # both runs landed in the one tileset

    # The grid center must serve at an overview zoom and a detail zoom.
    center_lon, center_lat = LON0 + GRID_N // 2 * STEP, LAT0 + GRID_N // 2 * STEP
    for z in (6, 9, 16):
        x, y = lonlat_to_tile(center_lon, center_lat, z)
        tms_y = (2**z - 1) - y
        tile = vt_ops.retrieve_tiles(z, x, tms_y, folder.id)
        assert tile is not None, f"no tile at z{z}"
        assert tile.tile_data[:2] == b"\x1f\x8b"  # gzipped PBF
        assert gzip.decompress(tile.tile_data)


def test_rebuild_replaces_tileset(db_session):
    from controllers.celery_controller import celery_tasks as ct

    folder, fab, cov = seed_tile_folder(db_session)
    build_tiles(db_session, folder, cov)
    first = folder_tilesets(db_session, folder.id)[0].id

    # The rebuild path (edit retiles, regenerate) must swap, not accumulate.
    ct._rebuild_folder_tiles(folder.id)
    db_session.expire_all()
    sets = folder_tilesets(db_session, folder.id)
    assert len(sets) == 1
    assert sets[0].id != first
    assert sets[0].tile_data is None
    assert {r.zoom_level for r in tile_rows(db_session, sets[0].id)} == set(range(17))


def snapshot_rows(s, mbtiles_id):
    return {
        (r.zoom_level, r.tile_column, r.tile_row): bytes(r.tile_data)
        for r in tile_rows(s, mbtiles_id)
    }


def test_splice_matches_full_rebuild_byte_for_byte(db_session):
    """THE splice gate: after an edit-shaped change, regenerating only the
    dirty region and splicing the rows into the live tileset must produce
    byte-identical z9-16 tiles to a full rebuild — inside the region (same
    content) and outside it (untouched). z0-8 stays deliberately stale."""
    from controllers.celery_controller import celery_tasks as ct
    from controllers.database_controller import vt_ops
    from database.models import kml_data

    folder, fab, cov = seed_tile_folder(db_session)
    build_tiles(db_session, folder, cov)
    db_session.expire_all()
    tileset = folder_tilesets(db_session, folder.id)[0]
    before = snapshot_rows(db_session, tileset.id)

    # The "edit": exclude every served location inside a small box (exactly
    # what an exclusion edit does - it deletes the kml rows).
    EDIT = (-80.03, 37.25, -80.00, 37.27)  # minx, miny, maxx, maxy
    doomed = (
        db_session.query(kml_data)
        .filter(
            kml_data.file_id == cov.id,
            kml_data.longitude >= EDIT[0],
            kml_data.longitude <= EDIT[2],
            kml_data.latitude >= EDIT[1],
            kml_data.latitude <= EDIT[3],
        )
        .all()
    )
    assert doomed, "the edit box must catch served points"
    for row in doomed:
        db_session.delete(row)
    db_session.commit()

    assert vt_ops.splice_tiles(folder.id, [list(EDIT)], db_session) is True
    db_session.expire_all()
    sets = folder_tilesets(db_session, folder.id)
    assert len(sets) == 1 and sets[0].id == tileset.id  # spliced IN PLACE
    spliced = snapshot_rows(db_session, tileset.id)

    # Reference: what a full rebuild produces from the same DB truth.
    ct._rebuild_folder_tiles(folder.id)
    db_session.expire_all()
    rebuilt = snapshot_rows(db_session, folder_tilesets(db_session, folder.id)[0].id)

    spliced_hi = {k: v for k, v in spliced.items() if k[0] >= 9}
    rebuilt_hi = {k: v for k, v in rebuilt.items() if k[0] >= 9}
    assert spliced_hi.keys() == rebuilt_hi.keys()
    diff = [k for k in rebuilt_hi if spliced_hi[k] != rebuilt_hi[k]]
    assert diff == [], f"{len(diff)} z9-16 tiles differ from a full rebuild"

    # The splice must have actually changed something (the edit is visible)...
    ranges = vt_ops.dirty_z9_ranges([list(EDIT)])
    changed = [k for k in spliced_hi if spliced_hi[k] != before.get(k)]
    assert changed, "the spliced region should differ from the pre-edit tiles"
    # ...while every changed tile lies inside the dirty region (locality).
    for z, x, y_tms in changed:
        y_xyz = (2**z - 1) - y_tms
        assert vt_ops._in_ranges(z, x, y_xyz, ranges), (
            f"tile {(z, x, y_tms)} outside the region changed"
        )

    # z0-8 untouched (stale by design until the settle rebuild).
    for k, v in spliced.items():
        if k[0] <= 8:
            assert before[k] == v


def test_splice_without_tileset_falls_back(db_session):
    from controllers.database_controller import vt_ops

    folder, fab, cov = seed_tile_folder(db_session)
    # No tiles built yet -> nothing to splice into.
    assert vt_ops.splice_tiles(folder.id, [[-80.03, 37.25, -80.00, 37.27]], db_session) is False


def test_folder_copy_carries_rows_not_blob(db_session):
    folder, fab, cov = seed_tile_folder(db_session)
    build_tiles(db_session, folder, cov)
    db_session.expire_all()
    src = folder_tilesets(db_session, folder.id)[0]
    n_rows = len(tile_rows(db_session, src.id))
    assert n_rows > 0

    new_folder = folder.copy(session=db_session, export=True)
    db_session.commit()
    copies = folder_tilesets(db_session, new_folder.id)
    assert len(copies) == 1
    assert copies[0].tile_data is None
    assert len(tile_rows(db_session, copies[0].id)) == n_rows
