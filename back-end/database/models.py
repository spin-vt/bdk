from sqlalchemy import Column, Integer, Float, Boolean, String, LargeBinary, DateTime, JSON, Date
from database.base import Base
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

class user(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    password = Column(String(256))
    provider_id = Column(Integer)
    brand_name = Column(String(50))
    folders = relationship('folder', back_populates='user', cascade='all, delete')
    towers = relationship('tower', back_populates='user', cascade='all, delete')

class tower(Base):
    __tablename__ = 'tower'

    id = Column(Integer, primary_key=True)
    tower_name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)

    # Relationship to TowerInfo and RasterData models (assuming they exist)
    user = relationship('user', back_populates='towers')
    tower_info = relationship('towerinfo', back_populates='tower', uselist=False, cascade='all, delete')
    raster_data = relationship('rasterdata', back_populates='tower', uselist=False, cascade='all, delete')

class towerinfo(Base):
    __tablename__ = 'towerinfo'

    id = Column(Integer, primary_key=True)
    latitude = Column(String)
    longitude = Column(String)
    frequency = Column(String)
    radius = Column(String)
    antennaHeight = Column(String)
    antennaTilt = Column(String)
    horizontalFacing = Column(String)
    floorLossRate = Column(String)
    
    # One-to-one relationship with Tower
    tower_id = Column(Integer, ForeignKey('tower.id', ondelete='CASCADE'))
    tower = relationship('tower', back_populates='tower_info', uselist=False)

class rasterdata(Base):
    __tablename__ = 'rasterdata'

    id = Column(Integer, primary_key=True)
    image_data = Column(LargeBinary)  # for storing binary image data
    transparent_image_data = Column(LargeBinary)
    loss_color_mapping = Column(JSON)
    north_bound = Column(String)
    south_bound = Column(String)
    east_bound = Column(String)
    west_bound = Column(String)
    
    # One-to-one relationship with Tower
    tower_id = Column(Integer, ForeignKey('tower.id', ondelete='CASCADE'))
    tower = relationship('tower', back_populates='raster_data', uselist=False)

class folder(Base): #filing, will change the name later for less confusion when reading
    __tablename__ = 'folder'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, default='upload') # Currently upload or export
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'))
    user = relationship('user', back_populates='folders')
    deadline = Column(Date) #This deadline makes it a filing for the current period
    files = relationship('file', back_populates='folder', cascade='all, delete')
    mbtiles = relationship('mbtiles', back_populates='folder', cascade='all, delete')
    kmzs = relationship('kmz', back_populates='folder', cascade='all, delete')


    def copy(self, session, name=None, type=None):
        name = name if name is not None else self.name
        type = type if type is not None else self.type
        new_folder = folder(name=name, type=type, user_id=self.user_id)
        session.add(new_folder)
        session.flush()  # To generate an ID for the new folder
        
        # Copy related files, mbtiles, and kmzs
        for file in self.files:
            file.copy(session=session, new_folder_id=new_folder.id)
        for mbtile in self.mbtiles:
            mbtile.copy(session=session, new_folder_id=new_folder.id)
        for kmz in self.kmzs:
            kmz.copy(session=session, new_folder_id=new_folder.id)

        return new_folder

class kmz(Base):
    __tablename__ = 'kmz'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'))
    kml_files = relationship('file', back_populates='kmz', cascade='all, delete')  # Assuming kml_data is your KML model
    folder = relationship('folder', back_populates='kmzs')  # Add this new back_populates to your Folder model
    def copy(self, session, new_folder_id):
        new_kmz = kmz(name=self.name, folder_id=new_folder_id)
        session.add(new_kmz)
        session.flush()
        
        for kml_file in self.kml_files:
            kml_file.copy(session=session, new_kmz_id=new_kmz.id, new_folder_id=new_folder_id)

        return new_kmz

class file(Base):
    __tablename__ = 'file'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    data = Column(LargeBinary)
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'))
    kmz_id = Column(Integer, ForeignKey('kmz.id', ondelete='CASCADE'), nullable=True)
    timestamp = Column(DateTime)  # this will add a timestamp column
    type = Column(String)
    computed = Column(Boolean, default=False)
    kmz = relationship('kmz', back_populates='kml_files')
    folder = relationship('folder', back_populates='files')
    fabric_data = relationship('fabric_data', back_populates='file', cascade='all, delete')  # Use fabric_data instead of data_entries
    kml_data = relationship('kml_data', back_populates='file', cascade='all, delete')

    def copy(self, session, new_kmz_id=None, new_folder_id=None):
        new_file = file(name=self.name, 
                        data=self.data, 
                        folder_id=new_folder_id, 
                        kmz_id=new_kmz_id, 
                        timestamp=datetime.now(), 
                        type=self.type, 
                        computed=self.computed)
        session.add(new_file)
        session.flush()
        
        fabric_data_copies = []
        for fabric_entry in self.fabric_data:
            fabric_data_copy = {
                "location_id":fabric_entry.location_id,
                "address_primary" : fabric_entry.address_primary,
                "city" : fabric_entry.city,
                "state" : fabric_entry.state,
                "zip_code" : fabric_entry.zip_code,
                "zip_suffix" : fabric_entry.zip_suffix,
                "unit_count" : fabric_entry.unit_count,
                "bsl_flag" : fabric_entry.bsl_flag,
                "building_type_code" : fabric_entry.building_type_code,
                "land_use_code" : fabric_entry.land_use_code,
                "address_confidence_code" : fabric_entry.address_confidence_code,
                "country_geoid" : fabric_entry.country_geoid,
                "block_geoid" : fabric_entry.block_geoid,
                "h3_9" : fabric_entry.h3_9,
                "latitude" : fabric_entry.latitude,
                "longitude" : fabric_entry.longitude,
                "fcc_rel" : fabric_entry.fcc_rel,
                "file_id" : new_file.id
            }
            fabric_data_copies.append(fabric_data_copy)

        kml_data_copies = []
        for kml_entry in self.kml_data:
            kml_data_copy = {
                "location_id":kml_entry.location_id,
                "served" : kml_entry.served,
                "wireless" : kml_entry.wireless,
                "lte" : kml_entry.lte,
                "username" : kml_entry.username,
                "coveredLocations" : kml_entry.coveredLocations,
                "maxDownloadNetwork" : kml_entry.maxDownloadNetwork,
                "maxDownloadSpeed" : kml_entry.maxDownloadSpeed,
                "maxUploadSpeed" : kml_entry.maxUploadSpeed,
                "techType" : kml_entry.techType,
                "address_primary" : kml_entry.address_primary,
                "longitude" : kml_entry.longitude,
                "latitude" : kml_entry.latitude,
                "latency" : kml_entry.latency,
                "category" : kml_entry.category,
                "file_id": new_file.id
            }
            kml_data_copies.append(kml_data_copy)

        session.bulk_insert_mappings(fabric_data, fabric_data_copies)
        session.bulk_insert_mappings(kml_data, kml_data_copies)

        return new_file

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
    fcc_rel = Column(String)
    file_id = Column(Integer, ForeignKey('file.id', ondelete='CASCADE'))
    id = Column(Integer, primary_key=True, autoincrement=True)  # Unique primary key
    file = relationship('file', back_populates='fabric_data')

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
    fcc_rel = Column(String)

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
    address_primary = Column(String)
    longitude = Column(Float)
    latitude = Column(Float)
    latency = Column(Integer)
    category = Column(String)


class mbtiles(Base):
    __tablename__ = 'mbtiles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tile_data = Column(LargeBinary)
    filename = Column(String)
    timestamp = Column(DateTime)
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'))
    folder = relationship('folder', back_populates='mbtiles')
    vector_tiles = relationship('vector_tiles', back_populates='mbtiles', cascade='all, delete')

    def copy(self, session, new_folder_id):
        new_mbtile = mbtiles(filename=self.filename, 
                              tile_data=self.tile_data, 
                              timestamp=datetime.now(), 
                              folder_id=new_folder_id)
        session.add(new_mbtile)
        session.flush()

        vector_tile_copies = []
        for vector_tile in self.vector_tiles:
            vector_tile_copy = {
                "zoom_level" : vector_tile.zoom_level,
                "tile_column" : vector_tile.tile_column,
                "tile_row" : vector_tile.tile_row,
                "tile_data" : vector_tile.tile_data,
                "mbtiles_id" : new_mbtile.id
            }
            vector_tile_copies.append(vector_tile_copy)
        session.bulk_insert_mappings(vector_tiles, vector_tile_copies)

class vector_tiles(Base):
    __tablename__ = 'vector_tiles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    zoom_level = Column(Integer)  
    tile_column = Column(Integer) 
    tile_row = Column(Integer)
    tile_data = Column(LargeBinary)
    mbtiles_id = Column(Integer, ForeignKey('mbtiles.id', ondelete='CASCADE'))
    mbtiles = relationship('mbtiles', back_populates='vector_tiles')

class ChallengeLocations(Base):
    __tablename__ = 'challenge_locations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    #these should be modified to store the correct data type in the future
    address = Column(String)
    primary_city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    zip_code_suffix = Column(String)
    unit_count = Column(String)
    building_type_code = Column(String)
    non_bsl_code = Column(String)
    bsl_lacks_address_flag = Column(String) 
    latitude = Column(String)   
    longitude = Column(String)
    address_id = Column(String)
    contact_name = Column(String)
    contact_email = Column(String)
    contact_phone = Column(String)
    category_code = Column(String)
    location_id = Column(String)
