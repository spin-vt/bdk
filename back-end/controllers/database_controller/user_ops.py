from database.models import user
from sqlalchemy.exc import IntegrityError
from utils.settings import DATABASE_URL
from multiprocessing import Lock
from database.sessions import ScopedSession, Session
import psycopg2
from werkzeug.security import generate_password_hash
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

def get_user_with_id(userid):
    session = Session()
    try:
        userVal = session.query(user).filter(user.id == userid).one()
        return userVal
    
    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given user ID or folder ID"
    except Exception as e:
        return str(e)
    finally:
        session.close()
    

def get_user_with_username(user_name):
    session = Session()
    try:
        userVal = session.query(user).filter(user.username == user_name).one()
        return userVal
    except NoResultFound:
        return None
    except MultipleResultsFound:
        return "Multiple results found for the given user ID or folder ID"
    except Exception as e:
        return str(e)
    finally:
        session.close()

def create_user_in_db(username, password):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("SELECT username FROM \"user\" WHERE username = %s", (username,))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        conn.close()
        return None

    hashed_password = generate_password_hash(password, method='sha256')

    cursor.execute("INSERT INTO \"user\" (username, password) VALUES (%s, %s) RETURNING id", (username, hashed_password))
    new_user_id = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return new_user_id