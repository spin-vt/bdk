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

import processData
from sqlalchemy import Column, Integer, Float, Boolean, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

Base = declarative_base()

class kml_data(Base):
    __tablename__ = 'kml'
    location_id = Column(Integer, primary_key=True)
    served = Column(Boolean)

DATABASE_URL = 'postgresql://postgres:db123@localhost:5432/postgres'
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)

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
    for _, row in bsl_fabric_near_fiber.iterrows():
        try:
            location_id = int(row.location_id)
            served = True
            add_values_to_db(location_id, served)
        except Exception as e:
            logging.error(f"Error occurred while inserting data: {e}")

    # Set served to False for fabric points not present in fabric_near_fiber
    not_served_fabric = fabric[~fabric['location_id'].isin(bsl_fabric_near_fiber['location_id'])]
    for _, row in not_served_fabric.iterrows():
        try:
            location_id = int(row.location_id)
            served = False
            add_values_to_db(location_id, served)
        except Exception as e:
            logging.error(f"Error occurred while inserting data: {e}")

    

if __name__ == "__main__":
    filter_locations("./FCC_Active_BSL_12312022_ver1.csv", "./Ash Ave Fiber Path.kml")
