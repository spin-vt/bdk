import psycopg2
from database.sessions import ScopedSession, Session
from database.models import user, folder
from threading import Lock
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from .user_ops import get_user_with_id

def get_folder(userid, folderid=None):
    userVal = get_user_with_id(userid)
    session = Session()
    try:
        if not folderid:
            folderVal = session.query(folder).filter(folder.user_id == userVal.id).order_by(folder.id.desc()).first()
        else:
            folderVal = session.query(folder).filter(folder.id == folderid, folder.user_id == userid).one()

        return folderVal

    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given user ID or folder ID"
    except Exception as e:
        return str(e)
    finally:
        session.close()


def create_folder(foldername, userid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_folder = folder(name=foldername, user_id=userid)
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