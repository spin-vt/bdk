from database.models import user
from database.sessions import Session
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

def change_user_in_db(username, provider_id, brandname, new_password): 
    session = Session() 
    try: 
        user = get_user_with_username(username, session)
        
        if user.username != username or user.provider_id != int(provider_id) or user.brand_name != str(brandname): 
            return {"error": "Username, provider id, or brand name does not match"}
        
        
        hashed_pwd = generate_password_hash(new_password, method='sha256')
        user.password = hashed_pwd
        session.commit() 

        return {"success": user.id}
    except Exception as e: 
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close() 
        
            
