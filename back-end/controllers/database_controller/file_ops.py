import psycopg2
from database.sessions import ScopedSession, Session
from database.models import file
from threading import Lock
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError

db_lock = Lock()

def get_files_in_folder(folderid):
    session = Session()

    try:
        files_in_folder = session.query(file).filter(file.folder_id == folderid).all()
        return files_in_folder

    except SQLAlchemyError as e:
        return "An error occurred while retrieving the files: " + str(e)
    finally:
        session.close()


def get_files_with_postfix(folderid, postfix):
    session = Session()

    try:
        files_with_ending = session.query(file).filter(file.folder_id == folderid, file.name.endswith(postfix)).all()
        return files_with_ending

    except SQLAlchemyError as e:
        return "An error occurred while retrieving the files: " + str(e)
    finally:
        session.close()


def get_file_with_id(fileid):
    session = Session()

    try:
        file_with_id = session.query(file).filter(file.id == fileid).one()
        return file_with_id

    except NoResultFound:
        return "No result found for the given file ID"
    except MultipleResultsFound:
        return "Multiple results found for the given file ID"
    except Exception as e:
        return str(e)
    finally:
        session.close()


def get_file_with_name(filename, folderid):
    session = Session()

    try:
        existing_file = session.query(file).filter(file.name == filename, file.folder_id == folderid).first()
        return existing_file

    except SQLAlchemyError as e:
        return "An error occurred while retrieving the file: " + str(e)
    finally:
        session.close()


def create_file(filename, content, folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_file = file(name=filename, data=content, folder_id=folderid, timestamp=datetime.now())
        session.add(new_file)
        if owns_session:
            session.commit()
        return new_file
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()

def get_filesinfo_in_folder(folderid):
    files_in_folder = get_files_in_folder(folderid)

    if not files_in_folder:
        return None

    files_info = []
    for file in files_in_folder:
        file_dict = {
            'id': file.id,
            'name': file.name,
            'timestamp': file.timestamp,
            'folder_id': file.folder_id,
            'computed': file.computed,
            # You can add any other attributes you want to return here.
        }
        files_info.append(file_dict)
    
    return files_info
