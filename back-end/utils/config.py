import base64
import os

from utils.settings import COOKIE_EXP_TIME, DATABASE_URL, IN_PRODUCTION


def validate_prod_secrets(in_production, jwt_secret):
    """Refuse to boot a production instance on a weak JWT signing secret.
    Dev/test instances are exempt."""
    if in_production and (not jwt_secret or len(jwt_secret) < 32):
        raise RuntimeError(
            "JWT_SECRET must be at least 32 bytes in production "
            "(set a long random value in the environment)."
        )


validate_prod_secrets(IN_PRODUCTION, os.getenv("JWT_SECRET"))


# Centralized configuration settings
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = base64.b64encode(os.getenv("JWT_SECRET").encode())
    JWT_TOKEN_LOCATION = [os.getenv("JWT_TOKEN_LOCATION")]
    JWT_ACCESS_COOKIE_NAME = os.getenv("JWT_ACCESS_COOKIE_NAME")
    # Session tokens carry (and require) their own audience so no other token
    # signed with the shared key — email verification tokens (aud=bdk-email),
    # admin_session tokens — can ever pass as an app session. Without this,
    # a 15-minute email token literally worked as a login cookie.
    JWT_ENCODE_AUDIENCE = "bdk-app"
    JWT_DECODE_AUDIENCE = "bdk-app"
    # Double-submit CSRF on the cookie session: login/register set a
    # JS-readable csrf_access_token cookie alongside the HttpOnly token, and
    # every mutating /api request must echo it in X-CSRF-TOKEN (the frontend
    # fetch wrapper does this globally). SameSite=Lax remains as
    # defense-in-depth, not the only line.
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SECURE = bool(IN_PRODUCTION)
    JWT_COOKIE_SAMESITE = "Lax"
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
    # An active task-info row (PENDING/STARTED/RETRY) older than this is
    # presumed dead and swept to FAILURE (services.job_service). A chain row is
    # keyed by its final task id, so an early-link crash strands it PENDING —
    # nothing but the sweep ever resolves those. Default: 2 hours, comfortably
    # above the slowest real operation (a full fabric replace + recompute).
    STUCK_TASK_MAX_AGE_SECONDS = int(os.getenv("STUCK_TASK_MAX_AGE_SECONDS", "7200"))

    # Email configurations
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ["true", "1", "t"]
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() in ["true", "1", "t"]
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
