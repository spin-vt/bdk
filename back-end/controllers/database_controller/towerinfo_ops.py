from sqlalchemy.exc import SQLAlchemyError

from database.models import towerinfo
from database.sessions import Session


def create_towerinfo(tower_info_data, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_towerinfo = towerinfo(**tower_info_data)
        session.add(new_towerinfo)
        if owns_session:
            session.commit()
        return new_towerinfo
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()
        return "An error occurred while creating the towerinfo: " + str(e)
    finally:
        if owns_session:
            session.close()
