from database.models import user
from sqlalchemy.exc import IntegrityError
from utils.settings import DATABASE_URL
from multiprocessing import Lock
from database.sessions import ScopedSession, Session
import psycopg2, sys
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

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

def updatePassword(username, password):
    session = Session()
    existing_user = get_user_with_username(username, session)
    
    hashed_password = generate_password_hash(password, method='sha256')
    
    if existing_user:
        # if user exists, update the password
        if isinstance(existing_user, str):  # To handle "Multiple results found" error
            return {"error": existing_user}
        
        existing_user.password = hashed_password
        message = {"success": f"Password updated for user {existing_user.id}"}
    else:
        return "user doesn't exist"

    session.commit()
    session.close()
    return message

if __name__ == "__main__":
    # sys.argv[0] is always the name of the script itself.
    # sys.argv[1] will be the first argument after the script name, and so on.
    if len(sys.argv) != 3:
        print("Usage: python3 ./updateUserPassword <username> <newPassword>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    
    updatePassword(username, password)