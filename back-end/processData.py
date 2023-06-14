import csv
from threading import Lock
from sqlalchemy import Column, Integer, String, Float
from flask_sqlalchemy import SQLAlchemy
import concurrent.futures
import logging

logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

NUMBER_THREADS = 4
BATCH_SIZE = 50000

db = SQLAlchemy()

class Data(db.Model):
    __tablename__ = 'bdk'

    location_id = Column(Integer, primary_key=True)
    address_primary = Column(String)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    zip_suffix = Column(String)
    unit_count = Column(Integer)
    bsl_flag = Column(String)
    building_type_code = Column(String)
    land_use_code = Column(Integer)
    address_confidence_code = Column(String)
    country_geoid = Column(String)
    block_geoid = Column(String)
    h3_9 = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)

db_lock = Lock()


def check_num_records_greater_zero():
    session = Session()
    return session.query(Data).count() > 0


def process_rows(rows):
    batch = []

    try:
        for row in rows:
            location_id = int(row[0])
            address_primary = row[1] if row[1] != '' else None
            city = row[2] if row[2] != '' else None
            state = row[3] if row[3] != '' else None
            zip_code = row[4] if row[4] != '' else None
            zip_suffix = row[5] if row[5] != '' else None
            unit_count = int(row[6]) if row[6] != '' else None
            bsl_flag = row[7] if row[7] != '' else None
            building_type_code = row[8] if row[8] != '' else None
            land_use_code = int(row[9]) if row[9] != '' else None
            address_confidence_code = (row[10]) if row[10] != '' else None
            country_geoid = str(row[11]) if row[11] != '' else None
            block_geoid = row[12] if row[12] != '' else None
            h3_9 = row[13] if row[13] != '' else None
            latitude = float(row[14]) if row[14] != '' else None
            longitude = float(row[15]) if row[15] != '' else None

            new_data = Data(
                location_id=location_id,
                address_primary=address_primary,
                city=city,
                state=state,
                zip_code=zip_code,
                zip_suffix=zip_suffix,
                unit_count=unit_count,
                bsl_flag=bsl_flag,
                building_type_code=building_type_code,
                land_use_code=land_use_code,
                address_confidence_code=address_confidence_code,
                country_geoid=country_geoid,
                block_geoid=block_geoid,
                h3_9=h3_9,
                latitude=latitude,
                longitude=longitude
            )
            batch.append(new_data)

            if len(batch) >= BATCH_SIZE:
                with db_lock:
                    db.session.bulk_save_objects(batch)
                    db.session.commit()
                batch = []

        if batch:
            with db_lock:
                db.session.bulk_save_objects(batch)
                db.session.commit()

    except Exception as e:
        logging.error(f"Error occurred while inserting data: {e}")

    finally:
        db.session.close()


def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


def open_and_read(file_name):
    with open(file_name, 'r') as file:
        csv_reader = csv.reader(file)
        next(csv_reader)
        all_rows = list(csv_reader)
        row_chunks = list(chunked(all_rows, 20000))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_rows, chunk) for chunk in row_chunks]
            concurrent.futures.wait(futures)
