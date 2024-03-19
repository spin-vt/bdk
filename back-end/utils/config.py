import os
import base64
from utils.settings import COOKIE_EXP_TIME, DATABASE_URL
# Centralized configuration settings
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = base64.b64encode(os.getenv('JWT_SECRET').encode())
    JWT_TOKEN_LOCATION = [os.getenv('JWT_TOKEN_LOCATION')]
    JWT_ACCESS_COOKIE_NAME = os.getenv('JWT_ACCESS_COOKIE_NAME')
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_ACCESS_TOKEN_EXPIRES = COOKIE_EXP_TIME
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    CELERY_BROKER_URL = 'redis://redis:6379/0'
    CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
