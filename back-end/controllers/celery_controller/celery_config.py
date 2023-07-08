from celery import Celery
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

celery = Celery('my_celery_app', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0', include=['controllers.celery_controller.celery_tasks'])
