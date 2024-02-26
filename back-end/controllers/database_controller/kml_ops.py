from database.models import kml_data, fabric_data, file, user, vector_tiles, mbtiles
from sqlalchemy.exc import IntegrityError
from utils.settings import BATCH_SIZE, DATABASE_URL
from sqlalchemy.exc import SQLAlchemyError
from multiprocessing import Lock
from database.sessions import ScopedSession, Session
from datetime import datetime
import logging, uuid, psycopg2, io, pandas, geopandas, shapely
from shapely.geometry import Point
import fiona
from io import StringIO, BytesIO
from .user_ops import get_user_with_id
from .file_ops import get_files_with_postfix, get_file_with_id, get_files_with_postfix, create_file, get_files_by_type
from .folder_ops import create_folder, get_upload_folder
from utils.logger_config import logger

db_lock = Lock()

def get_kml_data(userid, folderid, session=None): 
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    userVal = get_user_with_id(userid, session)

    try:
        # Query the File records related to the folder_id
        fabric_files = get_files_by_type(folderid, "fabric", session)
        kml_files = get_files_with_postfix(folderid, ".kml", session)
        geojson_files = get_files_with_postfix(folderid, ".geojson", session)
        coverage_files = kml_files + geojson_files

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

            for kml_file in coverage_files:
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
            for kml_file in coverage_files:
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


def get_kml_data_by_file(fileid, session=None): 
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        kml_entries = session.query(kml_data).filter_by(file_id=fileid).all()
        return kml_entries
    finally:
        if owns_session:
            session.close()

def add_to_db(pandaDF, kmlid, download, upload, tech, wireless, userid, latency, category, session):
    batch = [] 

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
                latency = latency, 
                category = category
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

    return True

def generate_csv_data(results, provider_id, brand_name):
    availability_csv = pandas.DataFrame()

    availability_csv['location_id'] = [row.location_id for row in results]
    availability_csv['provider_id'] = provider_id
    availability_csv['brand_name'] = brand_name
    availability_csv['technology'] = [row.techType for row in results]
    availability_csv['max_advertised_download_speed'] = [row.maxDownloadSpeed for row in results]
    availability_csv['max_advertised_upload_speed'] = [row.maxUploadSpeed for row in results]
    availability_csv['low_latency'] = [row.latency for row in results]
    availability_csv['business_residential_code'] = [row.category for row in results]

    availability_csv.drop_duplicates(subset=['location_id', 'technology'], keep='first', inplace=True)
    availability_csv = availability_csv[['provider_id', 'brand_name', 'location_id', 'technology', 'max_advertised_download_speed', 
                                         'max_advertised_upload_speed', 'low_latency', 'business_residential_code']]

    return availability_csv

def export(userid, folderid, providerid, brandname, session): 
    from controllers.celery_controller.celery_tasks import async_folder_copy_for_export

    all_files = get_files_with_postfix(folderid, '.kml', session) + get_files_with_postfix(folderid, '.geojson', session)
    all_file_ids = [file.id for file in all_files]
    results = session.query(kml_data).filter(kml_data.file_id.in_(all_file_ids)).all()

    availability_csv = generate_csv_data(results, providerid, brandname)

    output = io.BytesIO()
    availability_csv.to_csv(output, index=False, encoding='utf-8')
    csv_data_str = availability_csv.to_csv(index=False, encoding='utf-8')

    # original_folder = get_upload_folder(userid=userid, folderid=folderid, session=session)
    # new_folder = original_folder.copy(name=folder_name,type='export', session=session)

    # csv_file = create_file(filename=csv_name, content=csv_data_str.encode('utf-8'), folderid=new_folder.id, filetype='export', session=session)
    
    # session.add(csv_file)
    # session.commit()

    async_folder_copy_for_export.apply_async(args=[userid, folderid, csv_data_str])

    return output

def compute_lte(folderid, geojsonid, download, upload, tech, userid, latency, category):
    kml_files = get_files_with_postfix(folderid, '.kml')
    kml_file_ids = [file.id for file in kml_files]

    geojson_file = get_file_with_id(geojsonid)
    geojson_content = BytesIO(geojson_file.data)

    session = ScopedSession()
    
    # Load the required points from the kml_data table
    kml_data_points = session.query(kml_data).filter(kml_data.file_id.in_(kml_file_ids), kml_data.wireless == True).all()
    
    # Convert those points to a GeoDataFrame
    df = pandas.DataFrame([(point.id, point.longitude, point.latitude) for point in kml_data_points], columns=['id', 'longitude', 'latitude'])
    gdf_points = geopandas.GeoDataFrame(df, crs="EPSG:4326", geometry=geopandas.points_from_xy(df.longitude, df.latitude))
    
    # Load geoJSON polygon data
    lte_coverage = geopandas.read_file(geojson_content)
    lte_coverage = lte_coverage.to_crs("EPSG:4326")
    
    # Perform a spatial join to determine which points are within the polygon
    points_in_coverage = geopandas.sjoin(gdf_points, lte_coverage, predicate='within')
    
    # Update the lte column based on results
    covered_ids = points_in_coverage['id'].to_list()
    for point in kml_data_points:
        if point.id in covered_ids:
            point.lte = True
            point.file_id = geojsonid
            point.maxDownloadNetwork = download
            point.maxUploadSpeed = upload
            point.techType = tech
            point.coveredLocations = geojson_file.name
            point.latency = latency
            point.category = category

    session.commit()
    session.close()

def rename_conflicting_columns(gdf):
    """Rename 'index_left' and 'index_right' columns if they exist in a GeoDataFrame."""
    rename_dict = {}
    if 'index_left' in gdf.columns:
        rename_dict['index_left'] = 'index_left_original'
    if 'index_right' in gdf.columns:
        rename_dict['index_right'] = 'index_right_original'
    return gdf.rename(columns=rename_dict)

#might need to add lte data in the future
def compute_wireless_locations(folderid, kmlid, download, upload, tech, userid, latency, category, session):
    
    fabric_files = get_files_with_postfix(folderid, '.csv')
    coverage_file = get_file_with_id(kmlid)

    
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
    
    coverage_data = BytesIO(coverage_file.data)
    if (coverage_file.name.endswith('.kml')):
        fiona.drvsupport.supported_drivers['kml'] = 'rw'
        fiona.drvsupport.supported_drivers['KML'] = 'rw'
        wireless_coverage = geopandas.read_file(coverage_data, driver='KML')
    else:
        wireless_coverage = geopandas.read_file(coverage_data)

    wireless_coverage = wireless_coverage.to_crs("EPSG:4326")
    fabric = rename_conflicting_columns(fabric)
    wireless_coverage = rename_conflicting_columns(wireless_coverage)
    fabric_in_wireless = geopandas.sjoin(fabric,wireless_coverage,how="inner")
    bsl_fabric_in_wireless = fabric_in_wireless[fabric_in_wireless['bsl_flag']]
    bsl_fabric_in_wireless = bsl_fabric_in_wireless.drop_duplicates(subset='location_id', keep='first')

    logger.debug(f'number of points computed: {len(bsl_fabric_in_wireless)}')
    res = add_to_db(bsl_fabric_in_wireless, kmlid, download, upload, tech, True, userid, latency, category, session)
    return res

def preview_wireless_locations(folderid, kml_filename):
    
    fabric_files = get_files_with_postfix(folderid, '.csv')
    with open(kml_filename, 'rb') as file:  # Open the file in binary mode
        coverage_data = file.read()  # Read the entire content of the file into memory

    
    if fabric_files is None:
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
    
    coverage_data_io = BytesIO(coverage_data)
    
    fiona.drvsupport.supported_drivers['kml'] = 'rw'
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    wireless_coverage = geopandas.read_file(coverage_data_io, driver='KML')


    wireless_coverage = wireless_coverage.to_crs("EPSG:4326")
    fabric = rename_conflicting_columns(fabric)
    wireless_coverage = rename_conflicting_columns(wireless_coverage)
    fabric_in_wireless = geopandas.sjoin(fabric,wireless_coverage,how="inner")
    bsl_fabric_in_wireless = fabric_in_wireless[fabric_in_wireless['bsl_flag']]
    bsl_fabric_in_wireless = bsl_fabric_in_wireless.drop_duplicates(subset='location_id', keep='first')

    logger.debug(f'number of points computed: {len(bsl_fabric_in_wireless)}')
    return bsl_fabric_in_wireless

def compute_wired_locations(folderid, kmlid, download, upload, tech, userid, latency, category, session):
    

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

    # Convert the KML data bytes to a file-like object
    fiber_data = BytesIO(fiber_kml_data)

    fabric = geopandas.GeoDataFrame(
        df,
        crs="EPSG:4326",
        geometry=[shapely.geometry.Point(xy) for xy in zip(df.longitude, df.latitude)])

    buffer_meters = 100 
    if fiber_file_record.name.endswith('kml'):
        fiona.drvsupport.supported_drivers['kml'] = 'rw'
        fiona.drvsupport.supported_drivers['KML'] = 'rw'
        gdf_fiber = geopandas.read_file(fiber_data, driver='KML', encoding='utf-8')
    else:
        gdf_fiber = geopandas.read_file(fiber_data)

    fiber_paths = gdf_fiber[gdf_fiber.geom_type == 'LineString']

    fiber_paths = fiber_paths.to_crs('epsg:4326')

    fiber_paths_buffer = fiber_paths.to_crs("EPSG:5070")
    fiber_paths_buffer['geometry'] = fiber_paths_buffer.buffer(buffer_meters)
    fiber_paths_buffer = fiber_paths_buffer.to_crs("EPSG:4326")

    fabric_near_fiber = geopandas.sjoin(fabric, fiber_paths_buffer, how="inner")

    bsl_fabric_near_fiber = fabric_near_fiber[fabric_near_fiber['bsl_flag']] 

    bsl_fabric_near_fiber = bsl_fabric_near_fiber.drop_duplicates(subset='location_id', keep='first')
    # bsl_fabric_near_fiber = bsl_fabric_near_fiber.drop_duplicates()  

    res = add_to_db(bsl_fabric_near_fiber, kmlid, download, upload, tech, False, userid, latency, category, session)
    return res 

def add_network_data(folderid, kmlid ,download, upload, tech, type, userid, latency, category, session):
    res = False 
    if type == 0: 
        res = compute_wired_locations(folderid, kmlid, download, upload, tech, userid, latency, category, session)
    elif type == 1: 
        res = compute_wireless_locations(folderid, kmlid, download, upload, tech, userid, latency, category, session)
    return res 


