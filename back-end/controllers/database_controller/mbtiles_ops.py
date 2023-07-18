from database.sessions import ScopedSession, Session
from database.models import mbtiles
from threading import Lock
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound


def get_latest_mbtiles(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        latest_mbtiles_with_postfix = (session.query(mbtiles)
                                    .filter(mbtiles.folder_id == folderid)
                                    .order_by(mbtiles.timestamp.desc())
                                    .first())
        return latest_mbtiles_with_postfix
    except NoResultFound:
        return None
    except SQLAlchemyError as e:
        print(f"Error occurred during query: {str(e)}")
        return None
    finally:
        if owns_session:
            session.close()

def delete_mbtiles(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        mbtiles_files = (session.query(mbtiles).filter(mbtiles.folder_id == folderid).all())
        for mbtiles_f in mbtiles_files:
            session.delete(mbtiles_f)
        if owns_session:
            session.commit()

    except NoResultFound:
        print("No result found")
    except SQLAlchemyError as e:
        print(f"Error occurred during query: {str(e)}")
    finally:
        if owns_session:
            session.close()