from database.sessions import Session
from database.models import user, tower
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError

def create_tower(towername, userid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        towerVal = get_tower_with_towername(tower_name=towername, user_id=userid, session=session)
        if towerVal and not isinstance(towerVal, str):
            if towerVal.tower_info:
                session.delete(towerVal.tower_info)
            if towerVal.raster_data:
                session.delete(towerVal.raster_data)
            # No need to return here if you just want to update the tower
        else:
            towerVal = tower(tower_name=towername, user_id=userid)  # Make sure the class name is correct
            session.add(towerVal)

        if owns_session:
            session.commit()
            session.refresh(towerVal)  # Refresh the object to ensure the ID is fetched
            # tower_id = towerVal.id  # Now you have the ID
            session.close()    
        return towerVal  # Returning the ID after closing the session

    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()
            session.close()
        return "An error occurred while creating the tower: " + str(e)
    
def get_tower_with_towername(tower_name, user_id, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        towerVal = session.query(tower).filter(tower.tower_name == tower_name, tower.user_id == user_id).one()
        return towerVal
    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given tower name and user"
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()