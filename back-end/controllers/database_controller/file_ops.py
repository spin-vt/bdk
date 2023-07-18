import psycopg2
from database.sessions import ScopedSession, Session
from database.models import file
from threading import Lock
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound

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

def get_files_with_prefix(folderid, prefix, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        files_with_ending = session.query(file).filter(file.folder_id == folderid, file.name.startswith(prefix)).all()
        return files_with_ending
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


def create_file(filename, content, folderid, filetype=None, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_file = file(name=filename, data=content, folder_id=folderid, timestamp=datetime.now(), type=filetype)
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
                'computed': file.computed,
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
        if file_to_del:
            session.delete(file_to_del)
            if owns_session:
                session.commit()
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()
        print(f"Error occurred during deletion: {str(e)}")
    finally:
        if owns_session:
            session.close()

