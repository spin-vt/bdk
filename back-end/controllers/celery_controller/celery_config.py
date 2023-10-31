from celery import Celery
from flask import Flask
from flask_cors import CORS
import redis 


def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL'],
        include=['controllers.celery_controller.celery_tasks']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

app = Flask(__name__)

app.config.update(
    CELERY_BROKER_URL='redis://redis:6379/0',
    CELERY_RESULT_BACKEND='redis://redis:6379/0'
)

CORS(app, supports_credentials=True)

celery = make_celery(app)


# app = Flask(__name__)
# CORS(app)
# You can adjust this to switch between environments as needed
# celery = Celery(app.name, broker='redis://localhost:6379/0', include=['celery_setup.celery_tasks'])
# app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
# celery.conf.update(app.config)
