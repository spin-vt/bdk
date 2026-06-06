"""BDK Flask API as domain blueprints.

Importing this package (or `routes:app` for gunicorn) registers every
endpoint onto the shared app from utils.flask_app.
"""

from routes.admin import bp as admin_bp
from routes.auth import bp as auth_bp
from routes.challenge import bp as challenge_bp
from routes.edit import bp as edit_bp
from routes.export import bp as export_bp
from routes.files import bp as files_bp
from routes.filings import bp as filings_bp
from routes.organizations import bp as organizations_bp
from routes.tasks import bp as tasks_bp
from routes.tiles import bp as tiles_bp
from routes.users import bp as users_bp
from routes.wireless import bp as wireless_bp
from utils.flask_app import app

_blueprints = (
    admin_bp,
    auth_bp,
    challenge_bp,
    edit_bp,
    export_bp,
    files_bp,
    filings_bp,
    organizations_bp,
    tasks_bp,
    tiles_bp,
    users_bp,
    wireless_bp,
)

for _bp in _blueprints:
    app.register_blueprint(_bp)
