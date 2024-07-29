import psycopg2
from database.sessions import ScopedSession, Session
from database.models import user, folder
from threading import Lock
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from .user_ops import get_user_with_id

def get_export_folder(orgid, folderid=None, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        # Query to retrieve the last folder of type 'upload' for the given org
        if not folderid:
            folderVal = (session.query(folder)
                        .filter(folder.organization_id == orgid, folder.type == "export")
                        .order_by(folder.id.desc())
                        .first())
        else:
            folderVal = session.query(folder).filter(folder.id == folderid).one()
        return folderVal

    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given org ID"
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()

def get_upload_folder(orgid, folderid=None, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        # Query to retrieve the last folder of type 'upload' for the given org
        if not folderid:
            folderVal = (session.query(folder)
                        .filter(folder.organization_id == orgid, folder.type == "upload")
                        .order_by(folder.id.desc())
                        .first())
        else:
            folderVal = session.query(folder).filter(folder.id == folderid).one()
        return folderVal

    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given org ID"
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()

def get_folder_with_id(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        folderVal = session.query(folder).filter(folder.id == folderid).one()
        return folderVal

    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given org ID"
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()

def get_folders_by_type_for_org(orgid, foldertype, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        folders = session.query(folder).filter(folder.organization_id == orgid, folder.type == foldertype).all()
        return folders

    except NoResultFound:
        return None
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()


def create_folder(foldername, orgid, filingDeadline, foldertype, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_folder = folder(name=foldername, organization_id=orgid, deadline=filingDeadline, type=foldertype)
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

def get_number_of_folders_for_org(orgid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        count = session.query(folder).filter(folder.organization_id == orgid).count()
        return count
    except Exception as e:
        return -1
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


def folder_belongs_to_organization(folder_id, user_id, session):

    # Retrieve the user based on user_id
    userVal = session.query(user).filter(user.id == user_id).first()
    if not userVal:
        return False

    # Get the user's organization
    user_organization = userVal.organization
    if not user_organization:
        return False

    # Check if the folder belongs to this organization
    folderVal = session.query(folder).filter(folder.id == folder_id).first()
    if not folderVal:
        return False

    return folderVal.organization_id == user_organization.id