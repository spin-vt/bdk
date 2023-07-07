from database.models import kml_data, Data
from sqlalchemy.exc import IntegrityError
from utils.settings import BATCH_SIZE, DATABASE_URL
from multiprocessing import Lock
from database.sessions import ScopedSession, Session
import logging
import psycopg2
import pandas
import geopandas
import shapely
from shapely.geometry import Point
import fiona
from utils.settings import DATABASE_URL


db_lock = Lock()

def get_wired_data(): 
    session = ScopedSession() 

    try:
        # Define a relationship between kml_data and fabricUpload.Data
        results = session.query(
            kml_data.location_id, 
            kml_data.served, 
            Data.latitude, 
            Data.address_primary, 
            Data.longitude,
            kml_data.wireless,
            kml_data.lte,
            kml_data.username,
            kml_data.coveredLocations,
            kml_data.maxDownloadNetwork,
            kml_data.maxDownloadSpeed
        ).join(
            Data,
            kml_data.location_id == Data.location_id
        ).all()

        data = [{'location_id': r[0],
                'served': r[1],
                'latitude': r[2],
                'address': r[3],
                'longitude': r[4],
                'wireless': r[5],
                'lte': r[6],
                'username': r[7],
                'coveredLocations' : r[8],
                'maxDownloadNetwork': r[9],
                'maxDownloadSpeed': r[10]} for r in results]
    finally:
        session.close()

    return data

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

    print("did fabric in coverage")
    if not flag: 
        session = Session()
        batch = [] 
        not_served_fabric = fabric[~fabric['location_id'].isin(pandaDF['location_id'])]
        not_served_fabric = not_served_fabric.drop_duplicates()

        # Prepare a list of dictionaries to insert to the kml_data table
        rows_to_insert = [{
            'location_id': int(row.location_id),
            'served': False,
            'wireless': False,
            'lte': False,
            'username': "vineet",
            'coveredLocations': "",
            'maxDownloadNetwork': -1,
            'maxDownloadSpeed': -1
        } for _, row in not_served_fabric.iterrows()]

        # Use chunks if rows_to_insert is very large
        chunks = [rows_to_insert[i:i + BATCH_SIZE] for i in range(0, len(rows_to_insert), BATCH_SIZE)]

        for chunk in chunks:
            try:
                # Insert the chunk of records into the kml_data table
                session.bulk_insert_mappings(kml_data, chunk)
                session.commit()
            except IntegrityError:
                session.rollback()
                logging.error("IntegrityError occurred while inserting data.")
                return False
            except Exception as e:
                session.rollback()
                logging.error(f"Error occurred while inserting data: {e}")
                return False

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

    conn = psycopg2.connect(DATABASE_URL)
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


