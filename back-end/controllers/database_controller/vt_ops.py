import json
import os
import sqlite3
import subprocess
import uuid
from datetime import datetime
from multiprocessing import Lock

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


def add_values_to_VT(geojson_file_path, mbtiles_file_path, folderid):
    with sqlite3.connect(mbtiles_file_path) as mb_conn:
        mb_c = mb_conn.cursor()
        mb_c.execute(
            """
            SELECT zoom_level, tile_column, tile_row, tile_data
            FROM tiles
            """
        )

        # Create a new connection to Postgres
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        try:
            with open(mbtiles_file_path, "rb") as file:
                mbtiles_data = Binary(file.read())

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
                (mbtiles_data, new_filename, datetime.now(), folderid),
            )

            mbt_id = cur.fetchone()[0]

            data = [(row[0], row[1], row[2], Binary(row[3]), mbt_id) for row in mb_c]

            execute_values(
                cur,
                """
                INSERT INTO vector_tiles (zoom_level, tile_column, tile_row, tile_data, mbtiles_id) 
                VALUES %s
                """,
                data,
            )

            # Commit the transaction
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


def run_tippecanoe(command, folderid, geojsonpath, mbtilepath):
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
        print("Tippecanoe stderr:", result.stderr.decode())

    add_values_to_VT(geojsonpath, mbtilepath, folderid)
    return result.returncode


def create_tiles(geojson_array, folderid, session):
    network_data = get_kml_data(folderid, session)
    if network_data:
        point_geojson = {
            "type": "FeatureCollection",
            "features": [
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
            ],
        }

        # print(geojson_array)
        point_geojson["features"].extend(geojson for geojson in geojson_array)
        uuid_str = str(uuid.uuid4())
        unique_geojson_filename = f"data{uuid_str}.geojson"

        with open(unique_geojson_filename, "w") as f:
            json.dump(point_geojson, f)

        outputFile = f"output{uuid_str}.mbtiles"
        command = f"tippecanoe -o {outputFile} --base-zoom=7 -P --maximum-tile-bytes=3000000 -z 16 --drop-densest-as-needed {unique_geojson_filename} --force --use-attribute-for-id=location_id --layer=data"
        run_tippecanoe(command, folderid, unique_geojson_filename, outputFile)


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
