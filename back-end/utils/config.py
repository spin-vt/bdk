import base64
import os

from utils.settings import COOKIE_EXP_TIME, DATABASE_URL


# Centralized configuration settings
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = base64.b64encode(os.getenv("JWT_SECRET").encode())
    JWT_TOKEN_LOCATION = [os.getenv("JWT_TOKEN_LOCATION")]
    JWT_ACCESS_COOKIE_NAME = os.getenv("JWT_ACCESS_COOKIE_NAME")
    JWT_COOKIE_CSRF_PROTECT = False
    # flask-jwt-extended 4.7 enforces RFC 7519's "sub must be a string" by
    # default (JWT_VERIFY_SUB=True), which 422s every @jwt_required route here
    # because the app mints a dict identity ({"id": ...}). Disable that check to
    # keep auth working on the modern stack. TODO(phase1): migrate to string
    # identities (identity=str(user_id) + int(get_jwt_identity())) and re-enable.
    JWT_VERIFY_SUB = False
    JWT_ACCESS_TOKEN_EXPIRES = COOKIE_EXP_TIME
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

    # Email configurations
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ["true", "1", "t"]
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() in ["true", "1", "t"]
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
