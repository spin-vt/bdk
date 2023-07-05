import logging
from multiprocessing import Lock
import shapely
import geopandas
import geopandas as gpd
import pandas
from shapely.geometry import Point
from functools import partial
import pyproj
from shapely.ops import transform
import fiona
from sqlalchemy import inspect
import fabricUpload
from sqlalchemy import Column, Integer, Float, Boolean, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
import pandas as pd
from sqlalchemy.exc import IntegrityError
import geopandas as gpd
from datetime import datetime
import psycopg2
import os
from sqlalchemy import DateTime
from sqlalchemy.sql import func
import sqlite3
from sqlalchemy import LargeBinary
import kmlComputation
import json
import subprocess
import csv
from sqlalchemy import create_engine
from io import StringIO
from psycopg2.extensions import adapt, register_adapter, AsIs
from psycopg2 import Binary
from psycopg2.extras import execute_values
from fastkml import kml

logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
db_host = os.getenv('postgres', 'localhost')

Base = declarative_base()
BATCH_SIZE = 50000

class vector_tiles(Base):
    __tablename__ = 'vt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    zoom_level = Column(Integer)  
    tile_column = Column(Integer) 
    tile_row = Column(Integer)
    tile_data = Column(LargeBinary)
    username = Column(String)

class mbtiles(Base):
    __tablename__ = 'mbt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tile_data = Column(LargeBinary)
    
DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
engine = create_engine(DATABASE_URL)

inspector = inspect(engine)
if not inspector.has_table('vt'):
    Base.metadata.create_all(engine)

if not inspector.has_table('mbt'):
    Base.metadata.create_all(engine)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db_lock = Lock()

def recursive_placemarks(folder):
    for feature in folder.features():
        if isinstance(feature, kml.Placemark):
            yield feature
        elif isinstance(feature, kml.Folder):
            yield from recursive_placemarks(feature)


def read_kml(kml_file_path):
# Now you can extract all placemarks from the root KML object
    # geojson_array= []
    kml_obj = kml.KML()
    with open(kml_file_path, 'r') as file:
        doc = file.read()
        kml_obj.from_string(bytes(bytearray(doc, encoding='utf-8')))

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

    return geojson_features


def add_values_to_VT_test(mbtiles_file_path, username):
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
            
            # Prepare the vector tile data
            data = [(row[0], row[1], row[2], Binary(row[3]), username) for row in mb_c]

            # Execute values will generate a SQL INSERT query with placeholders for the parameters
            execute_values(cur, """
                INSERT INTO vt (zoom_level, tile_column, tile_row, tile_data, username) 
                VALUES %s
                """, data)

            # Open the .mbtiles file as binary and read the data
            with open(mbtiles_file_path, 'rb') as file:
                mbtiles_data = Binary(file.read())
            
            # Insert the .mbtiles data
            cur.execute("""
                INSERT INTO mbt (tile_data)
                VALUES (%s)
                """, (mbtiles_data,))

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

def add_values_to_VT(mbtiles_file_path):
    with sqlite3.connect(mbtiles_file_path) as mb_conn:
        mb_c = mb_conn.cursor()
        mb_c.execute(
            """
            SELECT zoom_level, tile_column, tile_row, tile_data
            FROM tiles
            """
        )
        
        pg_session = ScopedSession()

        try:
            for row in mb_c:
                vt = vector_tiles(
                    zoom_level=row[0],
                    tile_column=row[1],
                    tile_row=row[2],
                    tile_data=row[3], 
                )
                pg_session.merge(vt)
            
            with db_lock:
                pg_session.commit()

        except Exception as e:
            print(f"Error occurred: {e}")
            return -1

        finally:
            pg_session.close()
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

def tiles_join(geojson_data):
    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    # Extract the .mbtiles file from the database
    cursor.execute("SELECT tile_data FROM mbt LIMIT 1")
    mbtiles_data = cursor.fetchone()[0]

    # Save the .mbtiles file temporarily on the disk
    with open('existing.mbtiles', 'wb') as f:
        f.write(mbtiles_data)

    # Save the geojson_data to a .geojson file
    with open('data.geojson', 'w') as f:
        json.dump(geojson_data, f)
    
    # Use tippecanoe to create a new .mbtiles file from the geojson_data
    command = "tippecanoe -o new.mbtiles -z 16 --drop-densest-as-needed data.geojson --force --use-attribute-for-id=location_id"
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
         print("Tippecanoe stderr:", result.stderr.decode())


    # Use tile-join to merge the new .mbtiles file with the existing one
    command = "tile-join -o merged.mbtiles existing.mbtiles new.mbtiles"
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)
    if result.stderr:
         print("Tippecanoe stderr:", result.stderr.decode())

    # Delete the existing .mbtiles file from the database
    cursor.execute("TRUNCATE TABLE mbt")
    conn.commit()

    # # Read the merged .mbtiles file into memory
    # with open('merged.mbtiles', 'rb') as f:
    #     merged_mbtiles_data = f.read()

    # # Insert the merged .mbtiles file into the database
    # cursor.execute("INSERT INTO mbt (tile_data) VALUES (%s)", (Binary(merged_mbtiles_data),))

    # conn.commit()
    cursor.close()
    conn.close()

    val = add_values_to_VT_test("./merged.mbtiles")

    # Remove the temporary files
    os.remove('existing.mbtiles')
    os.remove('new.mbtiles')
    os.remove('merged.mbtiles')
    os.remove('data.geojson')

def create_tiles(geojson_array, username):
    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()
    cursor.execute('TRUNCATE TABLE vt')
    conn.commit()
    conn.close()
    network_data = kmlComputation.get_wired_data()
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

    command = "tippecanoe -o output.mbtiles -z 16 --drop-densest-as-needed data.geojson --force --use-attribute-for-id=location_id"
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
         print("Tippecanoe stderr:", result.stderr.decode())
    
    val = add_values_to_VT_test("./output.mbtiles", username)

# if __name__ == "__main__":
#     create_tiles()