from sqlalchemy import create_engine
from utils.settings import DATABASE_URL
from io import StringIO
import psycopg2
from database.sessions import ScopedSession, Session
from utils.facts import states
from database.models import fabric_data, file
from psycopg2.errors import UniqueViolation
from threading import Lock

db_lock = Lock()

def check_num_records_greater_zero(folderid):
    session = Session()

    # Might need to query multiple fabrics down the road
    files_in_folder = session.query(file).filter(file.folder_id == folderid, file.name.endswith('.csv')).one()

    # If there is no file in the folder, return False.
    if not files_in_folder:
        return None

    # Check each file in the folder to see if there are associated fabric_data entries.
    
    if session.query(fabric_data).filter(fabric_data.file_id == files_in_folder.id).count() > 0:
        return files_in_folder.id

    # If no file in the folder has associated fabric_data entries, return False.
    return None

def write_to_db(fileid): 
    session = ScopedSession()
    with db_lock: 
        file_record = session.query(file).filter(file.id == fileid).first()
        session.close() 

    if not file_record:
        raise ValueError(f"No file found with name {file_record.name}")

    csv_data = file_record.data.decode()

    engine = create_engine(DATABASE_URL)
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cur:
            # Create temporary table
            cur.execute('CREATE TEMP TABLE temp_fabric AS SELECT * FROM fabric_data_temp LIMIT 0;')

            # Copy data to temporary table
            output = StringIO(csv_data)
            cur.copy_expert("COPY temp_fabric FROM STDIN CSV HEADER DELIMITER ','", output)
            output.seek(0)

             # Insert data from temporary table to final table with user_id
            try:
                cur.execute(f'INSERT INTO fabric_data SELECT *, {fileid} as file_id FROM temp_fabric;')
                connection.commit()
            except psycopg2.errors.UniqueViolation:
                print("UniqueViolation occurred, ignoring.")
                
            connection.commit()
    finally:
        connection.close()

def address_query(query):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    results = []

    if query:
        query_split = query.split()

        if len(query_split) >= 3:
            primary_address = " ".join(query_split[:-2]).upper()
            city = query_split[-2].upper().strip()
            state = query_split[-1].upper().strip()

            cursor.execute(
                """
                SELECT address_primary, city, state, zip_code, latitude, longitude
                FROM "fabric_data"
                WHERE UPPER(address_primary) LIKE %s AND UPPER(city) = %s AND UPPER(state) = %s
                LIMIT 1
                """,
                ('%' + primary_address + '%', city, state,)
            )

            results.extend(cursor.fetchall())

        if len(query_split) >= 2:
            primary_address = " ".join(query_split[:-1]).upper()
            city_or_state = query_split[-1].upper().strip()

            if city_or_state in states:  
                cursor.execute(
                    """
                    SELECT address_primary, city, state, zip_code, latitude, longitude
                    FROM "fabric_data"
                    WHERE UPPER(address_primary) LIKE %s AND UPPER(state) = %s
                    LIMIT 3
                    """,
                    ('%' + primary_address + '%', city_or_state,)
                )

            else:  
                cursor.execute(
                    """
                    SELECT address_primary, city, state, zip_code, latitude, longitude
                    FROM "fabric_data" 
                    WHERE UPPER(address_primary) LIKE %s AND UPPER(city) = %s
                    LIMIT 3
                    """,
                    ('%' + primary_address + '%', city_or_state,)
                )

            results.extend(cursor.fetchall())

        cursor.execute(
            """
            SELECT address_primary, city, state, zip_code, latitude, longitude
            FROM "fabric_data" 
            WHERE UPPER(address_primary) LIKE %s 
            LIMIT 5
            """,
            ('%' + query.upper() + '%',)
        )

        results.extend(cursor.fetchall())

    results_dict = [
        {
            "address": result[0],
            "city": result[1],
            "state": result[2],
            "zipcode": result[3],
            "latitude": result[4],
            "longitude": result[5]
        } for result in results
    ]

    cursor.close()
    conn.close()

    return results_dict

if __name__ == "__main__":
    write_to_db("FCC_Active_BSL_12312022_ver1.csv", 1)