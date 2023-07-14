from sqlalchemy import Column, Integer, Float, Boolean, String, LargeBinary, DateTime
from sqlalchemy import Column, Integer, String, Float
from database.base import Base
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

class user(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    password = Column(String(256))
    folders = relationship('folder', back_populates='user', cascade='all, delete')

class folder(Base):
    __tablename__ = 'folder'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'))
    user = relationship('user', back_populates='folders')
    files = relationship('file', back_populates='folder', cascade='all, delete')
    mbtiles = relationship('mbtiles', back_populates='folder', cascade='all, delete')

class file(Base):
    __tablename__ = 'file'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    data = Column(LargeBinary)
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'))
    timestamp = Column(DateTime)  # this will add a timestamp column
    computed = Column(Boolean, default=False)
    folder = relationship('folder', back_populates='files')
    fabric_data = relationship('fabric_data', back_populates='file', cascade='all, delete')  # Use fabric_data instead of data_entries
    kml_data = relationship('kml_data', back_populates='file', cascade='all, delete')

class fabric_data(Base):
    __tablename__ = 'fabric_data'
    location_id = Column(Integer)
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
    file_id = Column(Integer, ForeignKey('file.id', ondelete='CASCADE'))
    id = Column(Integer, primary_key=True, autoincrement=True)  # Unique primary key
    file = relationship('file', back_populates='fabric_data')

    # __table_args__ = (UniqueConstraint('location_id', 'user_id', name='location_user_uc'),)

class fabric_data_temp(Base):
    __tablename__ = 'fabric_data_temp'
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
    __tablename__ = 'kml_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(Integer)
    served = Column(Boolean)
    wireless = Column(Boolean)
    lte = Column(Boolean)
    username = Column(String)
    coveredLocations = Column(String)
    maxDownloadNetwork = Column(String)
    maxDownloadSpeed = Column(Integer)
    maxUploadSpeed = Column(Integer)
    techType = Column(String)
    file_id = Column(Integer, ForeignKey('file.id', ondelete='CASCADE'))
    file = relationship('file', back_populates='kml_data')

class mbtiles(Base):
    __tablename__ = 'mbtiles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tile_data = Column(LargeBinary)
    filename = Column(String)
    timestamp = Column(DateTime)
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'))
    folder = relationship('folder', back_populates='mbtiles')
    vector_tiles = relationship('vector_tiles', back_populates='mbtiles', cascade='all, delete')

class vector_tiles(Base):
    __tablename__ = 'vector_tiles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    zoom_level = Column(Integer)  
    tile_column = Column(Integer) 
    tile_row = Column(Integer)
    tile_data = Column(LargeBinary)
    mbtiles_id = Column(Integer, ForeignKey('mbtiles.id', ondelete='CASCADE'))
    mbtiles = relationship('mbtiles', back_populates='vector_tiles')
