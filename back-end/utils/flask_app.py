from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail

from utils.config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, supports_credentials=True)

    mail = Mail()

    # Initialize other extensions
    jwt = JWTManager(app)

    mail.init_app(app)

    # Bootstrap the schema for fresh local databases (Alembic owns it in
    # containers). Done here rather than at import time so importing modules
    # never requires a live database.
    from database.sessions import init_db

    init_db()

    return app, jwt, mail


app, jwt, mail = create_app()
