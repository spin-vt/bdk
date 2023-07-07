from celery import Celery
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# For production
# celery = Celery(app.name, broker='redis://bdk-redis-1:6379/0')
# app.config['CELERY_RESULT_BACKEND'] = 'redis://bdk-redis-1:6379/0'
# celery.conf.update(app.config)
# You can adjust this to switch between environments as needed
celery = Celery('my_celery_app', broker='redis://localhost:6379/0', include=['controllers.celery_controller.celery_tasks'])
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery.conf.update(app.config)
