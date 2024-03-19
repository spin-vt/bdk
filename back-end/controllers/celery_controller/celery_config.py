from celery import Celery
from utils.config import Config

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



# app = Flask(__name__)
# CORS(app)
# You can adjust this to switch between environments as needed
# celery = Celery(app.name, broker='redis://localhost:6379/0', include=['celery_setup.celery_tasks'])
# app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
# celery.conf.update(app.config)
