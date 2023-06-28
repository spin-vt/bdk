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

logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
db_host = os.getenv('postgres', 'localhost')

Base = declarative_base()
BATCH_SIZE = 50000

class vector_tiles(Base):
    __tablename__ = 'VT'
    id = Column(Integer, primary_key=True)
    zoom_level = Column(Integer)  
    tile_column = Column(Integer) 
    tile_row = Column(Integer)
    tile_data = Column(LargeBinary)
    username = Column(String)
    date_added = Column(DateTime(timezone=True), server_default=func.now())
    
DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
engine = create_engine(DATABASE_URL)

inspector = inspect(engine)
if not inspector.has_table('VT'):
    Base.metadata.create_all(engine)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db_lock = Lock()

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

if __name__ == "__main__":
    add_values_to_VT("./output.mbtiles")