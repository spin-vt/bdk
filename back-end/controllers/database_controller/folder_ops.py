import psycopg2
from database.sessions import ScopedSession, Session
from database.models import user, folder
from threading import Lock
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from .user_ops import get_user_with_id

def get_export_folder(userid, folderid=None, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        # Query to retrieve the last folder of type 'upload' for the given user
        if not folderid:
            folderVal = (session.query(folder)
                        .filter(folder.user_id == userid, folder.type == "export")
                        .order_by(folder.id.desc())
                        .first())
        else:
            folderVal = session.query(folder).filter(folder.id == folderid, folder.user_id == userid).one()
        return folderVal

    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given user ID"
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()

def get_upload_folder(userid, folderid=None, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        # Query to retrieve the last folder of type 'upload' for the given user
        if not folderid:
            folderVal = (session.query(folder)
                        .filter(folder.user_id == userid, folder.type == "upload")
                        .order_by(folder.id.desc())
                        .first())
        else:
            folderVal = session.query(folder).filter(folder.id == folderid, folder.user_id == userid).one()
        return folderVal

    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given user ID"
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()

def create_folder(foldername, userid, filingDeadline, foldertype, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_folder = folder(name=foldername, user_id=userid, deadline = filingDeadline, type=foldertype)
        session.add(new_folder)
        if owns_session:
            session.commit()
        return new_folder
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()
        return "An error occurred while creating the folder: " + str(e)
    finally:
        if owns_session:
            session.close()

def get_number_of_folders_for_user(userid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        count = session.query(folder).filter(folder.user_id == userid).count()
        return count
    except Exception as e:
        return -1
    finally:
        if owns_session:
            session.close()

def get_folders_by_type_for_user(userid, foldertype, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        folders = session.query(folder).filter(folder.user_id == userid, folder.type == foldertype).all()
        return folders

    except NoResultFound:
        return None
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()


def delete_folder(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        folder_to_delete = session.query(folder).filter(folder.id == folderid).one()
        print(f'folder id is {folder_to_delete.id}', flush=True)
        session.delete(folder_to_delete)
        if owns_session:
            session.commit()

        return True

    except NoResultFound:
        return "Folder not found or unauthorized access"
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()
        return "An error occurred while deleting the folder: " + str(e)
    finally:
        if owns_session:
            session.close()