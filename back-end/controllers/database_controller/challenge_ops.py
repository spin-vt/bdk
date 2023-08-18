from sqlalchemy import create_engine
from utils.settings import DATABASE_URL
from io import StringIO
import psycopg2
from database.sessions import ScopedSession, Session
from utils.facts import states
from database.models import fabric_data, file, ChallengeLocations
from psycopg2.errors import UniqueViolation
from threading import Lock
import logging, uuid, psycopg2, io, pandas, geopandas, shapely, os
import geopandas as gpd
import pandas as pd

db_lock = Lock()

def writeToDB(data) -> None: 
    with db_lock:
        session = Session()
        try:
            # Create an instance of the ChallengeLocations model
            challenge_location = ChallengeLocations(
                contact_name=data.get('contact_name', None),
                contact_email=data.get('contact_email', None),
                contact_phone=data.get('contact_phone', None),
                category_code=data.get('category_code', None),
                location_id=data.get('location_id', None),
                address=data.get('address_primary', None),
                primary_city=data.get('city', None),
                state=data.get('state', None),
                zip_code=data.get('zip_code', None),
                zip_code_suffix=data.get('zip_code_suffix', None),
                unit_count=data.get('unit_count', None),
                building_type_code=data.get('building_type', None),
                non_bsl_code=data.get('non_bsl_code', None),
                bsl_lacks_address_flag=data.get('bsl_lacks_address_flag', None),
                latitude=data.get('latitude', None),
                longitude=data.get('longitude', None),
                address_id=data.get('address_id', None),
            )

            # Add this entry to the session
            session.add(challenge_location)

            # Commit the transaction
            session.commit()
        except UniqueViolation:  # Handle unique constraint violations, if any
            session.rollback()  # Rollback the session in case of any error
            raise
        except Exception as e:  # Handle any other SQLAlchemy/database exceptions
            session.rollback()
            raise e
        finally:
            session.close()

def export(): 
    availability_csv = pandas.DataFrame()

    #we would want to fetch only the entries for this user 
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM challenge_locations')
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    availability_csv['address'] = [row[0] for row in result]
    availability_csv['primary_city'] = [row[1] for row in result]
    availability_csv['state'] = [row[2] for row in result]
    availability_csv['zip_code'] = [row[3] for row in result]
    availability_csv['zip_code_suffix'] = [row[4] for row in result]
    availability_csv['unit_count'] = [row[5] for row in result]
    availability_csv['building_type_code'] = [row[6] for row in result]
    availability_csv['non_bsl_code'] = [row[7] for row in result]
    availability_csv['bsl_lacks_address_flag'] = [row[8] for row in result]
    availability_csv['latitude'] = [row[9] for row in result]
    availability_csv['longitude'] = [row[10] for row in result]
    availability_csv['address_id'] = [row[11] for row in result]
    availability_csv['contact_name'] = [row[12] for row in result]
    availability_csv['contact_email'] = [row[13] for row in result]
    availability_csv['contact_phone'] = [row[14] for row in result]
    availability_csv['category_code'] = [row[15] for row in result]
    availability_csv['location_id'] = [row[16] for row in result]

    availability_csv = availability_csv[[
    'address', 'primary_city', 'state', 'zip_code', 'zip_code_suffix',
    'unit_count', 'building_type_code', 'non_bsl_code',
    'bsl_lacks_address_flag', 'latitude', 'longitude', 'address_id',
    'contact_name', 'contact_email', 'contact_phone',
    'category_code', 'location_id'
    ]] 

    output = io.BytesIO()
    availability_csv.to_csv(output, index=False, encoding='utf-8')
    return output

def import_to_postgis(geojson_path, kml_path, csv1_path, csv2_path, db_name, db_user, db_password, db_host):
    # Check if the paths exist
    for path in [geojson_path, kml_path, csv1_path, csv2_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"The file {path} does not exist.")

    # 1. Create and set up PostGIS database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Function to run ogr2ogr and check its status
    def run_ogr2ogr(filepath, table_name):
        cmd = f'ogr2ogr -f "PostgreSQL" PG:"dbname={db_name} user={db_user} password={db_password} host={db_host}" "{filepath}" -nln {table_name}'
        ret = os.system(cmd)
        if ret != 0:
            raise RuntimeError(f"Failed to execute command {cmd} with return code {ret}")

    # 2. Import GeoJSON and other files
    run_ogr2ogr(geojson_path, "buildings")
    run_ogr2ogr(kml_path, "network")
    run_ogr2ogr(csv1_path, "fcc_data1")
    run_ogr2ogr(csv2_path, "fcc_data2")

    # 3. Add geometry columns and spatial indexes
    sql_commands = [
        "ALTER TABLE fcc_data1 ADD COLUMN geom geometry(Point, 4326);",
        "UPDATE fcc_data1 SET geom = ST_SetSRID(ST_MakePoint(CAST(longitude AS float), CAST(latitude AS float)), 4326);",
        "CREATE INDEX idx_fcc_data1_geom ON fcc_data1 USING GIST (geom);",
        
        "ALTER TABLE fcc_data2 ADD COLUMN geom geometry(Point, 4326);",
        "UPDATE fcc_data2 SET geom = ST_SetSRID(ST_MakePoint(CAST(longitude AS float), CAST(latitude AS float)), 4326);",
        "CREATE INDEX idx_fcc_data2_geom ON fcc_data2 USING GIST (geom);",

        "CREATE INDEX idx_buildings_geom ON buildings USING GIST (wkb_geometry);",
        "CREATE INDEX idx_network_geom ON network USING GIST (wkb_geometry);"
    ]

    for command in sql_commands:
        cur.execute(command)

    conn.commit()
    cur.close()
    conn.close()

    print("Data imported successfully!")
    compute_remaining_buildings_near_network(50)
    print("Challenge locations computed!")

def compute_remaining_buildings_near_network(proximity_distance_meters):
    # Connect to PostGIS database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Vacuum and analyze the tables for optimization
    cur.execute("VACUUM ANALYZE buildings;")
    cur.execute("VACUUM ANALYZE network;")
    cur.execute("VACUUM ANALYZE fcc_data1;")
    cur.execute("VACUUM ANALYZE fcc_data2;")
    conn.commit()

    # Step 1: Identify buildings not in fcc_data1 or fcc_data2
    sql_not_in_fcc = """
    CREATE TEMP TABLE temp_buildings AS 
    SELECT b.*
    FROM buildings b
    LEFT JOIN fcc_data1 f1 ON ST_DWithin(b.wkb_geometry, f1.geom, 0.0001) 
    LEFT JOIN fcc_data2 f2 ON ST_DWithin(b.wkb_geometry, f2.geom, 0.0001)
    WHERE f1.ogc_fid IS NULL AND f2.ogc_fid IS NULL;
    """

    # Step 2: Identify the buildings from the above set that are within a specified proximity of the network
    sql_near_network = f"""
    CREATE TABLE buildings_near_network AS 
    SELECT tb.*
    FROM temp_buildings tb, network n
    WHERE ST_DWithin(tb.wkb_geometry, n.wkb_geometry, {proximity_distance_meters})
    GROUP BY tb.id; 
    """

    # Execute commands
    cur.execute(sql_not_in_fcc)
    cur.execute(sql_near_network)

    # Commit and close
    conn.commit()
    cur.close()
    conn.close()

    print("Computation completed successfully!")

