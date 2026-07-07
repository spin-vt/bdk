"""BDK Flask API as domain blueprints.

Importing this package (or `routes:app` for gunicorn) registers every
endpoint onto the shared app from utils.flask_app.
"""

from routes.admin_api import bp as admin_api_bp
from routes.admin_ui import bp as admin_ui_bp
from routes.app_pages import bp as app_pages_bp  # server-rendered app pages (/org, /map, ...)
from routes.auth import bp as auth_bp
from routes.auth_pages import bp as auth_pages_bp  # server-rendered /auth/* (new shell)
from routes.challenge import bp as challenge_bp
from routes.edit import bp as edit_bp
from routes.export import bp as export_bp
from routes.fabric import bp as fabric_bp
from routes.files import bp as files_bp
from routes.files_page import bp as files_page_bp  # server-rendered /files page
from routes.filings import bp as filings_bp
from routes.jobs import bp as jobs_bp
from routes.map_page import bp as map_page_bp  # server-rendered /map (studio map)
from routes.organizations import bp as organizations_bp
from routes.setup_page import bp as setup_page_bp  # server-rendered /setup (the funnel)
from routes.submissions_page import bp as submissions_page_bp  # server-rendered /submissions
from routes.tasks import bp as tasks_bp
from routes.tiles import bp as tiles_bp
from routes.users import bp as users_bp
from utils.flask_app import app

_blueprints = (
    admin_api_bp,
    admin_ui_bp,
    app_pages_bp,
    auth_bp,
    auth_pages_bp,
    challenge_bp,
    edit_bp,
    export_bp,
    fabric_bp,
    files_bp,
    files_page_bp,
    filings_bp,
    jobs_bp,
    map_page_bp,
    organizations_bp,
    setup_page_bp,
    submissions_page_bp,
    tasks_bp,
    tiles_bp,
    users_bp,
)

for _bp in _blueprints:
    app.register_blueprint(_bp)
