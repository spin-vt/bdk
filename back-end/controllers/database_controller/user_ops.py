from database.models import user
from sqlalchemy.exc import IntegrityError
from utils.settings import DATABASE_URL
from multiprocessing import Lock
from database.sessions import ScopedSession, Session
import psycopg2
from werkzeug.security import generate_password_hash
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

def get_user_with_id(userid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        userVal = session.query(user).filter(user.id == userid).one()
        return userVal
    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given user ID"
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()

def get_user_with_username(user_name, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        userVal = session.query(user).filter(user.username == user_name).one()
        return userVal
    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given username"
    except Exception as e:
        return str(e)
    finally:
        if owns_session:
            session.close()

def create_user_in_db(username, password, providerid, brandname):
    session = Session()
    try:
        existing_user = get_user_with_username(username, session)
        if existing_user:
            return {"error": "Username already exists"}

        hashed_password = generate_password_hash(password, method='sha256')
        new_user = user(username=username, password=hashed_password, provider_id=providerid, brand_name=brandname)
        session.add(new_user)
    
        session.commit()

        return {"success": new_user.id}

    except Exception as e:
       
        session.rollback()
        return {"error": str(e)}

    finally:
        session.close()