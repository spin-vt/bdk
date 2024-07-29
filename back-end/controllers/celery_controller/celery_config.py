from celery import Celery, signals
from utils.config import Config
from database.sessions import Session
from database.models import celerytaskinfo
from datetime import datetime
from sqlalchemy.exc import OperationalError
import time

MAX_RETRIES = 5 
RETRY_DELAY = 1  # Initial delay in seconds

def make_celery():
    celery = Celery(__name__,
                    backend=Config.CELERY_RESULT_BACKEND,
                    broker=Config.CELERY_BROKER_URL,
                    include=['controllers.celery_controller.celery_tasks'])
    celery.conf.update(
        # Any specific Celery configuration options
    )
    return celery

celery = make_celery()


@signals.task_postrun.connect
def task_postrun_handler(task_id, **kwargs):
    session = Session()
    retries = 0
    try:
        task = session.query(celerytaskinfo).filter(celerytaskinfo.task_id==task_id).first()
        if task:
            task.status = kwargs['state']
            task.result = str(kwargs['retval'])
            end_time = datetime.now()
            runtime = (end_time - task.start_time).total_seconds() if task.start_time else None
            task.runtime = runtime
            session.commit()
    except OperationalError as e:
        if session:
            session.rollback()
        while retries <= MAX_RETRIES:
            time.sleep(RETRY_DELAY * (2 * retries))
            retries += 1
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
# app = Flask(__name__)
# CORS(app)
# You can adjust this to switch between environments as needed
# celery = Celery(app.name, broker='redis://localhost:6379/0', include=['celery_setup.celery_tasks'])
# app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
# celery.conf.update(app.config)
