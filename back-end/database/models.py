from sqlalchemy import Column, Integer, Float, Boolean, String, LargeBinary, DateTime
from sqlalchemy import Column, Integer, String, Float
from .base import Base

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

class kml_data(Base):
    __tablename__ = 'KML'
    location_id = Column(Integer, primary_key=True)
    served = Column(Boolean)
    wireless = Column(Boolean)
    lte = Column(Boolean)
    username = Column(String)
    coveredLocations = Column(String)
    maxDownloadNetwork = Column(String)
    maxDownloadSpeed = Column(Integer)


class vector_tiles(Base):
    __tablename__ = 'vt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    zoom_level = Column(Integer)  
    tile_column = Column(Integer) 
    tile_row = Column(Integer)
    tile_data = Column(LargeBinary)

class mbtiles(Base):
    __tablename__ = 'mbt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tile_data = Column(LargeBinary)
    filename = Column(String)  # this will add a filename column
    timestamp = Column(DateTime)  # this will add a timestamp column

class user(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    password = Column(String(256))

class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    file_name = Column(String, nullable=False)
    data = Column(LargeBinary, nullable=False)


    