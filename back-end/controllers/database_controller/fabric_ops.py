from sqlalchemy import create_engine
from utils.settings import DATABASE_URL
from io import StringIO
import psycopg2
from database.sessions import Session
from utils.facts import states
from database.models import Data
from psycopg2.errors import UniqueViolation

def check_num_records_greater_zero():
    session = Session()
    return session.query(Data).count() > 0

def write_to_db(fileName): 
    csv_file = fileName

    engine = create_engine(DATABASE_URL)

    with open(csv_file, 'r') as file:
        csv_data = file.read()

    connection = engine.raw_connection()
    try:
        with connection.cursor() as cur:
            output = StringIO(csv_data)
            try:
                cur.copy_expert("COPY fabric FROM STDIN CSV HEADER DELIMITER ','", output)
                output.seek(0)
            except UniqueViolation:
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
                FROM "fabric"
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
                    FROM "fabric"
                    WHERE UPPER(address_primary) LIKE %s AND UPPER(state) = %s
                    LIMIT 3
                    """,
                    ('%' + primary_address + '%', city_or_state,)
                )

            else:  
                cursor.execute(
                    """
                    SELECT address_primary, city, state, zip_code, latitude, longitude
                    FROM "fabric" 
                    WHERE UPPER(address_primary) LIKE %s AND UPPER(city) = %s
                    LIMIT 3
                    """,
                    ('%' + primary_address + '%', city_or_state,)
                )

            results.extend(cursor.fetchall())

        cursor.execute(
            """
            SELECT address_primary, city, state, zip_code, latitude, longitude
            FROM "fabric" 
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