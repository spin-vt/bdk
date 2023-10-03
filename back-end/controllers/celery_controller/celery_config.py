from celery import Celery
from flask import Flask
from flask_cors import CORS
from celery.signals import setup_logging
import logging

# Set up custom logger here if not already done in 'utils.logger_config'
# ... your logger setup ...

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['result_backend'],
        broker=app.config['broker_url'],
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
    broker_url='redis://redis:6379/0',
    result_backend='redis://redis:6379/0',
    worker_hijack_root_logger=False
)

CORS(app, supports_credentials=True)

celery = make_celery(app)


# app = Flask(__name__)
# CORS(app)
# You can adjust this to switch between environments as needed
# celery = Celery(app.name, broker='redis://localhost:6379/0', include=['celery_setup.celery_tasks'])
# app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
# celery.conf.update(app.config)
