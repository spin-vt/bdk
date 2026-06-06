from io import StringIO
from threading import Lock

import psycopg2
from sqlalchemy import and_, create_engine

from database.models import fabric_data, file
from database.sessions import Session
from utils.facts import states
from utils.settings import DATABASE_URL

from .file_ops import get_files_with_postfix

db_lock = Lock()


def check_num_records_greater_zero(folderid):
    session = Session()

    # Might need to query multiple fabrics down the road
    files_in_folder = (
        session.query(file).filter(file.folder_id == folderid, file.name.endswith(".csv")).all()
    )

    # If there is no file in the folder, return False.
    if not files_in_folder:
        return None

    # Check each file in the folder to see if there are associated fabric_data entries.
    for file in files_in_folder:
        if session.query(fabric_data).filter(fabric_data.file_id == file.id).count() > 0:
            return True

    # If no file in the folder has associated fabric_data entries, return False.
    return False


def write_to_db(fileid):
    # Own a plain Session here (not the request-scoped ScopedSession): this runs
    # in a Celery task, and under eager execution it shares the web handler's
    # thread — grabbing+closing the scoped session there would detach the
    # handler's ORM objects mid-request. A fresh Session is also consistent with
    # the sibling ops in this module.
    session = Session()
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
            cur.execute("CREATE TEMP TABLE temp_fabric AS SELECT * FROM fabric_data_temp LIMIT 0;")

            # Copy data to temporary table
            output = StringIO(csv_data)
            cur.copy_expert("COPY temp_fabric FROM STDIN CSV HEADER DELIMITER ','", output)
            output.seek(0)

            try:
                cur.execute(
                    f"INSERT INTO fabric_data SELECT *, {fileid} as file_id FROM temp_fabric;"
                )
                connection.commit()
            except psycopg2.errors.UniqueViolation:
                print("UniqueViolation occurred, ignoring.")

            connection.commit()
    finally:
        connection.close()


def address_query(folderid, query, session):
    all_fabric = get_files_with_postfix(folderid, ".csv", session)
    all_kml = get_files_with_postfix(folderid, ".kml", session)
    all_geojson = get_files_with_postfix(folderid, ".geojson", session)
    all_files_ids = [file.id for file in all_fabric + all_kml + all_geojson]

    results = []

    if query:
        query_split = query.split()

        primary_address_query = fabric_data.address_primary.ilike(
            "%" + " ".join(query_split[:-1]) + "%"
        )
        city_query = fabric_data.city.ilike(query_split[-1])
        state_query = fabric_data.state.ilike(query_split[-1])

        if len(query_split) >= 3:
            city_state_query = and_(
                fabric_data.city.ilike(query_split[-2]), fabric_data.state.ilike(query_split[-1])
            )

            results.extend(
                session.query(fabric_data)
                .filter(
                    primary_address_query, city_state_query, fabric_data.file_id.in_(all_files_ids)
                )
                .limit(1)
                .all()
            )

        if len(query_split) >= 2:
            if query_split[-1].upper() in states:
                results.extend(
                    session.query(fabric_data)
                    .filter(
                        primary_address_query, state_query, fabric_data.file_id.in_(all_files_ids)
                    )
                    .limit(3)
                    .all()
                )
            else:
                results.extend(
                    session.query(fabric_data)
                    .filter(
                        primary_address_query, city_query, fabric_data.file_id.in_(all_files_ids)
                    )
                    .limit(3)
                    .all()
                )

        simple_query = fabric_data.address_primary.ilike("%" + query + "%")
        results.extend(
            session.query(fabric_data)
            .filter(simple_query, fabric_data.file_id.in_(all_files_ids))
            .limit(5)
            .all()
        )

    results_dict = [
        {
            "address": result.address_primary,
            "city": result.city,
            "state": result.state,
            "zipcode": result.zip_code,
            "latitude": result.latitude,
            "longitude": result.longitude,
        }
        for result in results
    ]

    return results_dict
