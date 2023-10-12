import os
import psycopg2
import sqlite3
from controllers.database_controller.kml_ops import get_kml_data, generate_csv_data
import json
import subprocess
import geopandas
from shapely.geometry import shape
from io import StringIO
from psycopg2.extensions import adapt, register_adapter, AsIs
from psycopg2 import Binary
from psycopg2.extras import execute_values
from fastkml import kml
from utils.settings import DATABASE_URL
from multiprocessing import Lock
from celery import chain 
from datetime import datetime
from database.sessions import ScopedSession, Session
from database.models import vector_tiles, file, folder, kml_data, fabric_data, mbtiles
from controllers.celery_controller.celery_config import celery
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc
from .file_ops import get_files_by_type, get_file_with_id, get_files_with_postfix, create_file, update_file_type, get_files_with_prefix, get_file_with_name
from .folder_ops import get_upload_folder, get_export_folder
from .mbtiles_ops import get_latest_mbtiles, delete_mbtiles, get_mbtiles_with_id
from .user_ops import get_user_with_id, get_user_with_username
from utils.namingschemes import DATETIME_FORMAT, EXPORT_CSV_NAME_TEMPLATE

db_lock = Lock()

def recursive_placemarks(folder):
    for feature in folder.features():
        if isinstance(feature, kml.Placemark):
            yield feature
        elif isinstance(feature, kml.Folder):
            yield from recursive_placemarks(feature)


def read_kml(fileid, session):
# Now you can extract all placemarks from the root KML object
    # geojson_array= [
    file_record = get_file_with_id(fileid, session)

    if not file_record:
        raise ValueError(f"No file found with name {file_record.name}")
    
    kml_obj = kml.KML()
    doc = file_record.data
    kml_obj.from_string(doc)

    network_type = None
    polygon_encountered = False

    root_feature = list(kml_obj.features())[0]
    geojson_features = []
    for placemark in recursive_placemarks(root_feature):
        if placemark.geometry.geom_type == 'Point':
            continue
        # Use the placemark object here
        geojson_feature = {
            "type": "Feature",
            "geometry": placemark.geometry.__geo_interface__,  # This gets the GeoJSON geometry
            "properties": {"feature_type": placemark.geometry.geom_type,
                           'network_coverages': file_record.name,} # add the geometry type
        }
        geojson_features.append(geojson_feature)
        if placemark.geometry.geom_type == "Polygon":
            network_type = "wireless"
            polygon_encountered = True
        elif placemark.geometry.geom_type == "LineString" and not polygon_encountered:
            network_type = "wired"

    update_file_type(fileid, network_type)

    return geojson_features

def read_geojson(fileid, session):
    file_record = get_file_with_id(fileid, session)

    if not file_record:
        raise ValueError(f"No file found with name {file_record.name}")

    # Read the GeoJSON data using GeoPandas
    geojson_data = geopandas.read_file(StringIO(file_record.data.decode()))

    # Filter only polygons and linestrings
    desired_geometries = geojson_data[geojson_data.geometry.geom_type.isin(['Polygon', 'LineString'])]

    # Determine the network type
    if 'Polygon' in desired_geometries.geometry.geom_type.tolist():
        network_type = "wireless"
    else:
        network_type = "wired"

    # Update the file type in the database
    update_file_type(fileid, network_type)

    # Convert the GeoDataFrame with desired geometries to a similar format as in read_kml
    geojson_features = []
    for _, row in desired_geometries.iterrows():
        geojson_feature = {
            "type": "Feature",
            "geometry": shape(row['geometry']).__geo_interface__,
            "properties": {
                "feature_type": row['geometry'].geom_type,
                'network_coverages': file_record.name,
            }
        }
        geojson_features.append(geojson_feature)

    return geojson_features



def add_values_to_VT(mbtiles_file_path, folderid):
    with sqlite3.connect(mbtiles_file_path) as mb_conn:
        mb_c = mb_conn.cursor()
        mb_c.execute(
            """
            SELECT zoom_level, tile_column, tile_row, tile_data
            FROM tiles
            """
        )

        # Create a new connection to Postgres
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        try:
            with open(mbtiles_file_path, 'rb') as file:
                mbtiles_data = Binary(file.read())
            
            cur.execute("SELECT COUNT(*) FROM mbtiles WHERE folder_id = %s", (folderid,))
            count = cur.fetchone()[0]
            cur.execute('SELECT "name" FROM "folder" WHERE id = %s', (folderid,))
            foldername = cur.fetchone()[0]
            new_filename = f'{foldername}-{count+1}.mbtiles'

            cur.execute("""
                INSERT INTO mbtiles (tile_data, filename, timestamp, folder_id)
                VALUES (%s, %s, %s, %s) RETURNING id
                """, (mbtiles_data, new_filename, datetime.now(), folderid))

            mbt_id = cur.fetchone()[0]

            data = [(row[0], row[1], row[2], Binary(row[3]), mbt_id) for row in mb_c]

            execute_values(cur, """
                INSERT INTO vector_tiles (zoom_level, tile_column, tile_row, tile_data, mbtiles_id) 
                VALUES %s
                """, data)

            # Commit the transaction
            conn.commit()
        except psycopg2.Error as e:
            print(f"Database error occurred: {e}")
            conn.rollback()
            return -1
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            conn.rollback()
            return -1
        finally:
            cur.close()
            conn.close()
            os.remove(mbtiles_file_path)
            unique_geojson_filename = f"data-{folderid}.geojson"
            os.remove(unique_geojson_filename)
    return 1

def tiles_join(geojson_data, folderid, session):
    from controllers.celery_controller.celery_tasks import run_tippecanoe_tiles_join
    try:
        mbtile_file = get_latest_mbtiles(folderid, session)
        # Save the .mbtiles file temporarily on the disk
        with open(mbtile_file.filename, 'wb') as f:
            f.write(mbtile_file.tile_data)
        # Save the geojson_data to a .geojson file
        with open('data.geojson', 'w') as f:
            json.dump(geojson_data, f)
        # Use tippecanoe to create a new .mbtiles file from the geojson_data
        command1 = "tippecanoe -o new.mbtiles -P -z 16 --drop-densest-as-needed data.geojson --force --use-attribute-for-id=location_id"

        # Use tile-join to merge the new .mbtiles file with the existing one
        command2 = f"tile-join -o merged.mbtiles {mbtile_file.filename} new.mbtiles"

        run_tippecanoe_tiles_join.apply(args=(command1, command2, 1, ["./merged.mbtiles", mbtile_file.filename, "./new.mbtiles"]), throw=True)
        
    except SQLAlchemyError as e:
        print(f"Error occurred during query: {str(e)}")
        return None

    

def create_tiles(geojson_array, userid, folderid, session):
    from controllers.celery_controller.celery_tasks import run_tippecanoe
    network_data = get_kml_data(userid, folderid, session)
    if network_data:
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
                        'bsl': point['bsl'],
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

        unique_geojson_filename = f"data-{folderid}.geojson"

        with open(unique_geojson_filename, 'w') as f:
            json.dump(point_geojson, f)
        
        outputFile = "output" + str(userid) + ".mbtiles"
        command = f"tippecanoe -o {outputFile} --base-zoom=7 -P --maximum-tile-bytes=3000000 -z 16 --drop-densest-as-needed {unique_geojson_filename} --force --use-attribute-for-id=location_id --layer=data"
        run_tippecanoe(command, folderid, outputFile) 

def retrieve_tiles(zoom, x, y, username, mbtileid=None):
    session = Session()
    try:
        user = get_user_with_username(user_name=username, session=session)
        if not user:
            return None

        if mbtileid:
            tile = session.query(vector_tiles.tile_data).join(mbtiles, vector_tiles.mbtiles_id == mbtiles.id).filter(
                vector_tiles.zoom_level == int(zoom),
                vector_tiles.tile_column == int(x),
                vector_tiles.tile_row == int(y),
                mbtiles.id == mbtileid
            ).first()
        else:
            folder = get_upload_folder(userid=user.id, folderid=None, session=session)
            if not folder:
                return None
            tile = session.query(vector_tiles.tile_data).join(mbtiles, vector_tiles.mbtiles_id == mbtiles.id).filter(
                vector_tiles.zoom_level == int(zoom),
                vector_tiles.tile_column == int(x),
                vector_tiles.tile_row == int(y),
                mbtiles.folder_id == folder.id
            ).order_by(desc(mbtiles.timestamp)).first()

        return tile
    finally:
        session.close()

def toggle_tiles(markers, userid, mbtid):
    message = ''
    status_code = 0
    session = Session()
    try:
        # Get the last folder of the user
        if mbtid != -1:
            mbtiles_entry = get_mbtiles_with_id(mbtid=mbtid, session=session)
            user_last_folder = get_export_folder(userid=userid, folderid=mbtiles_entry.folder_id, session=session)
        else:
            user_last_folder = get_upload_folder(userid=userid, folderid=None, session=session)
        if user_last_folder:
            
            kml_set = set()
            for marker in markers:
                # Retrieve all kml_data entries where location_id equals to marker['id']
                kml_data_entries = session.query(kml_data).join(file).filter(kml_data.location_id == marker['id'], file.folder_id == user_last_folder.id).all()
                for kml_data_entry in kml_data_entries:
                    kml_file = get_file_with_id(fileid=kml_data_entry.file_id, session=session)
                    # Count files with .edit prefix in the folder
                    edit_count = len(get_files_with_prefix(folderid=user_last_folder.id, prefix=f"{kml_file.name}-edit", session=session))
                    if kml_data_entry.file_id not in kml_set:
                        new_file = create_file(filename=f"{kml_file.name}-edit{edit_count+1}/", content=None, folderid=user_last_folder.id, filetype='edit', session=session)
                        session.add(new_file)
                        session.commit()
                        kml_set.add(kml_file.id)
                    else:
                        new_file = get_file_with_name(filename=f"{kml_file.name}-edit{edit_count}/", folderid=user_last_folder.id, session=session)
                    
                    # Update each entry
                    kml_data_entry.file_id = new_file.id
                    kml_data_entry.served = marker['served']
                    kml_data_entry.coveredLocations = new_file.name
                    session.add(kml_data_entry)
                    session.commit()

        else:
            raise Exception('No last folder for the user')
        
        geojson_data = []
        all_kmls = get_files_with_postfix(user_last_folder.id, '.kml', session)
        for kml_f in all_kmls:
            geojson_data.append(read_kml(kml_f.id, session))
        
        all_geojsons = get_files_with_postfix(folderid=user_last_folder.id, postfix='.geojson', session=session)
        for geojson_f in all_geojsons:
            geojson_data.append(read_geojson(geojson_f.id, session))

        delete_mbtiles(user_last_folder.id, session)
        create_tiles(geojson_data, userid, user_last_folder.id, session)
        if mbtid != -1:
            existing_csvs = get_files_by_type(folderid=user_last_folder.id, filetype='export', session=session)
            for csv_file in existing_csvs:
                session.delete(csv_file)

            userVal = get_user_with_id(userid=userid, session=session)
            # Generate and save a new CSV
            all_file_ids = [file.id for file in get_files_with_postfix(user_last_folder.id, '.kml', session) + get_files_with_postfix(user_last_folder.id, '.geojson', session)]

            results = session.query(kml_data).filter(kml_data.file_id.in_(all_file_ids)).all()
            availability_csv = generate_csv_data(results, userVal.provider_id, userVal.brand_name)

            csv_name = EXPORT_CSV_NAME_TEMPLATE.format(brand_name=userVal.brand_name, current_datime=datetime.now().strftime(DATETIME_FORMAT))
            csv_data_str = availability_csv.to_csv(index=False, encoding='utf-8')
            new_csv_file = create_file(filename=csv_name, content=csv_data_str.encode('utf-8'), folderid=user_last_folder.id, filetype='export', session=session)
            session.add(new_csv_file)

        

        message = 'Markers toggled successfully'
        status_code = 200
        
        
        

    except Exception as e:
        session.rollback()  # rollback transaction on error
        message = str(e)  # send the error message to client
        status_code = 500

    finally:
        session.commit()
        session.close()

    return (message, status_code)
