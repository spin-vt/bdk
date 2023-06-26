import csv
from threading import Lock
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import concurrent.futures
import logging
from sqlalchemy import inspect
import os

logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
db_host = os.getenv('postgres', 'localhost')

NUMBER_THREADS = 8
BATCH_SIZE = 50000

Base = declarative_base()


class Data(Base):
    __tablename__ = 'Fabric'

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
    username = Column(String)

DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=0)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

inspector = inspect(engine)
if not inspector.has_table('Fabric'):
    Base.metadata.create_all(engine)

db_lock = Lock()


def check_num_records_greater_zero():
    session = Session()
    return session.query(Data).count() > 0


def process_rows(rows):
    session = Session()
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
            username = "vineet"

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
                longitude=longitude,
                username=username
            )
            batch.append(new_data)

            if len(batch) >= BATCH_SIZE:
                with db_lock:
                    session.bulk_save_objects(batch)
                    session.commit()
                batch = []

        if batch:
            with db_lock:
                session.bulk_save_objects(batch)
                session.commit()

    except Exception as e:
        logging.error(f"Error occurred while inserting data: {e}")

    finally:
        session.close()


def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


def open_and_read(file_name):
    with open(file_name, 'r') as file:
        csv_reader = csv.reader(file)
        next(csv_reader)
        all_rows = list(csv_reader)
        row_chunks = list(chunked(all_rows, 20000))
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUMBER_THREADS) as executor:
            futures = [executor.submit(process_rows, chunk) for chunk in row_chunks]
            concurrent.futures.wait(futures)