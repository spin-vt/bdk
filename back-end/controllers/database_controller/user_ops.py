from database.models import user
from database.sessions import Session
from werkzeug.security import generate_password_hash
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from utils.logger_config import logger


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

def get_userinfo_with_id(userid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        userVal = session.query(user).filter(user.id == userid).one()
        if userVal.organization:
            organization_info = {
                'organization_name': userVal.organization.name,
                'provider_id': userVal.organization.provider_id,
                'brand_name': userVal.organization.brand_name
            }
        else:
            organization_info = None

        return {
            'id': userVal.id,
            'email': userVal.username,
            'verified': userVal.verified,
            'organization': organization_info
        }
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
        logger.debug(e)
        return str(e)
    finally:
        if owns_session:
            session.close()

def create_user_in_db(username, password, session):
    try:
        existing_user = get_user_with_username(username, session)
        if existing_user:
            return {"error": "Email already exists"}

        hashed_password = generate_password_hash(password, method='sha256')
        new_user = user(username=username, password=hashed_password)
        session.add(new_user)
    
        session.commit()

        return {"success": new_user}

    except Exception as e:
       
        session.rollback()
        return {"error": str(e)}


def verify_user_email(user_id, email, session, setVerified=False):
    try:
        userVal = session.query(user).filter(user.username == email, user.id == user_id).one()
        if userVal:
            if setVerified:
                userVal.verified = True
                session.commit()
            return True
        else:
            return False
    except Exception as e:
        session.rollback()
        logger.debug(e)
        return False

def reset_user_password(user_id, password):
    session = Session()
    try:
        userVal = session.query(user).filter(user.id == user_id).one()
        if userVal:
            hashed_password = generate_password_hash(password, method='sha256')
            userVal.password = hashed_password
            session.commit()
            
    except Exception as e:
        session.rollback()
        logger.debug(e)
    finally:
        session.close()

def add_user_to_organization(user_id, org_id, session):
    userVal = get_user_with_id(userid=user_id, session=session)
    if userVal:
        userVal.organization_id = org_id
        session.commit()
        return True
    return False