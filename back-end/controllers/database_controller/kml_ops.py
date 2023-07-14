from database.models import kml_data, fabric_data, file, user
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
from io import StringIO, BytesIO

db_lock = Lock()

def get_kml_data(userid, folderid): 
    session = ScopedSession() 
    userVal = session.query(user).filter(user.id == userid).one()

    try:
        # Query the File records related to the folder_id
        fabric_file = session.query(file).filter(file.folder_id == folderid, file.name.endswith('.csv')).first()
        kml_files = session.query(file).filter(file.folder_id == folderid, file.name.endswith('.kml')).all()

        if not fabric_file or not kml_files:
            raise FileNotFoundError("Either fabric or KML files not found")

        # Query all locations in fabric_data
        all_locations = session.query(
            fabric_data.location_id,
            fabric_data.latitude, 
            fabric_data.address_primary,
            fabric_data.longitude
        ).filter(fabric_data.file_id == fabric_file.id).all()  # Change to fabric_file.id

        # Initialize an empty dictionary to hold location_id as key and its data as value, including location_id itself
        all_data = {r[0]: {'location_id': r[0], 'latitude': r[1], 'address': r[2], 'longitude': r[3]} for r in all_locations}

        default_data = {
            'served': False,
            'wireless': False,
            'lte': False,
            'username': userVal.username,
            'coveredLocations': "",
            'maxDownloadNetwork': -1,
            'maxDownloadSpeed': -1
        }

        for kml_file in kml_files:
            # Query all locations that are served
            resultsServed = session.query(
                kml_data.location_id, 
                kml_data.served, 
                kml_data.wireless,
                kml_data.lte,
                kml_data.username,
                kml_data.coveredLocations,
                kml_data.maxDownloadNetwork,
                kml_data.maxDownloadSpeed
            ).filter(
                kml_data.file_id == kml_file.id  # Change to kml_file.id
            ).all()


            # Add served data to the respective location in all_data, merge two file that served the same point,
            # record the maxdownloadnetwork and maxuploadspeed
            for r in resultsServed:
                if r[0] in all_data:
                    all_data[r[0]].update({
                        'served': r[1],
                        'wireless': r[2],
                        'lte': r[3],
                        'username': r[4],
                        'coveredLocations': r[5],
                        'maxDownloadNetwork': r[6],
                        'maxDownloadSpeed': r[7]
                    })
                else:
                    # The location was not in the fabric file, but it is in one of the KML files
                    # You need to decide how to handle this situation.
                    pass

            # For all other locations, fill with default values
            for loc in all_data.values():
                for key, value in default_data.items():
                    loc.setdefault(key, value)

        # Convert dictionary values to a list
        data = list(all_data.values())

    finally:
        session.close()

    return data

def add_to_db(pandaDF, kmlid, download, upload, tech, wireless, userid):
    batch = [] 
    session = Session()

    userVal = session.query(user).filter(user.id == userid).one()
    fileVal = session.query(file).filter(file.id == kmlid).one()

    for _, row in pandaDF.iterrows():
        try:
            if row.location_id == '': 
                continue

            existing_data = session.query(kml_data).filter(kml_data.location_id==int(row.location_id)).first()

            if download == "": 
                download = 0
                
            if existing_data is None:  # If the location_id doesn't exist in db
                newData = kml_data(
                    location_id = int(row.location_id),
                    served = True,
                    wireless = wireless,
                    lte = False,
                    username = userVal.username,
                    coveredLocations = fileVal.name,
                    maxDownloadNetwork = fileVal.name,
                    maxDownloadSpeed = int(download), 
                    maxUploadSpeed = int(upload), 
                    techType = tech,
                    file_id = fileVal.id
                )
                batch.append(newData)
            else:  # If the location_id exists
                existing_data.served = True
                existing_data.wireless = wireless

                if existing_data.coveredLocations == "": 
                    existing_data.coveredLocations = fileVal.name
                else:
                    covered_locations_list = existing_data.coveredLocations.split(', ')
                    if fileVal.name not in covered_locations_list:
                        covered_locations_list.append(fileVal.name)
                        existing_data.coveredLocations = ", ".join(covered_locations_list)

                if int(download) > int(existing_data.maxDownloadSpeed): 
                    existing_data.maxDownloadNetwork = fileVal.name
                    existing_data.maxDownloadSpeed = int(download)
                if int(upload) > int(existing_data.maxUploadSpeed): 
                    existing_data.maxUploadSpeed = int(upload)

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

    return True 

def export(): 
    PROVIDER_ID = 000 
    BRAND_NAME = 'Test' 
    LATENCY = 0 
    BUSINESS_CODE = 0

    availability_csv = pandas.DataFrame()

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute('SELECT location_id, "maxDownloadSpeed", "maxUploadSpeed", "techType" FROM "KML" WHERE served = true')
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    availability_csv['location_id'] = [row[0] for row in result]
    availability_csv['provider_id'] = PROVIDER_ID
    availability_csv['brand_name'] = BRAND_NAME
    availability_csv['technology'] = [row[3] for row in result]
    availability_csv['max_advertised_download_speed'] = [row[1] for row in result]
    availability_csv['max_advertised_upload_speed'] = [row[2] for row in result]
    availability_csv['low_latency'] = LATENCY
    availability_csv['business_residential_code'] = BUSINESS_CODE

    availability_csv = availability_csv[['provider_id', 'brand_name', 'location_id', 'technology', 'max_advertised_download_speed', 
                                        'max_advertised_upload_speed', 'low_latency', 'business_residential_code']] 

    filename = '../../FCC_broadband.csv'
    availability_csv.to_csv(filename, index=False)
    return filename


#might need to add lte data in the future
def compute_wireless_locations(fabricid, kmlid, download, upload, tech, userid):
    session = ScopedSession()
    fabric_file = session.query(file).filter(file.id == fabricid).first()
    coverage_file = session.query(file).filter(file.id == kmlid).first()
    
    if fabric_file is None or coverage_file is None:
        raise FileNotFoundError("Fabric or coverage file not found in the database")
    
    fabric_data = StringIO(fabric_file.data.decode())
    df = pandas.read_csv(fabric_data) 

    fabric = geopandas.GeoDataFrame(
        df.drop(['latitude', 'longitude'], axis=1),
        crs="EPSG:4326",
        geometry=[shapely.geometry.Point(xy) for xy in zip(df.longitude, df.latitude)])
    
    fiona.drvsupport.supported_drivers['kml'] = 'rw'
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    
    coverage_data = BytesIO(coverage_file.data)
    wireless_coverage = geopandas.read_file(coverage_data, driver='KML')
    wireless_coverage = wireless_coverage.to_crs("EPSG:4326")
    fabric_in_wireless = geopandas.sjoin(fabric,wireless_coverage,how="inner")
    bsl_fabric_in_wireless = fabric_in_wireless[fabric_in_wireless['bsl_flag']]
    bsl_fabric_in_wireless = bsl_fabric_in_wireless.drop_duplicates()

    session.close()
    res = add_to_db(bsl_fabric_in_wireless, kmlid, download, upload, tech, True, userid)
    return res

def compute_wired_locations(fabricid, kmlid, download, upload, tech, userid):
    # Open session
    session = ScopedSession()

    # Fetch Fabric file from database
    fabric_file_record = session.query(file).filter(file.id == fabricid).first()
    if not fabric_file_record:
        raise ValueError(f"No file found with name {fabric_file_record.name}")
    fabric_csv_data = fabric_file_record.data.decode()
    
    # Convert the CSV data string to a DataFrame
    fabric_data = StringIO(fabric_csv_data)
    df = pandas.read_csv(fabric_data)

    # Fetch Fiber file from database
    fiber_file_record = session.query(file).filter(file.id == kmlid).first()
    if not fiber_file_record:
        raise ValueError(f"No file found with name {fiber_file_record.name} and id {fiber_file_record.id}")
    fiber_kml_data = fiber_file_record.data

    # Convert the KML data bytes to a file-like object
    fiber_data = BytesIO(fiber_kml_data)

    fabric = geopandas.GeoDataFrame(
        df.drop(['latitude', 'longitude'], axis=1),
        crs="EPSG:4326",
        geometry=[shapely.geometry.Point(xy) for xy in zip(df.longitude, df.latitude)])

    fiona.drvsupport.supported_drivers['kml'] = 'rw'
    fiona.drvsupport.supported_drivers['KML'] = 'rw'

    buffer_meters = 100 
    gdf_fiber = geopandas.read_file(fiber_data, driver='KML', encoding='utf-8')
    fiber_paths = gdf_fiber[gdf_fiber.geom_type == 'LineString']

    fiber_paths = fiber_paths.to_crs('epsg:4326')

    fiber_paths_buffer = fiber_paths.to_crs("EPSG:5070")
    fiber_paths_buffer['geometry'] = fiber_paths_buffer.buffer(buffer_meters)
    fiber_paths_buffer = fiber_paths_buffer.to_crs("EPSG:4326")

    fabric_near_fiber = geopandas.sjoin(fabric, fiber_paths_buffer, how="inner")

    bsl_fabric_near_fiber = fabric_near_fiber[fabric_near_fiber['bsl_flag']] 

    bsl_fabric_near_fiber = bsl_fabric_near_fiber.drop_duplicates() 

    session.close()
    res = add_to_db(bsl_fabric_near_fiber, kmlid, download, upload, tech, False, userid)
    return res 

def add_network_data(fabricid, kmlid ,download, upload, tech, type, userid):
    res = False 
    if type == 0: 
        res = compute_wired_locations(fabricid, kmlid, download, upload, tech, userid)
    elif type == 1: 
        res = compute_wireless_locations(fabricid, kmlid, download, upload, tech, userid)
    return res 


