import psycopg2
from database.sessions import ScopedSession, Session
from database.models import user, file, kml_data, file_editfile_link
from threading import Lock
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
import re
import os
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

db_lock = Lock()

def get_files_in_folder(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        files_in_folder = session.query(file).filter(file.folder_id == folderid).all()
        return files_in_folder
    finally:
        if owns_session:
            session.close()

# Similar changes for the other functions

def get_files_with_postfix(folderid, postfix, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        files_with_ending = session.query(file).filter(file.folder_id == folderid, file.name.endswith(postfix)).all()
        return files_with_ending
    finally:
        if owns_session:
            session.close()


def get_all_network_files_for_fileinfoedit_table(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        kml_files = get_files_with_postfix(folderid, '.kml', session)
        geojson_files = get_files_with_postfix(folderid, '.geojson', session)
        return kml_files + geojson_files
    finally:
        if owns_session:
            session.close()

def get_files_by_type(folderid, filetype, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        files_with_type = session.query(file).filter(file.folder_id == folderid, file.type == filetype).all()
        return files_with_type
    except NoResultFound:
        return None
    except SQLAlchemyError as e:
        print(f"Error occurred during query: {str(e)}")
        return None
    finally:
        if owns_session:
            session.close()


def get_files_with_prefix(folderid, prefix, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        files_with_ending = session.query(file).filter(file.folder_id == folderid, file.name.startswith(prefix)).all()
        return files_with_ending
    except NoResultFound:
        return None
    except SQLAlchemyError as e:
        print(f"Error occurred during query: {str(e)}")
        return None
    finally:
        if owns_session:
            session.close()

def get_file_with_id(fileid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        file_with_id = session.query(file).filter(file.id == fileid).one()
        return file_with_id
    except NoResultFound:
        return None
    except MultipleResultsFound:
        print(f"Multiple files found with the same id: {fileid}")
        return None
    except SQLAlchemyError as e:
        print(f"Error occurred during query: {str(e)}")
        return None
    finally:
        if owns_session:
            session.close()

def get_file_with_name(filename, folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        existing_file = session.query(file).filter(file.name == filename, file.folder_id == folderid).first()
        return existing_file
    except NoResultFound:
        return None
    except MultipleResultsFound:
        print(f"Multiple files found with the same name: {filename}")
        return None
    except SQLAlchemyError as e:
        print(f"Error occurred during query: {str(e)}")
        return None
    finally:
        if owns_session:
            session.close()


def create_file(filename, content, folderid, filetype=None, maxDownloadSpeed=None, maxUploadSpeed=None, techType=None, latency=None, category=None, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_file = file(name=filename, data=content, folder_id=folderid, timestamp=datetime.now(), type=filetype, maxDownloadSpeed=maxDownloadSpeed, maxUploadSpeed=maxUploadSpeed, techType=techType, latency=latency, category=category)
        session.add(new_file)
        if owns_session:
            session.commit()
        return new_file
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()

def update_file_type(file_id, filetype, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    if filetype is None:
        return {"error": "File type not provided"}

    try:
        file_to_update = session.query(file).filter(file.id == file_id).first()
        if file_to_update is None:
            return {"error": "File not found"}

        file_to_update.type = filetype
        if owns_session:
            session.commit()

        return {"success": "File type updated successfully"}
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()
        return {"error": str(e)}

#pass in a folderid
def get_filesinfo_in_folder(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        files_in_folder = get_files_in_folder(folderid, session)
        if not files_in_folder:
            return None

        files_info = []
        for file in files_in_folder:

            file_dict = {
                'id': file.id,
                'name': file.name,
                'timestamp': file.timestamp,
                'folder_id': file.folder_id,
                'type': file.type,
                'kml_data': None
            }
            
            files_info.append(file_dict)

        return files_info
    finally:
        if owns_session:
            session.close()

def delete_file(fileid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        file_to_del = get_file_with_id(fileid, session)
        file_to_del = get_file_with_id(fileid, session)
        if file_to_del:
            # Delete all associated editfile links first
            links = session.query(file_editfile_link).filter(file_editfile_link.file_id == fileid).all()
            for link in links:
                session.delete(link)

            # Proceed to delete the file
            session.delete(file_to_del)
            if owns_session:
                session.commit()


    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()
        print(f"Error occurred during deletion: {str(e)}")
        raise
    finally:
        if owns_session:
            session.close()


def file_belongs_to_organization(file_id, user_id, session):
    # Retrieve the user based on user_id
    userVal = session.query(user).filter(user.id == user_id).first()
    if not userVal:
        return False

    # Get the user's organization
    organization = userVal.organization
    if not organization:
        return False

    # Check if the file belongs to this organization
    fileVal = session.query(file).filter(file.id == file_id).first()
    if not fileVal:
        return False

    # Check if the file's folder belongs to the same organization
    folder = fileVal.folder
    if not folder:
        return False

    return folder.user.organization_id == organization.id
