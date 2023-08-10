from sqlalchemy import create_engine
from utils.settings import DATABASE_URL
from io import StringIO
import psycopg2
from database.sessions import ScopedSession, Session
from utils.facts import states
from database.models import fabric_data, file, ChallengeLocations
from psycopg2.errors import UniqueViolation
from threading import Lock
import logging, uuid, psycopg2, io, pandas, geopandas, shapely

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