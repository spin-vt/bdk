from database.models import kml_data, fabric_data, file, user
from sqlalchemy.exc import IntegrityError
from utils.settings import BATCH_SIZE, DATABASE_URL
from sqlalchemy.exc import SQLAlchemyError
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
from .user_ops import get_user_with_id
from .file_ops import get_files_with_postfix, get_file_with_id, get_files_with_postfix


db_lock = Lock()

def get_kml_data(userid, folderid, session=None): 
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    userVal = get_user_with_id(userid, session)

    try:
        # Query the File records related to the folder_id
        fabric_files = get_files_with_postfix(folderid, ".csv", session)
        kml_files = get_files_with_postfix(folderid, ".kml", session)

        # Query all locations in fabric_data
        all_data = {}
        if len(fabric_files) > 0:
            for fabric_file in fabric_files:
                all_locations = session.query(
                    fabric_data.location_id,
                    fabric_data.latitude, 
                    fabric_data.address_primary,
                    fabric_data.longitude,
                    fabric_data.bsl_flag
                ).filter(fabric_data.file_id == fabric_file.id).all()  # Change to fabric_file.id

                # Initialize a dictionary to hold location_id as key and its data as value, including location_id itself
                all_data.update({r[0]: {'location_id': r[0], 'latitude': r[1], 'address': r[2], 'longitude': r[3], 'bsl': r[4]} for r in all_locations})

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
                        existing_data = all_data[r[0]]
                        new_data = {
                            'served': r[1],
                            'wireless': r[2] or existing_data.get('wireless', False),
                            'lte': r[3] or existing_data.get('lte', False),
                            'username': r[4],
                            'coveredLocations': ', '.join(filter(None, [r[5], existing_data.get('coveredLocations', '')])),
                            'maxDownloadNetwork': r[6] if r[7] > existing_data.get('maxDownloadSpeed', -1) else existing_data.get('maxDownloadNetwork', ''),
                            'maxDownloadSpeed': max(r[7], existing_data.get('maxDownloadSpeed', -1))
                        }
                        # Merge the existing and new data
                        all_data[r[0]].update(new_data)
                    else:
                        # The location was not in the fabric file, but it is in one of the KML files
                        # You need to decide how to handle this situation.
                        pass

                # For all other locations, fill with default values
            for loc in all_data.values():
                for key, value in default_data.items():
                    loc.setdefault(key, value)
        else:
            for kml_file in kml_files:
                print(kml_file.name)
                # Query all locations that are served
                resultsServed = session.query(
                    kml_data.location_id, 
                    kml_data.served, 
                    kml_data.wireless,
                    kml_data.lte,
                    kml_data.username,
                    kml_data.coveredLocations,
                    kml_data.maxDownloadNetwork,
                    kml_data.maxDownloadSpeed,
                    kml_data.address_primary,
                    kml_data.latitude,
                    kml_data.longitude
                ).filter(
                    kml_data.file_id == kml_file.id  # Change to kml_file.id
                ).all()

                # Add served data to the respective location in all_data, merge two file that served the same point,
                # record the maxdownloadnetwork and maxuploadspeed
                for r in resultsServed:
                    existing_data = all_data.get(r[0], {})
                    new_data = {
                        'location_id': r[0],
                        'served': r[1],
                        'wireless': r[2] or existing_data.get('wireless', False),
                        'lte': r[3] or existing_data.get('lte', False),
                        'username': r[4],
                        'coveredLocations': ', '.join(filter(None, [r[5], existing_data.get('coveredLocations', '')])),
                        'maxDownloadNetwork': r[6] if r[7] > existing_data.get('maxDownloadSpeed', -1) else existing_data.get('maxDownloadNetwork', ''),
                        'maxDownloadSpeed': max(r[7], existing_data.get('maxDownloadSpeed', -1)),
                        'address': r[8],
                        'latitude': r[9],
                        'longitude': r[10],
                        'bsl': 'False',
                    }
                    # Merge the existing and new data
                    all_data[r[0]] = new_data
                


        # Convert dictionary values to a list
        data = list(all_data.values())
    except SQLAlchemyError as e:
        print('Error when querying the database')
        return None
    finally:
        if owns_session:
            session.close()

        return data

def add_to_db(pandaDF, kmlid, download, upload, tech, wireless, userid):
    batch = [] 
    session = Session()

    userVal = get_user_with_id(userid)
    fileVal = get_file_with_id(kmlid)

    for _, row in pandaDF.iterrows():
        try:
            if row.location_id == '': 
                continue
            
            if download == "": 
                download = 0
                
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
                file_id = fileVal.id,
                address_primary = row.address_primary,
                longitude = row.longitude,
                latitude = row.latitude,
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

    cursor.execute('SELECT location_id, "maxDownloadSpeed", "maxUploadSpeed", "techType" FROM kml_data WHERE served = true')
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
def compute_wireless_locations(folderid, kmlid, download, upload, tech, userid):
    
    fabric_files = get_files_with_postfix(folderid, '.csv')
    coverage_file = get_file_with_id(kmlid)

    session = ScopedSession()
    
    if fabric_files is None or coverage_file is None:
        raise FileNotFoundError("Fabric or coverage file not found in the database")
    
    fabric_arr = []
    for fabric_file in fabric_files:
        tempdf = pandas.read_csv(StringIO(fabric_file.data.decode()))
        fabric_arr.append(tempdf)
    df = pandas.concat(fabric_arr)

    fabric = geopandas.GeoDataFrame(
        df,
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

def compute_wired_locations(folderid, kmlid, download, upload, tech, userid):
    

    # Fetch Fabric file from database
    fabric_files = get_files_with_postfix(folderid, '.csv')
    if not fabric_files:
        raise ValueError(f"No fabric file found")
    
    fabric_arr = []
    for fabric_file in fabric_files:
        tempdf = pandas.read_csv(StringIO(fabric_file.data.decode()))
        fabric_arr.append(tempdf)
    df = pandas.concat(fabric_arr)

    # Fetch Fiber file from database
    fiber_file_record = get_file_with_id(kmlid)
    if not fiber_file_record:
        raise ValueError(f"No file found with name {fiber_file_record.name} and id {fiber_file_record.id}")
    fiber_kml_data = fiber_file_record.data

    # Open session
    session = ScopedSession()

    # Convert the KML data bytes to a file-like object
    fiber_data = BytesIO(fiber_kml_data)

    fabric = geopandas.GeoDataFrame(
        df,
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

def add_network_data(folderid, kmlid ,download, upload, tech, type, userid):
    res = False 
    if type == 0: 
        res = compute_wired_locations(folderid, kmlid, download, upload, tech, userid)
    elif type == 1: 
        res = compute_wireless_locations(folderid, kmlid, download, upload, tech, userid)
    return res 


