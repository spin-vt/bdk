from sqlalchemy import Column, Integer, Float, Boolean, String, LargeBinary, DateTime
from sqlalchemy import Column, Integer, String, Float
from database.base import Base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class Data(Base):
    __tablename__ = 'fabric'
    
    # id = Column(Integer, primary_key=True, autoincrement=True)
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
    user_id = Column(Integer, ForeignKey('user.id'))  # add this line to establish a foreign key
    user = relationship('user', backref='Data')  # add this line to define a relationship

class Data_temp(Base):
    __tablename__ = 'fabric_temp'
    
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
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(Integer)
    served = Column(Boolean)
    wireless = Column(Boolean)
    lte = Column(Boolean)
    username = Column(String)
    coveredLocations = Column(String)
    maxDownloadNetwork = Column(String)
    maxDownloadSpeed = Column(Integer)
    user_id = Column(Integer, ForeignKey('user.id'))  # add this line to establish a foreign key
    user = relationship('user', backref='kml_data')  # add this line to define a relationship

class vector_tiles(Base):
    __tablename__ = 'vt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    zoom_level = Column(Integer)  
    tile_column = Column(Integer) 
    tile_row = Column(Integer)
    tile_data = Column(LargeBinary)
    user_id = Column(Integer, ForeignKey('user.id'))  # add this line to establish a foreign key
    mbt_id = Column(Integer, ForeignKey('mbt.id'))  # change 'mbt.id' to 'mbtiles.id'
    user = relationship('user', back_populates='vector_tiles')  # add this line
    mbtiles = relationship('mbtiles', back_populates='vector_tiles')  # add this line

class user(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    password = Column(String(256))
    vector_tiles = relationship('vector_tiles', back_populates='user')
    mbtiles = relationship('mbtiles', back_populates='user')  # change backref to back_populates

class mbtiles(Base):
    __tablename__ = 'mbt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tile_data = Column(LargeBinary)
    filename = Column(String)  # this will add a filename column
    timestamp = Column(DateTime)  # this will add a timestamp column
    user_id = Column(Integer, ForeignKey('user.id'))  # add this line to establish a foreign key
    user = relationship('user', back_populates='mbtiles')  # add this line
    vector_tiles = relationship('vector_tiles', back_populates='mbtiles')  # add this line to define a relationship, change 'vt' to 'vector_tiles'

class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    file_name = Column(String, nullable=False)
    data = Column(LargeBinary, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))  # add this line to establish a foreign key
    user = relationship('user', backref='File')  # add this line to define a relationship


    