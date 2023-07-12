import os
import psycopg2
import sqlite3
from controllers.database_controller.kml_ops import get_wired_data
import json
import subprocess
from psycopg2.extensions import adapt, register_adapter, AsIs
from psycopg2 import Binary
from psycopg2.extras import execute_values
from fastkml import kml
from utils.settings import DATABASE_URL
from multiprocessing import Lock
from celery import chain 
from datetime import datetime
from database.sessions import ScopedSession
from database.models import vector_tiles, File
from controllers.celery_controller.celery_config import celery
from controllers.celery_controller.celery_tasks import run_tippecanoe, run_tippecanoe_tiles_join

db_lock = Lock()

def recursive_placemarks(folder):
    for feature in folder.features():
        if isinstance(feature, kml.Placemark):
            yield feature
        elif isinstance(feature, kml.Folder):
            yield from recursive_placemarks(feature)


def read_kml(file_name):
# Now you can extract all placemarks from the root KML object
    # geojson_array= []
    session = ScopedSession()
    file_record = session.query(File).filter(File.file_name == file_name).first()

    if not file_record:
        raise ValueError(f"No file found with name {file_name}")
    
    kml_obj = kml.KML()
    doc = file_record.data
    kml_obj.from_string(doc)

    root_feature = list(kml_obj.features())[0]
    geojson_features = []
    for placemark in recursive_placemarks(root_feature):
        # Use the placemark object here
        geojson_feature = {
            "type": "Feature",
            "geometry": placemark.geometry.__geo_interface__,  # This gets the GeoJSON geometry
            "properties": {"feature_type": placemark.geometry.geom_type} # add the geometry type
        }
        geojson_features.append(geojson_feature)

    session.close()
    return geojson_features


def add_values_to_VT(mbtiles_file_path, user_id):
    with sqlite3.connect(mbtiles_file_path) as mb_conn:
        mb_c = mb_conn.cursor()
        mb_c.execute(
            """
            SELECT zoom_level, tile_column, tile_row, tile_data
            FROM tiles
            """
        )

        try:
            # Create a new connection to Postgres
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # Open the .mbtiles file as binary and read the data
            with open(mbtiles_file_path, 'rb') as file:
                mbtiles_data = Binary(file.read())
            
            # Query the count of existing mbtiles for the user
            cur.execute("SELECT COUNT(*) FROM mbt WHERE user_id = %s", (user_id,))
            count = cur.fetchone()[0]

            # Define new filename
            cur.execute('SELECT "username" FROM "user" WHERE id = %s', (user_id,))
            username = cur.fetchone()[0]
            new_filename = f'{username}-{count+1}.mbtiles'

            # Insert the .mbtiles data
            cur.execute("""
                INSERT INTO mbt (tile_data, filename, timestamp, user_id)
                VALUES (%s, %s, %s, %s) RETURNING id
                """, (mbtiles_data, new_filename, datetime.now(), user_id))

            # Get the id of the mbtiles file
            mbt_id = cur.fetchone()[0]

            # Prepare the vector tile data
            data = [(row[0], row[1], row[2], Binary(row[3]), mbt_id) for row in mb_c]

            # Execute values will generate a SQL INSERT query with placeholders for the parameters
            execute_values(cur, """
                INSERT INTO vt (zoom_level, tile_column, tile_row, tile_data, mbt_id) 
                VALUES %s
                """, data)

            # Don't forget to commit the transaction
            conn.commit()

        except Exception as e:
            print(f"Error occurred: {e}")
            return -1

        finally:
            cur.close()
            conn.close()
            os.remove(mbtiles_file_path)
    return 1

# Potential method for recreating mbtiles with pbf in db
def create_mbtiles_from_db(output_path):
    # Connect to the PostgreSQL database
    pg_session = ScopedSession()

    # Connect to the new .mbtiles file
    with sqlite3.connect(output_path) as mb_conn:
        mb_c = mb_conn.cursor()

        # Create the tables
        mb_c.execute(
            """
            CREATE TABLE metadata (
                name TEXT,
                value TEXT
            );
            """
        )

        mb_c.execute(
            """
            CREATE TABLE tiles (
                zoom_level INTEGER,
                tile_column INTEGER,
                tile_row INTEGER,
                tile_data BLOB
            );
            """
        )

        # Query for the vector tile data
        tile_data = pg_session.query(vector_tiles).all()

        # Insert the data into the .mbtiles file
        for row in tile_data:
            mb_c.execute(
                """
                INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data)
                VALUES (?, ?, ?, ?)
                """,
                (row.zoom_level, row.tile_column, row.tile_row, row.tile_data),
            )

        # Commit the changes and close the connection
        mb_conn.commit()

    # Close the PostgreSQL session
    pg_session.close()

def tiles_join(geojson_data, user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Extract the .mbtiles file from the database
    cursor.execute("SELECT tile_data FROM mbt WHERE user_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
    mbtiles_data = cursor.fetchone()[0]

    # Save the .mbtiles file temporarily on the disk
    with open('existing.mbtiles', 'wb') as f:
        f.write(mbtiles_data)

    # Save the geojson_data to a .geojson file
    with open('data.geojson', 'w') as f:
        json.dump(geojson_data, f)
    
    # Use tippecanoe to create a new .mbtiles file from the geojson_data
    command1 = "tippecanoe -o new.mbtiles -z 16 --drop-densest-as-needed data.geojson --force --use-attribute-for-id=location_id"

    # Use tile-join to merge the new .mbtiles file with the existing one
    command2 = "tile-join -o merged.mbtiles existing.mbtiles new.mbtiles"

    # cursor.execute("TRUNCATE TABLE mbt")
    conn.commit()
    cursor.close()
    conn.close()
    # chain tasks
    run_tippecanoe_tiles_join(command1, command2, 1, ["./merged.mbtiles", "./existing.mbtiles", "./new.mbtiles"])()


def create_tiles(geojson_array, user_id):
    # conn = psycopg2.connect(DATABASE_URL)
    # cursor = conn.cursor()
    # cursor.execute('TRUNCATE TABLE vt')
    # conn.commit()
    # conn.close()
    network_data = get_wired_data()
    point_geojson = {
         "type": "FeatureCollection",
         "features": [
             {
                 "type": "Feature",
                 "properties": {
                     "location_id": point['location_id'],
                     "served": point['served'],
                     "address": point['address'],
                     "wireless": point['wireless'],
                     'lte': point['lte'],
                     'username': point['username'],
                     'network_coverages': point['coveredLocations'],
                     'maxDownloadNetwork': point['maxDownloadNetwork'],
                     'maxDownloadSpeed': point['maxDownloadSpeed'],
                     "feature_type": "Point"
                 },
                 "geometry": {
                     "type": "Point",
                     "coordinates": [point['longitude'], point['latitude']]
                 }
             }
             for point in network_data
         ]
     }
    
    # print(geojson_array)
    point_geojson["features"].extend(geojson for geojson in geojson_array)

    with open('data.geojson', 'w') as f:
         json.dump(point_geojson, f)
         
    command = "tippecanoe -o output.mbtiles --base-zoom=7 --maximum-tile-bytes=3000000 -z 16 --drop-densest-as-needed data.geojson --force --use-attribute-for-id=location_id"
    run_tippecanoe(command, user_id, "output.mbtiles") 

def retrieve_tiles(zoom, x, y, username):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # First, get the user ID
    cursor.execute(
        """
        SELECT id
        FROM "user"
        WHERE username = %s
        """, 
        (username,)
    )
    user_id_result = cursor.fetchone()

    # If the user ID is found, continue to the next query
    if user_id_result:
        user_id = user_id_result[0]
    else: 
        return None

    with db_lock:
            cursor.execute(
                """
                SELECT vt.tile_data
                FROM vt
                JOIN mbt ON vt.mbt_id = mbt.id
                WHERE vt.zoom_level = %s AND vt.tile_column = %s AND vt.tile_row = %s AND mbt.user_id = %s
                ORDER BY mbt.timestamp DESC
                """, 
                (int(zoom), int(x), int(y), user_id)
            )
    tile = cursor.fetchone()
    return tile

def toggle_tiles(markers, user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    geojson_data = []

    try:
        with db_lock:
            for marker in markers:
                cursor.execute(
                    """
                    UPDATE "KML"
                    SET "served" = %s
                    WHERE "location_id" = %s
                    """, 
                    (marker['served'], marker['id'],)
                )
                cursor.execute(
                    """
                    SELECT "KML".location_id, 
                           "KML".served, 
                           fabric.latitude, 
                           fabric.address_primary, 
                           fabric.longitude,
                           "KML".wireless,
                           "KML".lte,
                           "KML".username,
                           "KML"."coveredLocations",
                           "KML"."maxDownloadNetwork",
                           "KML"."maxDownloadSpeed" 
                    FROM "KML"
                    JOIN fabric ON "KML".location_id = fabric.location_id
                    WHERE "KML".location_id = %s
                    """, 
                    (marker['id'],)
                )
                row = cursor.fetchone()

                point_geojson = {
                    "type": "Feature",
                    "properties": {
                        "location_id": row[0],
                        "served": row[1],
                        "address": row[3],
                        "wireless": row[5],
                        'lte': row[6],
                        'username': row[7],
                        'network_coverages': row[8],
                        'maxDownloadNetwork': row[9],
                        'maxDownloadSpeed': row[10],
                        "feature_type": "Point"
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row[4], row[2]]  # Please adjust indices based on your column order
                    }
                }

                geojson_data.append(point_geojson)

        conn.commit()

        
        tiles_join(geojson_data, user_id)
        message = 'Markers toggled successfully'
        status_code = 200

    except Exception as e:
        conn.rollback()  # rollback transaction on error
        message = str(e)  # send the error message to client
        status_code = 500

    finally:
        cursor.close()
        conn.close()

    return (message, status_code)

def get_mbt_info():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("SELECT id, filename, timestamp FROM mbt")
    rows = cursor.fetchall()

    if rows is None:
        return None
    mbtiles = [{"id": row[0], "filename": row[1], "timestamp": row[2]} for row in rows]
    return mbtiles