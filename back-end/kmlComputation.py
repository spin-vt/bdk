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
from sqlalchemy import Column, Integer, Float, Boolean, String, ARRAY, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
import pandas as pd
from sqlalchemy.exc import IntegrityError
import geopandas as gpd
from datetime import datetime
import psycopg2
import os
import json 
import subprocess
import vectorTile

logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
db_host = os.getenv('postgres', 'localhost')

Base = declarative_base()
BATCH_SIZE = 50000

class kml_data(Base):
    __tablename__ = 'KML'
    location_id = Column(Integer, primary_key=True)
    served = Column(Boolean)
    wireless = Column(Boolean)
    lte = Column(Boolean)
    username = Column(String)
    coveredLocations = Column(String)
    maxDownloadNetwork = Column(String)
    maxDownloadSpeed = Column(Integer)

DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
engine = create_engine(DATABASE_URL)

inspector = inspect(engine)
if not inspector.has_table('KML'):
    Base.metadata.create_all(engine)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db_lock = Lock()

def get_wireless_data(): 
    session = ScopedSession()

    results = session.query(kml_data).all()

    location_ids = {r.location_id for r in results}

    results = session.query(fabricUpload.Data).filter(fabricUpload.Data.location_id.in_(location_ids)).all()

    latitudes = {r.location_id: r.latitude for r in results}
    longitudes = {r.location_id: r.longitude for r in results}
    addresses = {r.location_id: r.address_primary for r in results}

    data = [
        {
            'location_id': r.location_id,
            'served': True,
            'latitude': latitudes.get(r.location_id),
            'address': addresses.get(r.location_id),
            'longitude': longitudes.get(r.location_id),
            'type': 'lte' if r.lte in location_ids else 'non-lte'
        } for r in results
    ]

    return data

def get_wired_data():
    session = ScopedSession()

    results = session.query(kml_data).all()

    location_ids = [r.location_id for r in results]

    fabric_results = session.query(fabricUpload.Data).filter(fabricUpload.Data.location_id.in_(location_ids)).all()

    latitudes = {r.location_id: r.latitude for r in fabric_results}
    longitudes = {r.location_id: r.longitude for r in fabric_results}
    addresses = {r.location_id: r.address_primary for r in fabric_results}

    data = [{'location_id': r.location_id,
             'served': r.served,
             'latitude': latitudes.get(r.location_id),
             'address': addresses.get(r.location_id),
             'longitude': longitudes.get(r.location_id),
             'wireless': r.wireless,
            'lte': r.lte,
            'username': r.username,
            'coveredLocations' : r.coveredLocations,
            'maxDownloadNetwork': r.maxDownloadNetwork,
            'maxDownloadSpeed': r.maxDownloadSpeed} for r in results]

    return data

#might need to add lte data in the future
def compute_wireless_locations(Fabric_FN, Coverage_fn, flag, download, upload, tech):
    df = pandas.read_csv(Fabric_FN) 

    fabric = geopandas.GeoDataFrame(
        df.drop(['latitude', 'longitude'], axis=1),
        crs="EPSG:4326",
        geometry=[shapely.geometry.Point(xy) for xy in zip(df.longitude, df.latitude)])
    
    fiona.drvsupport.supported_drivers['kml'] = 'rw'
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    
    wireless_coverage = geopandas.read_file(Coverage_fn)
    wireless_coverage = wireless_coverage.to_crs("EPSG:4326")
    fabric_in_wireless = geopandas.sjoin(fabric,wireless_coverage,how="inner")
    bsl_fabric_in_wireless = fabric_in_wireless[fabric_in_wireless['bsl_flag']]
    bsl_fabric_in_wireless = bsl_fabric_in_wireless.drop_duplicates()

    res = add_to_db(bsl_fabric_in_wireless, Coverage_fn, fabric, flag, download, True)
    return res 

def compute_wired_locations(Fabric_FN, Fiber_FN, flag, download, upload, tech):
    df = pandas.read_csv(Fabric_FN)

    fabric = geopandas.GeoDataFrame(
        df.drop(['latitude', 'longitude'], axis=1),
        crs="EPSG:4326",
        geometry=[shapely.geometry.Point(xy) for xy in zip(df.longitude, df.latitude)])

    fiona.drvsupport.supported_drivers['kml'] = 'rw'
    fiona.drvsupport.supported_drivers['KML'] = 'rw'

    buffer_meters = 100 
    gdf_fiber = geopandas.read_file(Fiber_FN, driver='KML', encoding='utf-8')
    fiber_paths = gdf_fiber[gdf_fiber.geom_type == 'LineString']

    fiber_paths = fiber_paths.to_crs('epsg:4326')

    fiber_paths_buffer = fiber_paths.to_crs("EPSG:5070")
    fiber_paths_buffer['geometry'] = fiber_paths_buffer.buffer(buffer_meters)
    fiber_paths_buffer = fiber_paths_buffer.to_crs("EPSG:4326")

    fabric_near_fiber = geopandas.sjoin(fabric, fiber_paths_buffer, how="inner")

    bsl_fabric_near_fiber = fabric_near_fiber[fabric_near_fiber['bsl_flag']] 

    bsl_fabric_near_fiber = bsl_fabric_near_fiber.drop_duplicates() 
    res = add_to_db(bsl_fabric_near_fiber, Fiber_FN, fabric, flag, download, False)
    return res 

def add_network_data(Fabric_FN, Fiber_FN, flag, download, upload, tech, type):
    res = False 
    if type == 0: 
        res = compute_wired_locations(Fabric_FN, Fiber_FN, flag, download, upload, tech)
    elif type == 1: 
        res = compute_wireless_locations(Fabric_FN, Fiber_FN, flag, download, upload, tech)
    return res 

def add_to_db(pandaDF, networkName, fabric, flag, download, wireless):
    batch = [] 
    session = Session()
    for _, row in pandaDF.iterrows():
        try:
            if row.location_id == '': 
                continue

            existing_data = session.query(kml_data).filter_by(location_id=int(row.location_id)).first()

            if download == "": 
                download = 0
                
            if existing_data is None:  # If the location_id doesn't exist in db
                newData = kml_data(
                    location_id = int(row.location_id),
                    served = True,
                    wireless = wireless,
                    lte = False,
                    username = "vineet",
                    coveredLocations = networkName,
                    maxDownloadNetwork = networkName,
                    maxDownloadSpeed = int(download)
                )
                batch.append(newData)
            else:  # If the location_id exists
                existing_data.served = True
                existing_data.wireless = wireless

                if existing_data.coveredLocations == "": 
                    existing_data.coveredLocations = networkName
                else:
                    covered_locations_list = existing_data.coveredLocations.split(', ')
                    if networkName not in covered_locations_list:
                        covered_locations_list.append(networkName)
                        existing_data.coveredLocations = ", ".join(covered_locations_list)

                if int(download) > int(existing_data.maxDownloadSpeed): 
                    existing_data.maxDownloadNetwork = networkName
                    existing_data.maxDownloadSpeed = int(download)

            if len(batch) >= BATCH_SIZE:
                with db_lock:
                    try:
                        session.bulk_save_objects(batch)
                        session.commit()
                    except IntegrityError:
                        session.rollback()
                
                batch = []
        except Exception as e:
            logging.error(f"Error occurred while inserting data: {e}")
            return False 

    if batch:
        with db_lock:
            try:
                session.bulk_save_objects(batch)
                session.commit()
            except IntegrityError:
                session.rollback() 
    session.commit()
    session.close()

    if not flag: 
        session = Session()
        batch = [] 
        not_served_fabric = fabric[~fabric['location_id'].isin(pandaDF['location_id'])]
        not_served_fabric = not_served_fabric.drop_duplicates()
        for _, row in not_served_fabric.iterrows():
            try:
                newData = kml_data(
                    location_id = int(row.location_id),
                    served = False,
                    wireless = False,
                    lte = False,
                    username = "vineet",
                    coveredLocations = "",
                    maxDownloadNetwork = -1,
                    maxDownloadSpeed = -1
                )
                
                batch.append(newData)
                if len(batch) >= BATCH_SIZE:
                    with db_lock:
                        try:
                            session.bulk_save_objects(batch)
                            session.commit()
                        except IntegrityError:
                            session.rollback()  
                    batch = []
            except Exception as e:
                logging.error(f"Error occurred while inserting data: {e}")
                return False 
                
        if batch:
            with db_lock:
                try:
                    session.bulk_save_objects(batch)
                    session.commit()
                except IntegrityError:
                    session.rollback()  
        session.close()
    return True 

def export(download_speed, upload_speed, tech_type): 
    PROVIDER_ID = 000 
    BRAND_NAME = 'Test' 

    TECHNOLOGY_CODE = tech_type
    MAX_DOWNLOAD_SPEED = download_speed
    MAX_UPLOAD_SPEED = upload_speed

    LATENCY = 0 
    BUSINESS_CODE = 0

    availability_csv = pandas.DataFrame()

    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    cursor.execute('SELECT location_id FROM "KML" WHERE served = true')
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    availability_csv['location_id'] = [row[0] for row in result]
    availability_csv['provider_id'] = PROVIDER_ID
    availability_csv['brand_name'] = BRAND_NAME
    availability_csv['technology'] = TECHNOLOGY_CODE
    availability_csv['max_advertised_download_speed'] = MAX_DOWNLOAD_SPEED
    availability_csv['max_advertised_upload_speed'] = MAX_UPLOAD_SPEED
    availability_csv['low_latency'] = LATENCY
    availability_csv['business_residential_code'] = BUSINESS_CODE

    availability_csv = availability_csv[['provider_id', 'brand_name', 'location_id', 'technology', 'max_advertised_download_speed', 
                                        'max_advertised_upload_speed', 'low_latency', 'business_residential_code']] 

    filename = 'FCC_broadband.csv'
    availability_csv.to_csv(filename, index=False)
    return filename

# if __name__ == "__main__":
#     compute_wireless_locations("FCC_Active_BSL_12312022_ver1.csv", "filled_full_poly.kml", True, 100, 50, "temp")