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

# Register adapter for bytea data type
register_adapter(bytes, psycopg2.Binary)

def add_values_to_VT_test(mbtiles_file_path):
    with sqlite3.connect(mbtiles_file_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles")
        rows = cursor.fetchall()

        # Write to CSV file
        with open('tiles.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header row
            writer.writerow(['zoom_level', 'tile_column', 'tile_row', 'tile_data'])
            
            # Write data rows
            for row in rows:
                # Convert binary data to sqlite3.Binary object
                modified_row = [sqlite3.Binary(value) if isinstance(value, bytes) else value for value in row]
                writer.writerow(modified_row)

    pg_copy_to_table(engine, 'vt', 'tiles.csv')

def pg_copy_to_table(engine, table_name, file_path):
    with open(file_path, 'r') as f:
        conn = engine.raw_connection()
        cursor = conn.cursor()
        cursor.copy_expert(f"COPY {table_name} (zoom_level, tile_column, tile_row, tile_data) FROM STDIN CSV HEADER", f)
        conn.commit()
        cursor.close()
        conn.close()


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
                    username="vineet"
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

def create_tiles():
    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()
    cursor.execute('TRUNCATE TABLE vt')
    conn.commit()
    conn.close()
    network_data = kmlComputation.get_wired_data()
    geojson = {
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
                    'maxDownloadSpeed': point['maxDownloadSpeed']
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [point['longitude'], point['latitude']]
                }
            }
            for point in network_data
        ]
    }

    with open('data.geojson', 'w') as f:
        json.dump(geojson, f)

    command = "tippecanoe -o output.mbtiles -z 16 --drop-densest-as-needed data.geojson --force"
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
        print("Tippecanoe stderr:", result.stderr.decode())
    
    val = add_values_to_VT_test("./output.mbtiles")

# if __name__ == "__main__":
#     create_tiles()