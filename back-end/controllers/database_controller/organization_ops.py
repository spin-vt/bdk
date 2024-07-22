from database.models import organization, user
from database.sessions import Session
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from utils.logger_config import logger


def get_organization_with_orgname(org_name, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        orgVal = session.query(organization).filter(organization.name == org_name).one()
        return orgVal
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

def create_organization(org_name, session):
    try:
        new_org = organization(name=org_name)
        session.add(new_org)
        session.commit()
        return new_org

    except Exception as e:
        
        session.rollback()
        return {'error': e}
    
def get_admin_user_for_organization(org_id, session):
    try:
        admin = session.query(user).filter_by(organization_id=org_id, is_admin=True).first()
        return admin
    except NoResultFound:
        return None
    except Exception as e:
        logger.debug(e)
        return str(e)