from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, select, text
from sqlalchemy.sql import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from processData import Data

Base = declarative_base()

class kml_data(Base):
    __tablename__ = 'kml'
    location_id = Column(Integer, primary_key=True)
    served = Column(Boolean)

DATABASE_URL = 'postgresql://postgres:db123@localhost:5432/postgres'

engine = create_engine(DATABASE_URL)
# Create a session to interact with the database
Session = sessionmaker(bind=engine)
session = Session()

def get_points_within_box(min_lat, min_lng, max_lat, max_lng):
    query = text("SELECT bdk.location_id, bdk.latitude, bdk.longitude, bdk.address_primary, kml.served FROM bdk LEFT JOIN kml ON bdk.location_id = kml.location_id WHERE bdk.latitude BETWEEN :min_lat AND :max_lat AND bdk.longitude BETWEEN :min_lng AND :max_lng")
    points = session.execute(query, {"min_lat": min_lat, "max_lat": max_lat, "min_lng": min_lng, "max_lng": max_lng})

    return [{
        'location_id': point.location_id,
        'lat': point.latitude,
        'lng': point.longitude,
        'address': point.address_primary,
        'served': point.served
    } for point in points]
