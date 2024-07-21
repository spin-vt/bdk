from flask import Flask
from utils.config import Config
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os
from flask_mail import Mail



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, supports_credentials=True)
    
    mail = Mail()

    # Initialize other extensions
    jwt = JWTManager(app)

    mail.init_app(app)

    return app, jwt, mail

app, jwt, mail = create_app()