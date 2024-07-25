import os
import psycopg2
import sqlite3
from controllers.database_controller.kml_ops import get_kml_data, generate_csv_data
import json
import subprocess
import geopandas
from shapely.geometry import shape
from io import StringIO
from psycopg2.extensions import adapt, register_adapter, AsIs
from psycopg2 import Binary
from psycopg2.extras import execute_values
from fastkml import kml
from utils.settings import DATABASE_URL
from multiprocessing import Lock
from celery import chain 
from datetime import datetime
from database.sessions import ScopedSession, Session
from database.models import vector_tiles, file, folder, kml_data, fabric_data, mbtiles
from controllers.celery_controller.celery_config import celery
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc
from .file_ops import get_files_by_type, get_file_with_id, get_files_with_postfix, create_file, update_file_type, get_files_with_prefix, get_file_with_name
from .folder_ops import get_upload_folder, get_export_folder, get_folder_with_id
from .mbtiles_ops import get_latest_mbtiles, delete_mbtiles, get_mbtiles_with_id
from .user_ops import get_user_with_id
from utils.namingschemes import DATETIME_FORMAT, EXPORT_CSV_NAME_TEMPLATE
from utils.logger_config import logger
import uuid


db_lock = Lock()

def extract_geometry(placemark):
    geometries = []
    geometries.append(placemark.geometry.__geo_interface__)
    return geometries

def recursive_placemarks(folder):
    for feature in folder.features():
        if isinstance(feature, kml.Placemark):
            yield feature
        elif isinstance(feature, kml.Folder):
            yield from recursive_placemarks(feature)

def read_kml(fileid, session):
    file_record = get_file_with_id(fileid, session)

    if not file_record:
        raise ValueError(f"No file found with ID {fileid}")
    
    kml_obj = kml.KML()
    doc = file_record.data
    kml_obj.from_string(doc)


    root_feature = list(kml_obj.features())[0]
    geojson_features = []
    for placemark in recursive_placemarks(root_feature):
        geometries = extract_geometry(placemark)
        for geometry in geometries:
            geom_type = geometry['type']
            if geom_type == 'Point':
                continue
            geojson_feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "feature_type": geom_type,
                    "network_coverages": file_record.name
                }  # No properties extracted
            }
            geojson_features.append(geojson_feature)
            
    return geojson_features


def read_geojson(fileid, session):
    file_record = get_file_with_id(fileid, session)

    if not file_record:
        raise ValueError(f"No file found with name {file_record.name}")

    # Read the GeoJSON data using GeoPandas
    geojson_data = geopandas.read_file(StringIO(file_record.data.decode()))

    # Filter only polygons and linestrings
    desired_geometries = geojson_data[geojson_data.geometry.geom_type.isin(['Polygon', 'LineString', 'MultiPolygon'])]

    # Convert the GeoDataFrame with desired geometries to a similar format as in read_kml
    geojson_features = []
    for _, row in desired_geometries.iterrows():
        geojson_feature = {
            "type": "Feature",
            "geometry": shape(row['geometry']).__geo_interface__,
            "properties": {
                "feature_type": row['geometry'].geom_type,
                'network_coverages': file_record.name,
            }
        }
        geojson_features.append(geojson_feature)

    return geojson_features



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
            with open(mbtiles_file_path, 'rb') as file:
                mbtiles_data = Binary(file.read())
            
            cur.execute("SELECT COUNT(*) FROM mbtiles WHERE folder_id = %s", (folderid,))
            count = cur.fetchone()[0]
            cur.execute('SELECT "name" FROM "folder" WHERE id = %s', (folderid,))
            foldername = cur.fetchone()[0]
            new_filename = f'{foldername}-{count+1}.mbtiles'

            cur.execute("""
                INSERT INTO mbtiles (tile_data, filename, timestamp, folder_id)
                VALUES (%s, %s, %s, %s) RETURNING id
                """, (mbtiles_data, new_filename, datetime.now(), folderid))

            mbt_id = cur.fetchone()[0]

            data = [(row[0], row[1], row[2], Binary(row[3]), mbt_id) for row in mb_c]

            execute_values(cur, """
                INSERT INTO vector_tiles (zoom_level, tile_column, tile_row, tile_data, mbtiles_id) 
                VALUES %s
                """, data)

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
                        "location_id": point['location_id'],
                        "served": point['served'],
                        "address": point['address'],
                        "wireless": point['wireless'],
                        'lte': point['lte'],
                        'network_coverages': point['coveredLocations'],
                        'maxDownloadNetwork': point['maxDownloadNetwork'],
                        'maxDownloadSpeed': point['maxDownloadSpeed'],
                        'bsl': point['bsl'],
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
        uuid_str = str(uuid.uuid4())
        unique_geojson_filename = f"data{uuid_str}.geojson"

        with open(unique_geojson_filename, 'w') as f:
            json.dump(point_geojson, f)
        
        outputFile = f"output{uuid_str}.mbtiles"
        command = f"tippecanoe -o {outputFile} --base-zoom=7 -P --maximum-tile-bytes=3000000 -z 16 --drop-densest-as-needed {unique_geojson_filename} --force --use-attribute-for-id=location_id --layer=data"
        run_tippecanoe(command, folderid, unique_geojson_filename, outputFile)

def retrieve_tiles(zoom, x, y, folderid):
    session = Session()
    try:
       
        tile = session.query(vector_tiles.tile_data).join(mbtiles, vector_tiles.mbtiles_id == mbtiles.id).filter(
            vector_tiles.zoom_level == int(zoom),
            vector_tiles.tile_column == int(x),
            vector_tiles.tile_row == int(y),
            mbtiles.folder_id == folderid
        ).order_by(desc(mbtiles.timestamp)).first()
       

        return tile
    finally:
        session.close()
 
