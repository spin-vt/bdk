import csv
from io import StringIO
from sqlalchemy import create_engine, text
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float
import os

Base = declarative_base()

class Data(Base):
    __tablename__ = 'fabric'

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

db_host = os.getenv('postgres', 'localhost')
DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'

engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=0)
Base.metadata.create_all(engine)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_num_records_greater_zero():
    session = Session()
    return session.query(Data).count() > 0

def write_to_db(fileName): 
    csv_file = fileName

    with open(csv_file, 'r') as file:
        csv_data = file.read()

    engine = create_engine('postgresql://postgres:db123@localhost:5432/postgres')

    connection = engine.raw_connection()
    try:
        with connection.cursor() as cur:
            output = StringIO(csv_data)
            cur.copy_expert("COPY fabric FROM STDIN CSV HEADER DELIMITER ','", output)
            output.seek(0)
        connection.commit()
    finally:
        connection.close()
