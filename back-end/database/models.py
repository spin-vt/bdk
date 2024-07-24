from sqlalchemy import Column, Integer, Float, Boolean, String, LargeBinary, DateTime, JSON, Date, Table
from database.base import Base
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

class organization(Base):
    __tablename__ = 'organization'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    provider_id = Column(Integer)
    brand_name = Column(String(50))
    users = relationship('user', back_populates='organization')
    folders = relationship('folder', back_populates='organization', cascade='all, delete')
    towers = relationship('tower', back_populates='organization', cascade='all, delete')

class user(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(256))
    is_admin = Column(Boolean, default=False)
    verified = Column(Boolean, default=False)
    organization_id = Column(Integer, ForeignKey('organization.id'))
    organization = relationship('organization', back_populates='users')
    

class tower(Base):
    __tablename__ = 'tower'

    id = Column(Integer, primary_key=True)
    tower_name = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False)

    # Relationship to TowerInfo and RasterData models (assuming they exist)
    organization = relationship('organization', back_populates='towers')
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
    deadline = Column(Date) #This deadline makes it a filing for the current period
    organization_id = Column(Integer, ForeignKey('organization.id', ondelete='CASCADE'))
    organization = relationship('organization', back_populates='folders')
    files = relationship('file', back_populates='folder', cascade='all, delete')
    mbtiles = relationship('mbtiles', back_populates='folder', cascade='all, delete')
    editfiles = relationship('editfile', back_populates='folder', cascade='all,delete')

    def copy(self, session, export=True, name=None, type=None, deadline=None):
        name = name if name is not None else self.name
        type = type if type is not None else self.type
        new_folder = folder(name=name, type=type, organization_id=self.organization_id, deadline=deadline)
        session.add(new_folder)
        session.flush()  # To generate an ID for the new folder
        

        new_file_mapping = {}
        new_editfile_mapping = {}

        # Copy related files, mbtiles
        for file in self.files:
            if not export and file.name.endswith('.csv'):
                continue
            new_file = file.copy(session=session, new_folder_id=new_folder.id, export=export)
            new_file_mapping[file.id] = new_file.id
        for edit_file in self.editfiles:
            new_edit_file = edit_file.copy(session=session, new_folder_id=new_folder.id)
            new_editfile_mapping[edit_file.id] = new_edit_file.id
        
        # Only copy 
        if export:
            for mbtile in self.mbtiles:
                mbtile.copy(session=session, new_folder_id=new_folder.id)

        for file in self.files:
            for link in file.editfile_links:
                if link.editfile_id in new_editfile_mapping:  # Ensure the editfile was copied
                    new_link = file_editfile_link(
                        file_id=new_file_mapping[file.id],
                        editfile_id=new_editfile_mapping[link.editfile_id]
                    )
                    session.add(new_link)
        return new_folder

class file_editfile_link(Base):
    __tablename__ = 'file_editfile_link'
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('file.id', ondelete='CASCADE'))
    editfile_id = Column(Integer, ForeignKey('editfile.id', ondelete='CASCADE'))

    # Establishing the relationships with the 'file' and 'editfile' tables
    file = relationship("file", back_populates="editfile_links")
    editfile = relationship("editfile", back_populates="file_links")

class file(Base):
    __tablename__ = 'file'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    data = Column(LargeBinary)
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'))
    timestamp = Column(DateTime) 
    type = Column(String)
    maxDownloadSpeed = Column(Integer)
    maxUploadSpeed = Column(Integer)
    techType = Column(String)
    # techType = Column(Integer)
    latency = Column(String)
    # latency = Column(Integer)
    category = Column(String)
    computed = Column(Boolean, default=False)
    folder = relationship('folder', back_populates='files')
    fabric_data = relationship('fabric_data', back_populates='file', cascade='all, delete')  # Use fabric_data instead of data_entries
    kml_data = relationship('kml_data', back_populates='file', cascade='all, delete')
    editfile_links = relationship("file_editfile_link", back_populates="file")

    
    def copy(self, session, export, new_folder_id=None):
        new_file = file(name=self.name, 
                        data=self.data, 
                        folder_id=new_folder_id,
                        timestamp=datetime.now(), 
                        type=self.type,
                        maxDownloadSpeed=self.maxDownloadSpeed,
                        maxUploadSpeed=self.maxUploadSpeed,
                        techType=self.techType,
                        latency=self.latency,
                        category=self.category,
                        )
        session.add(new_file)
        session.flush()
        
        if export:
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
    

class editfile(Base):
    __tablename__ = 'editfile'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    data = Column(LargeBinary)
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'))
    timestamp = Column(DateTime) 
    folder = relationship('folder', back_populates='editfiles')
    file_links = relationship("file_editfile_link", back_populates="editfile")

    def copy(self, session, new_folder_id=None):
        new_edit_file = editfile(name=self.name, 
                        data=self.data, 
                        folder_id=new_folder_id,
                        timestamp=datetime.now(), 
                        )
        session.add(new_edit_file)
        session.flush()

        return new_edit_file

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
    coveredLocations = Column(String)
    maxDownloadNetwork = Column(String)
    maxDownloadSpeed = Column(Integer)
    maxUploadSpeed = Column(Integer)
    techType = Column(String)
    # techType = Column(Integer)
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
