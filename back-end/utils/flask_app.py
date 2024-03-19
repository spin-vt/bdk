from flask import Flask
from utils.config import Config
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, supports_credentials=True)
    
    # Initialize other extensions
    jwt = JWTManager(app)

    return app, jwt

app, jwt = create_app()