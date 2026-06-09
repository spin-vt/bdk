import os

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from utils.config import Config
from utils.logger_config import logger

# back-end/ (parent of utils/) — the server-rendered admin panel's Jinja
# templates and static assets live here.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    # template_folder/static_folder point at back-end/{templates,static} (not the
    # package-relative default). static is served under /admin/static so it never
    # collides with the SPA; nothing else uses Flask's static route.
    app = Flask(
        __name__,
        template_folder=os.path.join(BACKEND_DIR, "templates"),
        static_folder=os.path.join(BACKEND_DIR, "static"),
        static_url_path="/admin/static",
    )
    app.config.from_object(Config)
    # Scope CORS to the SPA's JSON API only. The server-rendered /admin panel is
    # same-origin and must NOT be reachable cross-origin with credentials.
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Behind nginx, trust one proxy hop so request.remote_addr (used for rate
    # limiting and audit IPs) is the real client, not 127.0.0.1.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Security headers for the admin panel: a strict CSP (no inline scripts —
    # admin JS is externalized), anti-clickjacking, and no referrer leakage.
    # Only applied to /admin so the SPA is unaffected.
    @app.after_request
    def _admin_security_headers(response):
        if request.path.startswith("/admin"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
            )
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    mail = Mail()

    # Initialize other extensions
    jwt = JWTManager(app)

    mail.init_app(app)

    # Rate limiting on auth endpoints. Storage reuses the Celery Redis in
    # dev/prod; falls back to in-memory when no redis broker is configured (tests).
    # Disabled via RATELIMIT_ENABLED=false so the suite doesn't trip limits across
    # tests; the dedicated rate-limit test re-enables it.
    broker = os.getenv("CELERY_BROKER_URL", "") or ""
    storage_uri = broker if broker.startswith("redis://") else "memory://"
    limiter = Limiter(get_remote_address, app=app, storage_uri=storage_uri, default_limits=[])
    if os.getenv("RATELIMIT_ENABLED", "true").lower() not in ("1", "true", "t", "yes"):
        limiter.enabled = False

    # 429s get a friendly response in the right shape (HTML for the admin panel,
    # JSON for the API). Registered specifically so it wins over the generic
    # Exception handler below.
    @app.errorhandler(429)
    def ratelimit_handler(error):
        if request.path.startswith("/admin"):
            return render_template(
                "admin/login.html",
                error="Too many attempts. Please wait a minute and try again.",
            ), 429
        return jsonify(
            {"status": "error", "message": "Too many requests. Please slow down and try again."}
        ), 429

    # Request-scoped DB session lifecycle: web handlers use
    # database.sessions.get_session() (the scoped session); this teardown rolls
    # back anything uncommitted and returns the connection at the end of every
    # request, so handlers never close sessions themselves.
    from database.sessions import ScopedSession

    @app.teardown_appcontext
    def remove_session(exception=None):
        ScopedSession.remove()

    # Global fallback so an unexpected error returns a clean JSON 500 in the
    # unified {status: error, message} shape instead of leaking an HTML
    # stack trace. Real HTTP errors (404, 405, the JWT 401s, ...) pass through
    # to Flask's normal handling.
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        logger.exception(error)
        return jsonify({"status": "error", "message": "Internal server error"}), 500

    # Bootstrap the schema for fresh local databases (Alembic owns it in
    # containers). Done here rather than at import time so importing modules
    # never requires a live database.
    from database.sessions import init_db

    init_db()

    return app, jwt, mail, limiter


app, jwt, mail, limiter = create_app()
