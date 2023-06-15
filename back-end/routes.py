import logging
import time
from logging.handlers import RotatingFileHandler
from logging import getLogger, INFO
import os
import processData
import uuid
import servicePlan
import kmlEngine
import filterPointsFunction
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError

logging.basicConfig(level=logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger = getLogger(__name__)

# Add RotatingFileHandler for file logging
file_handler = RotatingFileHandler(filename='app.log', maxBytes=1000000, backupCount=1)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.addHandler(console_handler)

from flask import Flask, abort, jsonify, request, make_response
from flask_cors import CORS
from celery import Celery

locations_served_dict = {}

import json

app = Flask(__name__)
CORS(app)

celery = Celery(app.name, broker='redis://localhost:6379/0')
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery.conf.update(app.config)

# configure the logger to print out log messages to the console and file
logging.basicConfig(level=logging.DEBUG)


@celery.task(bind=True)
def process_input_file(self, file_name, task_id):
    result = processData.open_and_read(file_name)
    # Notify the submit_fiber_form method that the worker has finished processing
    self.update_state(state='PROCESSED')
    return result


logging.basicConfig(level=logging.DEBUG)


@celery.task(bind=True)
def provide_kml_locations(self, names):
    try:
        result = kmlEngine.filter_locations(names[0], names[1])
        self.update_state(state='PROCESSED')
        return result
    except Exception as e:
        logging.exception("Error processing KML file: %s", str(e))
        self.update_state(state='FAILED')
        raise


@app.route("/is-db-altered")
def is_db_altered():
    if len(kmlEngine.get_precise_data(10)) > 0:
        return jsonify({"Status": "Success", "Message": "Data has been added to db"})
    else:
        return jsonify({"Status": "Failure", "Message": "Data has not been added to db"})


@app.route("/location-data-range/<lat>/<long>/<range>", methods=['GET'])
def get_locations_in_range(lat, long, range):
    return jsonify(kmlEngine.get_locations_in_range(lat, long, range))


@app.route("/served-data", methods=['GET'])
def get_number_records():
    return jsonify(kmlEngine.get_precise_data())


@app.route('/pointsWithin/<minLat>/<maxLat>/<minLng>/<maxLng>', methods=['GET'])
def get_points(minLat, minLng, maxLat, maxLng):
    print(minLat + " " + minLng + " " + maxLat + " " + maxLng)
    points = filterPointsFunction.get_points_within_box(minLat, minLng, maxLat, maxLng)
    return jsonify(points)


import uuid
import time
import os
import json

@app.route('/submit-fiber-form', methods=['POST', 'GET'])
def submit_fiber_form():
    if request.method == 'POST':
        names = []

        if 'file' not in request.files:
            return make_response('Error: No file uploaded', 400)

        files = request.files.getlist('file')

        if len(files) <= 0:
            return make_response('Error: No file uploaded', 400)

        for file in files:
            print(file)
            file_name = file.filename
            names.append(file_name)

            if file_name.endswith('.csv'):
                # Process CSV file
                file.save(file_name)

                # Generate a unique task ID
                task_id = str(uuid.uuid4())

                # Start the task
                task = process_input_file.apply_async(args=[file_name, task_id])

                # Check the task status periodically
                while not task.ready():
                    time.sleep(1)

                # Check if the task has finished processing

                response_data = {'Status': "Ok"}

            elif file_name.endswith('.kml'):
                # Process KML file
                if not processData.check_num_records_greater_zero():
                    return make_response('Error: Records not in database', 400)

                file.save(file_name)
                task_id = str(uuid.uuid4())
                task = provide_kml_locations.apply_async(args=[names])
                logging.info("Started KML processing task with ID %s", task_id)

                while not task.ready():
                    time.sleep(1)

                logging.info("KML processing task %s completed", task_id)
                result = task.result
                dict_values = result

                if result is None:
                    logging.error("KML processing task %s failed with error: %s", task_id, task.traceback)
                    response_data = {'Status': 'Error'}
                else:
                    locations_served_dict = result
                    response_data = {'Status': 'Ok'}

        for name in names:
            os.remove(name)

        return json.dumps(response_data)

    else:
        response_data = {'Status': "Not a valid request type"}
        return json.dumps(response_data)


# Example of what an endpoint looks like
# You can add more routes with similar template logic
@app.route('/')
def home():
    response_body = {
        "name": "Success!",
        "message": "Backend successfully connected to frontend"
    }

    return response_body


@app.route("/submit-service-plan", methods=['POST'])
def post_to_service_plan_table():
    download_speed = request.form.get('downloadSpeed')
    upload_speed = request.form.get('uploadSpeed')
    tech_type = request.form.get('techType')
    isp_name = request.form.get('ispName')

    if kmlEngine.check_num_records_greater_zero():
        response_data = {'Status': "Success"}
        return jsonify(response_data)

    return jsonify({'error': 'An error occurred while processing the request.'}), 400


@app.route("/get-visualization/<isp_name>/")
def get_visualization(isp_name):
    with open("locale-data.json") as f:
        data = json.load(f)

        status = "Failure"
        filtered_data = {}

        filtered_data = [d for d in data["data"] if d["user_account"] == isp_name]

        if filtered_data:
            status = "Success"

        response_body = [
            ("status", status),
            ("data", filtered_data)
        ]

        return jsonify(response_body)


@app.route("/locale-data-all/")
def get_all_data():
    with open("locale-data.json") as f:
        data = json.load(f)
        data = json.loads(json.dumps(data))
    response_body = {
        "status": "success",
        "data": data
    }
    return jsonify(response_body)


from coordinateCluster import get_bounding_boxes

@app.route("/api/coordinates", methods=['POST'])
def get_bounding_coordinates():
    data = request.get_json()
    filename = data['filename']

    if not os.path.isfile(filename):
        return jsonify({"error": "File not found"}), 404

    df = pd.read_csv(filename)
    if not {'latitude', 'longitude'}.issubset(df.columns):
        return jsonify({"error": "CSV does not contain latitude or longitude column"}), 400

    coordinates = df[['latitude', 'longitude']].to_dict('records')

    return jsonify(coordinates)


from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, decode_token
from flask_jwt_extended.exceptions import NoAuthorizationError
from processData import Data
from sqlalchemy import or_
import csv
from threading import Lock
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import concurrent.futures
from sqlalchemy import inspect

app.config['SECRET_KEY'] = 'ADFAKJFDLJEOQRIOPQ498689780'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:db123@localhost:5432/postgres'
app.config["JWT_SECRET_KEY"] = "ADFAKJFDLJEOQRI"
jwt = JWTManager(app)

# CORS(app)

Base = declarative_base()
DATABASE_URL = 'postgresql://postgres:db123@localhost:5432/postgres'
engine = create_engine(DATABASE_URL)

# Check if the table exists
inspector = inspect(engine)
if not inspector.has_table('User'):
    try:
        Base.metadata.create_all(engine)
    except ProgrammingError as e:
        logging.exception("Error creating 'User' table: %s", str(e))

db_lock = Lock()


class User(Base):
    __tablename__ = 'User'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    password = Column(String(256))


@app.route('/api/search', methods=['GET'])
def search_location():
    # Establish PostgreSQL connection
    conn = psycopg2.connect('postgresql://postgres:db123@localhost:5432/postgres')
    cursor = conn.cursor()

    query = request.args.get('query').upper()


    if query:
        # Retrieve location_id from PostgreSQL table 'kml'
        cursor.execute(
            """
            SELECT address_primary, city, state, zip_code, latitude, longitude
            FROM bdk 
            WHERE UPPER(address_primary) LIKE %s 
            LIMIT 5
            """,
            ('%' + query + '%',)
        )
        results = cursor.fetchall()
        results_dict = [{"address": result[0], "city": result[1], "state": result[2], "zipcode": result[3], "latitude": result[4], "longitude": result[5]} for result in results]

    else:
        results_dict = {}

    # Convert SQLAlchemy results to dictionary format for jsonify
    # Close cursor and connection
    cursor.close()
    conn.close()
    return jsonify(results_dict)


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # Establish PostgreSQL connection
    conn = psycopg2.connect('postgresql://postgres:db123@localhost:5432/postgres')
    cursor = conn.cursor()

    # Check if the username already exists
    cursor.execute("SELECT username FROM \"User\" WHERE username = %s", (username,))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Username already exists.'})

    # Generate hashed password
    hashed_password = generate_password_hash(password, method='sha256')

    # Insert new user into the users table
    cursor.execute("INSERT INTO \"User\" (username, password) VALUES (%s, %s) RETURNING id", (username, hashed_password))
    new_user_id = cursor.fetchone()[0]

    # Commit the transaction and close the cursor and connection
    conn.commit()
    cursor.close()
    conn.close()

    # Create the access token
    access_token = create_access_token(identity={'id': new_user_id, 'username': username})

    response = make_response(jsonify({'status': 'success', 'token': access_token}))
    # Set access token as a secure HTTP only cookie
    response.set_cookie('token', access_token, httponly=False, samesite='Lax', secure=False)
    return response


@app.route('/api/login', methods=['POST'])
def login():
    # Get the data from the request
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # Establish PostgreSQL connection
    conn = psycopg2.connect('postgresql://postgres:db123@localhost:5432/postgres')
    cursor = conn.cursor()

    # Query your database for the user
    cursor.execute("SELECT * FROM \"User\" WHERE username = %s", (username,))
    user = cursor.fetchone()

    # Check the user's password
    if user is not None and check_password_hash(user[2], password):
        # If the password is valid, log the user in
        user_id = user[0]
        access_token = create_access_token(identity={'id': user_id, 'username': username})
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'token': access_token})
    else:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Invalid credentials'})


@app.route('/api/logout', methods=['POST'])
def logout():
    return jsonify({'status': 'success', 'token': ''})


@app.route('/api/user', methods=['GET'])
@jwt_required()
def get_user_info():
    try:
        identity = get_jwt_identity()
        return jsonify({'username': identity['username']})
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401


from flask import send_file

'''
@wired: if true return wired csv, otherwise wireless
'''
@app.route('/export', methods=['GET'])
def export():
    response_data = {'Status': 'Failure'}

    filename = kmlEngine.exportWired()
    if filename:
        response_data = {'Status': "Success"}
        return send_file(filename, as_attachment=True)
    else:
        return jsonify(response_data)


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    app.run(port=8000, debug=True)
