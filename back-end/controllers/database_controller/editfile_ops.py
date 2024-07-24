import psycopg2
from database.sessions import ScopedSession, Session
from database.models import editfile, user, file_editfile_link
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


def get_editfiles_in_folder(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        files_in_folder = session.query(editfile).filter(editfile.folder_id == folderid).all()
        return files_in_folder
    finally:
        if owns_session:
            session.close()



def get_editfile_with_id(fileid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        file_with_id = session.query(editfile).filter(editfile.id == fileid).one()
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

def create_editfile(filename, content, folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_file = editfile(name=filename, data=content, folder_id=folderid, timestamp=datetime.now())
        session.add(new_file)
        if owns_session:
            session.commit()
        return new_file
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()

def get_editfilesinfo_in_folder(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        files_in_folder = get_editfiles_in_folder(folderid, session)
        if not files_in_folder:
            return []

        files_info = []
        for file in files_in_folder:

            file_dict = {
                'id': file.id,
                'name': file.name,
                'timestamp': file.timestamp,
                'folder_id': file.folder_id,
            }
            
            files_info.append(file_dict)

        return files_info
    finally:
        if owns_session:
            session.close()


def delete_editfile(editfileid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        editfile_to_del = session.query(editfile).filter(editfile.id == editfileid).first()
        if editfile_to_del:
            # Delete all associated file links first
            links = session.query(file_editfile_link).filter(file_editfile_link.editfile_id == editfileid).all()
            for link in links:
                session.delete(link)

            # Proceed to delete the editfile
            session.delete(editfile_to_del)
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



def editfile_belongs_to_organization(file_id, user_id, session):
    # Retrieve the user based on user_id
    userVal = session.query(user).filter(user.id == user_id).first()
    if not userVal:
        return False

    # Get the user's organization
    user_organization = userVal.organization
    if not user_organization:
        return False

    # Check if the file belongs to this organization
    fileVal = session.query(editfile).filter(editfile.id == file_id).first()
    if not fileVal:
        return False

    # Check if the file's folder belongs to the same organization
    folder = fileVal.folder
    if not folder:
        return False

    return folder.organization_id == user_organization.id


