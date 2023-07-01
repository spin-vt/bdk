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
    
DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
engine = create_engine(DATABASE_URL)

inspector = inspect(engine)
if not inspector.has_table('vt'):
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


def add_values_to_VT_test(mbtiles_file_path):
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
            
            # Prepare the data
            data = [(row[0], row[1], row[2], Binary(row[3])) for row in mb_c]

            # Execute values will generate a SQL INSERT query with placeholders for the parameters
            execute_values(cur, """
                INSERT INTO vt (zoom_level, tile_column, tile_row, tile_data) 
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

def create_tiles(geojson_array):
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
    
    val = add_values_to_VT_test("./output.mbtiles")

# if __name__ == "__main__":
#     create_tiles()