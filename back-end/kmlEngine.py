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
import processData
from sqlalchemy import Column, Integer, Float, Boolean, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
import pandas as pd
from sqlalchemy.exc import IntegrityError
import geopandas as gpd
from datetime import datetime
import psycopg2
import os

logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
db_host = os.getenv('DB_HOST', 'localhost')

Base = declarative_base()
BATCH_SIZE = 50000

class kml_data(Base):
    __tablename__ = 'kml'
    location_id = Column(Integer, primary_key=True)
    served = Column(Boolean)

class wireless(Base):
    __tablename__ = 'lte'
    location_id = Column(Integer, primary_key=True)

class wireless2(Base):
    __tablename__ = 'non-lte'
    location_id = Column(Integer, primary_key=True)

DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
engine = create_engine(DATABASE_URL)

# Check if the table exists
inspector = inspect(engine)
if not inspector.has_table('kml'):
    Base.metadata.create_all(engine)

inspector = inspect(engine)
if not inspector.has_table('lte'):
    Base.metadata.create_all(engine)

inspector = inspect(engine)
if not inspector.has_table('non-lte'):
    Base.metadata.create_all(engine)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db_lock = Lock()


def add_values_to_db(location_id, served):
    session = ScopedSession()
    try:
        new_data = kml_data(location_id=location_id, served=served)
        session.merge(new_data)
        with db_lock:
            session.commit()
        session.remove()

    except Exception as e:
        return -1

    return 1

def check_num_records_greater_zero():
    session = ScopedSession()
    return session.query(kml_data).count() > 0

def get_precise_wireless_data(): 
    session = ScopedSession()

    results = session.query(wireless).all()
    # Get location IDs from kml_data
    location_ids = [r.location_id for r in results]

    # Query bdk_data using location IDs to get latitudes and longitudes
    lte_results = session.query(processData.Data).filter(processData.Data.location_id.in_(location_ids)).all()

    # Map location IDs to latitudes and longitudes
    latitudes = {r.location_id: r.latitude for r in lte_results}
    longitudes = {r.location_id: r.longitude for r in lte_results}
    addresses = {r.location_id: r.address_primary for r in lte_results}

    data = [{'location_id': r.location_id,
             'served': True,
             'latitude': latitudes.get(r.location_id),
             'address': addresses.get(r.location_id),
             'longitude': longitudes.get(r.location_id)} for r in results]

    return data

def get_precise_data():
    session = ScopedSession()

    results = session.query(kml_data).all()

    # Get location IDs from kml_data
    location_ids = [r.location_id for r in results]

    # Query bdk_data using location IDs to get latitudes and longitudes
    bdk_results = session.query(processData.Data).filter(processData.Data.location_id.in_(location_ids)).all()

    # Map location IDs to latitudes and longitudes
    latitudes = {r.location_id: r.latitude for r in bdk_results}
    longitudes = {r.location_id: r.longitude for r in bdk_results}
    addresses = {r.location_id: r.address_primary for r in bdk_results}

    # Combine kml_data and bdk_data to create data dictionary
    data = [{'location_id': r.location_id,
             'served': r.served,
             'latitude': latitudes.get(r.location_id),
             'address': addresses.get(r.location_id),
             'longitude': longitudes.get(r.location_id)} for r in results]

    return data

def check_mismatches():
    with db_lock:
        with ScopedSession() as session:
            table1_ids = set([row[0] for row in session.query(kml_data.location_id)])
            table2_ids = set([row[0] for row in session.query(processData.Data.location_id)])
            mismatched_ids = table1_ids.symmetric_difference(table2_ids)
            for id in mismatched_ids:
                record1 = session.query(kml_data).filter_by(location_id=id).first()
                record2 = session.query(processData.Data).filter_by(location_id=id).first()
                if record1 and not record2:
                    new_record = processData.Data(location_id=id, served=False)
                    session.add(new_record)
                elif not record1 and record2:
                    new_record = kml_data(location_id=id, served=False)
                    session.add(new_record)
            session.commit()

def wired_locations(fabric_fn, coverage_fn, lte_fn):
    df = pandas.read_csv(fabric_fn) ##Changed fabric (v2)

    fabric = geopandas.GeoDataFrame(
        df.drop(['latitude', 'longitude'], axis=1),
        crs="EPSG:4326",
        geometry=[shapely.geometry.Point(xy) for xy in zip(df.longitude, df.latitude)])
    
    # Enable KML support
    fiona.drvsupport.supported_drivers['kml'] = 'rw'
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    
    wireless_coverage = geopandas.read_file(coverage_fn)
    wireless_coverage = wireless_coverage.to_crs("EPSG:4326")
    fabric_in_wireless = geopandas.sjoin(fabric,wireless_coverage,how="inner")

    # filter for only data where bsl_flag is true
    bsl_fabric_in_wireless = fabric_in_wireless[fabric_in_wireless['bsl_flag']]
    bsl_fabric_in_wireless = bsl_fabric_in_wireless.drop_duplicates()

    print(len(fabric_in_wireless), len(bsl_fabric_in_wireless))

    # Create a dataset for 2.5GHz tower points

    # first, load in the 2.5GHz tower approximation that Wesley drew
    lte_coverage = geopandas.read_file(lte_fn)

    lte_fabric = gpd.GeoDataFrame()  # Initialize an empty GeoDataFrame

    # next, get all points within this coverage
    lte_fabric = bsl_fabric_in_wireless[bsl_fabric_in_wireless.geometry.within(lte_coverage['geometry'][0])]

    nonlte_fabric = bsl_fabric_in_wireless[~bsl_fabric_in_wireless.geometry.within(lte_coverage['geometry'][0])]

    #need to double check the accuracy
    for i in range(1, len(lte_coverage)):
        # on each iteration, only keep the points within
        lte_fabric = pd.concat([lte_fabric, bsl_fabric_in_wireless[bsl_fabric_in_wireless.geometry.within(lte_coverage['geometry'][i])]])
        # on each iteration, only keep the points not inside each polygon
        nonlte_fabric = nonlte_fabric[~nonlte_fabric.geometry.within(lte_coverage['geometry'][i])]

    # convert lte_fabric back to a GeoDataFrame
    lte_fabric = gpd.GeoDataFrame(lte_fabric, crs="EPSG:4326")

    # remove duplicate rows from both
    lte_fabric = lte_fabric.drop_duplicates()
    nonlte_fabric = nonlte_fabric.drop_duplicates()

    print(len(lte_fabric), len(nonlte_fabric))

    session = Session()
    batch = [] 
    for _, row in lte_fabric.iterrows():
        try:
            newData = wireless(
                location_id = int(row.location_id),
            )
            
            batch.append(newData)
            if len(batch) >= BATCH_SIZE:
                with db_lock:
                    try:
                        session.bulk_save_objects(batch)
                        session.commit()
                    except IntegrityError:
                        session.rollback()  # Rollback the transaction on unique constraint violation
                batch = []

        except Exception as e:
            logging.error(f"Error occurred while inserting data: {e}")
            
    if batch:
        with db_lock:
            try:
                session.bulk_save_objects(batch)
                session.commit()
            except IntegrityError:
                session.rollback()  # Rollback the transaction on unique constraint violation
    session.close()
    
    session = Session()
    batch = [] 

    for _, row in nonlte_fabric.iterrows():
        try:
            newData = wireless2(
                location_id = int(row.location_id),
            )
            
            batch.append(newData)
            if len(batch) >= BATCH_SIZE:
                with db_lock:
                    try:
                        session.bulk_save_objects(batch)
                        session.commit()
                    except IntegrityError:
                        session.rollback()  # Rollback the transaction on unique constraint violation
                batch = []
        except Exception as e:
            logging.error(f"Error occurred while inserting data: {e}")
            
    if batch:
        with db_lock:
            try:
                session.bulk_save_objects(batch)
                session.commit()
            except IntegrityError:
                session.rollback()  # Rollback the transaction on unique constraint violation
    session.close()

        
def filter_locations(Fabric_FN, Fiber_FN):

    df = pandas.read_csv(Fabric_FN) ##Changed fabric (v2)

    fabric = geopandas.GeoDataFrame(
        df.drop(['latitude', 'longitude'], axis=1),
        crs="EPSG:4326",
        geometry=[shapely.geometry.Point(xy) for xy in zip(df.longitude, df.latitude)])

    # Enable KML support
    fiona.drvsupport.supported_drivers['kml'] = 'rw'
    fiona.drvsupport.supported_drivers['KML'] = 'rw'

    buffer_meters = 100  # meters
    gdf_fiber = geopandas.read_file(Fiber_FN, driver='KML', encoding='utf-8')
    fiber_paths = gdf_fiber[gdf_fiber.geom_type == 'LineString']

    fiber_paths = fiber_paths.to_crs('epsg:4326')

    # Project the fiber map to build a buffer object for a spatial join
    fiber_paths_buffer = fiber_paths.to_crs("EPSG:5070")
    fiber_paths_buffer['geometry'] = fiber_paths_buffer.buffer(buffer_meters)
    fiber_paths_buffer = fiber_paths_buffer.to_crs("EPSG:4326")

    # Now, get points within the buffer and plot
    fabric_near_fiber = geopandas.sjoin(fabric, fiber_paths_buffer, how="inner")

    # Filter out any rows where bsl_flag is False
    bsl_fabric_near_fiber = fabric_near_fiber[fabric_near_fiber['bsl_flag']] #keep if bsl_flag is true

    # Drop any duplicate rows
    bsl_fabric_near_fiber = bsl_fabric_near_fiber.drop_duplicates()
    # Set served to True for fabric points present in fabric_near_fiber
    batch = [] 
    session = Session()
    for _, row in bsl_fabric_near_fiber.iterrows():
        try:
            newData = kml_data(
                location_id = int(row.location_id),
                served = True
            )
            
            batch.append(newData)

            if len(batch) >= BATCH_SIZE:
                with db_lock:
                    try:
                        session.bulk_save_objects(batch)
                        session.commit()
                    except IntegrityError:
                        session.rollback()  # Rollback the transaction on unique constraint violation
                
                batch = []
            # add_values_to_db(location_id, served)
        except Exception as e:
            logging.error(f"Error occurred while inserting data: {e}")

    if batch:
        with db_lock:
            try:
                session.bulk_save_objects(batch)
                session.commit()
            except IntegrityError:
                session.rollback()  # Rollback the transaction on unique constraint violation
    session.close()

    session = Session()
    batch = [] 
    # Set served to False for fabric points not present in fabric_near_fiber
    not_served_fabric = fabric[~fabric['location_id'].isin(bsl_fabric_near_fiber['location_id'])]
    not_served_fabric = not_served_fabric.drop_duplicates()
    for _, row in not_served_fabric.iterrows():
        try:
            newData = kml_data(
                location_id = int(row.location_id),
                served = False
            )
            
            batch.append(newData)
            if len(batch) >= BATCH_SIZE:
                with db_lock:
                    try:
                        session.bulk_save_objects(batch)
                        session.commit()
                    except IntegrityError:
                        session.rollback()  # Rollback the transaction on unique constraint violation
                batch = []
            # add_values_to_db(location_id, served)
        except Exception as e:
            logging.error(f"Error occurred while inserting data: {e}")
            
    if batch:
        with db_lock:
            try:
                session.bulk_save_objects(batch)
                session.commit()
            except IntegrityError:
                session.rollback()  # Rollback the transaction on unique constraint violation
    session.close()

def exportWired(): 
    PROVIDER_ID = 777
    BRAND_NAME = 'Test'
    TECHNOLOGY_CODE = 1
    MAX_DOWNLOAD_SPEED = 1
    MAX_UPLOAD_SPEED = 1
    LATENCY = 1
    BUSINESS_CODE = 'X'

    availability_csv = pandas.DataFrame()

    # Establish PostgreSQL connection
    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    # Retrieve location_id from PostgreSQL table 'kml'
    cursor.execute("SELECT location_id FROM kml WHERE served = true")
    result = cursor.fetchall()

    # Close cursor and connection
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

    print(len(availability_csv))

    filename = 'wiredCSV.csv'
    availability_csv.to_csv(filename, index=False)
    return filename

def exportWireless(): 
    PROVIDER_ID = 777
    BRAND_NAME = 'Test'
    TECHNOLOGY_CODE = 1
    MAX_DOWNLOAD_SPEED = 1
    MAX_UPLOAD_SPEED = 1
    LATENCY = 1
    BUSINESS_CODE = 'X'

    availability_csv = pandas.DataFrame()

    # Establish PostgreSQL connection
    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    # Retrieve location_id from PostgreSQL table 'kml'
    cursor.execute("SELECT location_id FROM lte")
    result = cursor.fetchall()

    # Close cursor and connection
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

    print(len(availability_csv))

    filename = 'wirelessCSV.csv'
    availability_csv.to_csv(filename, index=False)
    return filename

# if __name__ == "__main__":
# #     exportWired()
# #     filter_locations("./FCC_Active_BSL_12312022_ver1.csv", "./Ash Ave Fiber Path.kml")
#     wired_locations("./FCC_Active_BSL_12312022_ver1.csv", "./filled_full_poly.kml", "./25GHz_coverage.geojson")
