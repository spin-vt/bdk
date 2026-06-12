import math
import os
import sqlite3
import subprocess
import uuid
from datetime import datetime
from multiprocessing import Lock

import orjson
import psycopg2
from psycopg2 import Binary
from psycopg2.extras import execute_values
from shapely.geometry import mapping
from sqlalchemy import desc

from controllers.database_controller.kml_ops import get_kml_data
from database.models import mbtiles, vector_tiles
from database.sessions import Session
from utils.settings import DATABASE_URL

from .file_ops import (
    get_file_with_id,
)
from .geo_io import read_geo_bytes

db_lock = Lock()

# The full pyramid is built in TWO tippecanoe runs merged into one tileset:
#
#   z0-8  (overview) — density dropping allowed: a z0 tile contains every
#         fabric point, so thinning is mandatory there. These zooms are only
#         ever produced by full rebuilds.
#   z9-16 (detail)   — built with NO dropping of any kind (-pk -pf, no
#         --drop-densest-as-needed, no byte cap) so a tile's bytes are a pure
#         function of the features that intersect it. tippecanoe's
#         --drop-densest-as-needed shares the min-gap it discovers on an
#         oversized tile across the whole zoom level, making tile content
#         depend on OTHER tiles' density — which both silently thinned dense
#         areas and would make regenerating just an edited region produce
#         different bytes than a full rebuild. Purity at z9-16 is what lets
#         an edit retile regenerate only its dirty region and splice the rows
#         into the live tileset.
TIPPECANOE_SHARED = "--base-zoom=7 -P --force --use-attribute-for-id=location_id --layer=data"
TIPPECANOE_LOW = f"-z 8 --maximum-tile-bytes=3000000 --drop-densest-as-needed {TIPPECANOE_SHARED}"
TIPPECANOE_HIGH = f"-Z 9 -z 16 -pk -pf {TIPPECANOE_SHARED}"


def _features_from_gdf(gdf, name, skip_points=False, keep_types=None):
    """Build GeoJSON Feature dicts from a GeoDataFrame, mirroring the legacy
    read_kml/read_geojson output (a ``feature_type`` and ``network_coverages``
    property per feature)."""
    features = []
    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        geom_type = geom.geom_type
        if skip_points and geom_type == "Point":
            continue
        if keep_types is not None and geom_type not in keep_types:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {
                    "feature_type": geom_type,
                    "network_coverages": name,
                },
            }
        )
    return features


def read_kml(fileid, session):
    file_record = get_file_with_id(fileid, session)
    if not file_record:
        raise ValueError(f"No file found with ID {fileid}")

    # Reads every layer (KML folders are layers); skips Point markers as before.
    gdf = read_geo_bytes(file_record.data, ".kml")
    return _features_from_gdf(gdf, file_record.name, skip_points=True)


def read_geojson(fileid, session):
    file_record = get_file_with_id(fileid, session)
    if not file_record:
        raise ValueError(f"No file found with ID {fileid}")

    gdf = read_geo_bytes(file_record.data, ".geojson")
    # Preserve the original filter: polygons and linestrings only.
    return _features_from_gdf(
        gdf, file_record.name, keep_types={"Polygon", "LineString", "MultiPolygon"}
    )


def add_values_to_VT(geojson_file_path, mbtiles_file_paths, folderid):
    """Store the tiles from one or more freshly built .mbtiles files as ONE
    tileset: a single mbtiles anchor row (no file blob — vector_tiles rows
    are the only thing ever served) plus all the tile rows. The zoom ranges
    of the input files must be disjoint (z0-8 + z9-16)."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM mbtiles WHERE folder_id = %s", (folderid,))
        count = cur.fetchone()[0]
        cur.execute('SELECT "name" FROM "folder" WHERE id = %s', (folderid,))
        foldername = cur.fetchone()[0]
        new_filename = f"{foldername}-{count + 1}.mbtiles"

        cur.execute(
            """
            INSERT INTO mbtiles (tile_data, filename, timestamp, folder_id)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (None, new_filename, datetime.now(), folderid),
        )

        mbt_id = cur.fetchone()[0]

        for mbtiles_file_path in mbtiles_file_paths:
            with sqlite3.connect(mbtiles_file_path) as mb_conn:
                mb_c = mb_conn.cursor()
                mb_c.execute("SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles")
                data = [(row[0], row[1], row[2], Binary(row[3]), mbt_id) for row in mb_c]
            execute_values(
                cur,
                """
                INSERT INTO vector_tiles (zoom_level, tile_column, tile_row, tile_data, mbtiles_id)
                VALUES %s
                """,
                data,
            )

        conn.commit()
    except psycopg2.Error as e:
        print(f"Database error occurred: {e}")
        conn.rollback()
        return -1
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
        conn.rollback()
        return -1
    finally:
        cur.close()
        conn.close()
        for mbtiles_file_path in mbtiles_file_paths:
            if os.path.exists(mbtiles_file_path):
                os.remove(mbtiles_file_path)
        os.remove(geojson_file_path)
    return 1


# def run_tippecanoe_tiles_join(command1, command2, folderid, mbtilepaths):

#     # run first command
#     result1 = subprocess.run(command1, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     if result1.returncode != 0:
#         raise Exception(f"Command '{command1}' failed with return code {result1.returncode}")

#     # run second command
#     result2 = subprocess.run(command2, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     if result2.returncode != 0:
#         raise Exception(f"Command '{command2}' failed with return code {result2.returncode}")

#     # print outputs if any
#     if result1.stdout:
#         print("Tippecanoe stdout:", result1.stdout.decode())
#     if result1.stderr:
#         print("Tippecanoe stderr:", result1.stderr.decode())
#     if result2.stdout:
#         print("Tile-join stdout:", result2.stdout.decode())
#     if result2.stderr:
#         print("Tile-join stderr:", result2.stderr.decode())

#     # handle the result
#     add_values_to_VT(mbtilepaths[0], folderid)
#     for i in range(1, len(mbtilepaths)):
#         os.remove(mbtilepaths[i])

#     return result2.returncode

# def tiles_join(geojson_data, folderid, session):
#     try:
#         mbtile_file = get_latest_mbtiles(folderid, session)
#         # Save the .mbtiles file temporarily on the disk
#         with open(mbtile_file.filename, 'wb') as f:
#             f.write(mbtile_file.tile_data)
#         # Save the geojson_data to a .geojson file
#         with open('data.geojson', 'w') as f:
#             json.dump(geojson_data, f)
#         # Use tippecanoe to create a new .mbtiles file from the geojson_data
#         command1 = "tippecanoe -o new.mbtiles -P -z 16 --drop-densest-as-needed data.geojson --force --use-attribute-for-id=location_id"

#         # Use tile-join to merge the new .mbtiles file with the existing one
#         command2 = f"tile-join -o merged.mbtiles {mbtile_file.filename} new.mbtiles"

#         run_tippecanoe_tiles_join(command1, command2, 1, ["./merged.mbtiles", mbtile_file.filename, "./new.mbtiles"])

#     except SQLAlchemyError as e:
#         print(f"Error occurred during query: {str(e)}")
#         return None


def run_tippecanoe(command):
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
        print("Tippecanoe stderr:", result.stderr.decode())

    return result.returncode


def _point_features(network_data):
    """The point half of the tile feature stream, in get_kml_data order. Both
    the full build and the splice MUST build features this way (same shape,
    same relative order) for spliced tiles to byte-match a full rebuild."""
    return [
        {
            "type": "Feature",
            "properties": {
                "location_id": point["location_id"],
                "served": point["served"],
                "address": point["address"],
                "wireless": point["wireless"],
                "lte": point["lte"],
                "network_coverages": point["coveredLocations"],
                "maxDownloadNetwork": point["maxDownloadNetwork"],
                "maxDownloadSpeed": point["maxDownloadSpeed"],
                "bsl": point["bsl"],
                "feature_type": "Point",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [point["longitude"], point["latitude"]],
            },
        }
        for point in network_data
    ]


def _write_ldjson(path, features):
    # Newline-delimited features (not one giant FeatureCollection): orjson is
    # much faster than json for the big point sets, and tippecanoe's -P can
    # only parallelize input parsing on line-delimited input.
    with open(path, "wb") as f:
        for feat in features:
            f.write(orjson.dumps(feat))
            f.write(b"\n")


def create_tiles(geojson_array, folderid, session):
    network_data = get_kml_data(folderid, session)
    if network_data:
        features = _point_features(network_data)
        features.extend(geojson_array)
        uuid_str = str(uuid.uuid4())
        unique_geojson_filename = f"data{uuid_str}.geojson"
        _write_ldjson(unique_geojson_filename, features)

        low_file = f"output{uuid_str}-low.mbtiles"
        high_file = f"output{uuid_str}-high.mbtiles"
        run_tippecanoe(f"tippecanoe -o {low_file} {TIPPECANOE_LOW} {unique_geojson_filename}")
        run_tippecanoe(f"tippecanoe -o {high_file} {TIPPECANOE_HIGH} {unique_geojson_filename}")
        add_values_to_VT(unique_geojson_filename, [low_file, high_file], folderid)


# ---- splice: regenerate only the z9-16 tiles a change touched --------------

SPLICE_MIN_Z = 9
MAX_Z = 16
# tippecanoe renders features up to its --buffer (default 5/256 of a tile)
# beyond a tile's edge; 16/256 of a z9 tile safely covers that overhang at
# every spliced zoom.
TILE_BUFFER_MARGIN = 16 / 256


def _lonlat_to_z9_tile_f(lon, lat):
    n = 2**SPLICE_MIN_Z
    x = (lon + 180) / 360 * n
    r = math.radians(lat)
    y = (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n
    return x, y


def _z9_tile_f_to_lonlat(xf, yf):
    n = 2**SPLICE_MIN_Z
    lon = xf / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yf / n))))
    return lon, lat


def dirty_z9_ranges(bboxes):
    """Snap lon/lat bboxes ([minx, miny, maxx, maxy]) to inclusive z9 XYZ
    tile ranges (x0, x1, y0, y1). Each bbox is expanded by the tile-buffer
    overhang BEFORE snapping: a changed point within buffer distance of a
    region edge is also rendered by the neighboring tile, so that neighbor
    must be regenerated too."""
    n = 2**SPLICE_MIN_Z
    ranges = []
    for minx, miny, maxx, maxy in bboxes:
        x0f, y0f = _lonlat_to_z9_tile_f(minx, maxy)  # NW corner
        x1f, y1f = _lonlat_to_z9_tile_f(maxx, miny)  # SE corner
        ranges.append(
            (
                max(0, math.floor(x0f - TILE_BUFFER_MARGIN)),
                min(n - 1, math.floor(x1f + TILE_BUFFER_MARGIN)),
                max(0, math.floor(y0f - TILE_BUFFER_MARGIN)),
                min(n - 1, math.floor(y1f + TILE_BUFFER_MARGIN)),
            )
        )
    return ranges


def _selection_box(rng):
    """The lon/lat box of features a splice run needs for this region: the
    region itself plus the buffer margin, so region-edge tiles get their full
    buffer content."""
    x0, x1, y0, y1 = rng
    minx, maxy = _z9_tile_f_to_lonlat(x0 - TILE_BUFFER_MARGIN, y0 - TILE_BUFFER_MARGIN)
    maxx, miny = _z9_tile_f_to_lonlat(x1 + 1 + TILE_BUFFER_MARGIN, y1 + 1 + TILE_BUFFER_MARGIN)
    return minx, miny, maxx, maxy


def _in_ranges(z, x, y_xyz, ranges):
    """Is the (XYZ) tile inside any dirty z9 range (by z9 ancestor)?"""
    k = z - SPLICE_MIN_Z
    ax, ay = x >> k, y_xyz >> k
    return any(x0 <= ax <= x1 and y0 <= ay <= y1 for x0, x1, y0, y1 in ranges)


def folder_coverage_features(folderid, session):
    """Every coverage file's line/polygon features, in deterministic file
    order — the geometry half of the tile feature stream."""
    from .file_ops import get_files_with_postfix

    features = []
    for kml_f in get_files_with_postfix(folderid, ".kml", session):
        features.extend(read_kml(kml_f.id, session))
    for geojson_f in get_files_with_postfix(folderid, ".geojson", session):
        features.extend(read_geojson(geojson_f.id, session))
    return features


def splice_tiles(folderid, bboxes, session):
    """Regenerate the z9-16 tiles in the regions the given lon/lat bboxes
    touch and replace those rows INSIDE the folder's current tileset (the
    serving path never changes; z0-8 overview tiles go deliberately stale
    until a settle rebuild). Because z9-16 is built drop-free, the spliced
    tiles are byte-identical to what a full rebuild would produce.

    The splice input is the points inside the region + margin and every
    coverage geometry passed WHOLE — clipping geometries (even with
    tippecanoe's own --clip-bounding-box) perturbs polygon simplification
    inside the region; out-of-region output tiles are simply discarded.

    Returns True on success, False when there's nothing to splice into or
    nothing to draw (callers fall back to a full rebuild)."""
    current = (
        session.query(mbtiles)
        .filter(mbtiles.folder_id == folderid)
        .order_by(desc(mbtiles.timestamp))
        .first()
    )
    if current is None or not bboxes:
        return False
    network_data = get_kml_data(folderid, session)
    if not network_data:
        return False

    ranges = dirty_z9_ranges(bboxes)
    boxes = [_selection_box(r) for r in ranges]
    points = [
        f
        for f in _point_features(network_data)
        if any(
            minx <= f["geometry"]["coordinates"][0] <= maxx
            and miny <= f["geometry"]["coordinates"][1] <= maxy
            for minx, miny, maxx, maxy in boxes
        )
    ]
    features = points + folder_coverage_features(folderid, session)

    uuid_str = str(uuid.uuid4())
    src = f"splice{uuid_str}.geojson"
    out = f"splice{uuid_str}.mbtiles"
    _write_ldjson(src, features)
    try:
        run_tippecanoe(f"tippecanoe -o {out} {TIPPECANOE_HIGH} {src}")
        with sqlite3.connect(out) as mb_conn:
            rows = mb_conn.execute(
                "SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles"
            ).fetchall()
    finally:
        for path in (src, out):
            if os.path.exists(path):
                os.remove(path)

    new_tiles = [
        (z, x, y_tms, Binary(bytes(data)), current.id)
        for z, x, y_tms, data in rows
        if _in_ranges(z, x, (2**z - 1) - y_tms, ranges)
    ]

    # Delete-then-insert the region's rows in ONE transaction, so a viewer
    # never sees the region empty mid-splice.
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        for z in range(SPLICE_MIN_Z, MAX_Z + 1):
            k = z - SPLICE_MIN_Z
            n = 2**z
            for x0, x1, y0, y1 in ranges:
                ya, yb = y0 << k, ((y1 + 1) << k) - 1  # XYZ rows
                cur.execute(
                    """
                    DELETE FROM vector_tiles
                    WHERE mbtiles_id = %s AND zoom_level = %s
                      AND tile_column BETWEEN %s AND %s
                      AND tile_row BETWEEN %s AND %s
                    """,
                    (current.id, z, x0 << k, ((x1 + 1) << k) - 1, n - 1 - yb, n - 1 - ya),
                )
        if new_tiles:
            execute_values(
                cur,
                """
                INSERT INTO vector_tiles (zoom_level, tile_column, tile_row, tile_data, mbtiles_id)
                VALUES %s
                """,
                new_tiles,
            )
        conn.commit()
    except Exception as e:
        print(f"Splice failed, tiles unchanged: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()
    return True


def retrieve_tiles(zoom, x, y, folderid):
    session = Session()
    try:
        tile = (
            session.query(vector_tiles.tile_data)
            .join(mbtiles, vector_tiles.mbtiles_id == mbtiles.id)
            .filter(
                vector_tiles.zoom_level == int(zoom),
                vector_tiles.tile_column == int(x),
                vector_tiles.tile_row == int(y),
                mbtiles.folder_id == folderid,
            )
            .order_by(desc(mbtiles.timestamp))
            .first()
        )

        return tile
    finally:
        session.close()
