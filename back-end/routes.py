import logging
import time
import os
import json
import uuid
from logging.handlers import RotatingFileHandler
from logging import getLogger
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, Column, Integer, String, Float, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import ProgrammingError
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, abort, jsonify, request, make_response, send_file
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    decode_token
)
from flask_jwt_extended.exceptions import NoAuthorizationError
from celery import Celery
import concurrent.futures
from sqlalchemy import inspect
from threading import Lock
import csv
import zipfile
import sqlite3
from flask import Response
import subprocess

import fabricUpload
import kmlComputation
from fabricUpload import Data
from coordinateCluster import get_bounding_boxes
import vectorTile
import fabricUpload

logging.basicConfig(level=logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger = getLogger(__name__)

file_handler = RotatingFileHandler(filename='app.log', maxBytes=1000000, backupCount=1)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.addHandler(console_handler)

app = Flask(__name__)
CORS(app)

celery = Celery(app.name, broker='redis://localhost:6379/0')
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery.conf.update(app.config)

db_host = os.getenv('postgres', 'localhost')

logging.basicConfig(level=logging.DEBUG)

app.config['SECRET_KEY'] = 'ADFAKJFDLJEOQRIOPQ498689780'
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://postgres:db123@{db_host}:5432/postgres'
app.config["JWT_SECRET_KEY"] = "ADFAKJFDLJEOQRI"
jwt = JWTManager(app)

Base = declarative_base()
DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
engine = create_engine(DATABASE_URL)

logging.basicConfig(level=logging.DEBUG)
db_lock = Lock()

states = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]

@celery.task(bind=True)
def process_input_file(self, file_name, task_id):
    result = fabricUpload.write_to_db(file_name)
    self.update_state(state='PROCESSED')
    return result


@celery.task(bind=True)
def provide_kml_locations(self, fabric, network, downloadSpeed, uploadSpeed, techType, flag, networkType):
    try:
        result = kmlComputation.add_network_data(fabric, network, flag, downloadSpeed, uploadSpeed, techType, networkType)
        self.update_state(state='PROCESSED')
        return result
    except Exception as e:
        logging.exception("Error processing KML file: %s", str(e))
        self.update_state(state='FAILED')
        raise

@app.route("/served-data", methods=['GET'])
def get_number_records():
    return jsonify(kmlComputation.get_wired_data())

@app.route('/submit-data', methods=['POST', 'GET'])
def submit_data():
    if request.method == 'POST':
        names = []

        if 'file' not in request.files:
            return make_response('Error: No file uploaded', 400)

        files = request.files.getlist('file')

        if len(files) <= 0:
            return make_response('Error: No file uploaded', 400)

        file_data_list = request.form.getlist('fileData')

        # inspector = inspect(engine)
        # if inspector.has_table('Fabric') and inspector.has_table('KML'):
        #     response_data = {'Status': "Ok"}
        #     return json.dumps(response_data)
        
        fabricName = ""
        flag = False

        for file, file_data_str in zip(files, file_data_list):
            file_name = file.filename
            names.append(file_name)

            file_data = json.loads(file_data_str)

            downloadSpeed = file_data.get('downloadSpeed', '')
            uploadSpeed = file_data.get('uploadSpeed', '')
            techType = file_data.get('techType', '')
            networkType = file_data.get('networkType', '')

            if file_name.endswith('.csv'):
                file.save(file_name)
                fabricName = file_name

                task_id = str(uuid.uuid4())

                task = process_input_file.apply_async(args=[file_name, task_id])

                while not task.ready():
                    time.sleep(1)

                response_data = {'Status': "Ok"}

            elif file_name.endswith('.kml'):
                if not fabricUpload.check_num_records_greater_zero():
                    return make_response('Error: Fabric records not in database', 400)

                file.save(file_name)
                task_id = str(uuid.uuid4())

                if networkType == "Wired": 
                    networkType = 0
                else: 
                    networkType = 1

                task = provide_kml_locations.apply_async(args=[fabricName, file_name, downloadSpeed, uploadSpeed, techType, flag, networkType])
                logging.info("Started KML processing task with ID %s %s %s", task_id, fabricName, file_name)

                while not task.ready():
                    time.sleep(1)

                logging.info("KML processing task %s completed", task_id)
                flag = True
                # result = task.result
                # dict_values = result

                if task is False:
                    logging.error("KML processing task %s failed with error: %s", task_id, task.traceback)
                    response_data = {'Status': 'Error'}
                else:
                    response_data = {'Status': 'Ok'}
                    
        vectorTile.create_tiles()
        for name in names:
            os.remove(name)

        return json.dumps(response_data)

    else:
        response_data = {'Status': "Not a valid request type"}
        return json.dumps(response_data)


@app.route('/')
def home():
    response_body = {
        "name": "Success!",
        "message": "Backend successfully connected to frontend"
    }

    return response_body

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


@app.route('/api/search', methods=['GET'])
def search_location():
    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    query = request.args.get('query').upper()

    results = []

    if query:
        query_split = query.split()

        if len(query_split) >= 3:
            primary_address = " ".join(query_split[:-2]).upper()
            city = query_split[-2].upper().strip()
            state = query_split[-1].upper().strip()

            cursor.execute(
                """
                SELECT address_primary, city, state, zip_code, latitude, longitude
                FROM "Fabric"
                WHERE UPPER(address_primary) LIKE %s AND UPPER(city) = %s AND UPPER(state) = %s
                LIMIT 1
                """,
                ('%' + primary_address + '%', city, state,)
            )

            results.extend(cursor.fetchall())

        if len(query_split) >= 2:
            primary_address = " ".join(query_split[:-1]).upper()
            city_or_state = query_split[-1].upper().strip()

            if city_or_state in states:  
                cursor.execute(
                    """
                    SELECT address_primary, city, state, zip_code, latitude, longitude
                    FROM "Fabric"
                    WHERE UPPER(address_primary) LIKE %s AND UPPER(state) = %s
                    LIMIT 3
                    """,
                    ('%' + primary_address + '%', city_or_state,)
                )

            else:  
                cursor.execute(
                    """
                    SELECT address_primary, city, state, zip_code, latitude, longitude
                    FROM "Fabric" 
                    WHERE UPPER(address_primary) LIKE %s AND UPPER(city) = %s
                    LIMIT 3
                    """,
                    ('%' + primary_address + '%', city_or_state,)
                )

            results.extend(cursor.fetchall())

        cursor.execute(
            """
            SELECT address_primary, city, state, zip_code, latitude, longitude
            FROM "Fabric" 
            WHERE UPPER(address_primary) LIKE %s 
            LIMIT 5
            """,
            ('%' + query.upper() + '%',)
        )

        results.extend(cursor.fetchall())

    results_dict = [
        {
            "address": result[0],
            "city": result[1],
            "state": result[2],
            "zipcode": result[3],
            "latitude": result[4],
            "longitude": result[5]
        } for result in results
    ]

    cursor.close()
    conn.close()
    return jsonify(results_dict)


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    cursor.execute("SELECT username FROM \"User\" WHERE username = %s", (username,))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Username already exists.'})

    hashed_password = generate_password_hash(password, method='sha256')

    cursor.execute("INSERT INTO \"User\" (username, password) VALUES (%s, %s) RETURNING id", (username, hashed_password))
    new_user_id = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    access_token = create_access_token(identity={'id': new_user_id, 'username': username})

    response = make_response(jsonify({'status': 'success', 'token': access_token}))
    response.set_cookie('token', access_token, httponly=False, samesite='Lax', secure=False)
    return response


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM \"User\" WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user is not None and check_password_hash(user[2], password):
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


@app.route('/export', methods=['GET'])
def export():
    response_data = {'Status': 'Failure'}

    download_speed = request.args.get('downloadSpeed', default='', type=str)
    upload_speed = request.args.get('uploadSpeed', default='', type=str)
    tech_type = request.args.get('techType', default='', type=str)

    filename = kmlComputation.export(download_speed, upload_speed, tech_type)

    if filename:
        response_data = {'Status': "Success"}
        return send_file(filename, as_attachment=True)
    else:
        return jsonify(response_data)


@app.route('/export-wireless', methods=['GET'])
def export_wireless():
    response_data = {'Status': 'Failure'}

    download_speed = request.args.get('downloadSpeed', default='', type=str)
    upload_speed = request.args.get('uploadSpeed', default='', type=str)
    tech_type = request.args.get('techType', default='', type=str)

    filename = kmlComputation.exportWireless(download_speed, upload_speed, tech_type)
    filename2 = kmlComputation.exportWireless2(download_speed, upload_speed, tech_type)

    if filename and filename2:
        with zipfile.ZipFile('wirelessCSVs.zip', 'w') as zipf:
            zipf.write(filename, os.path.basename(filename))
            zipf.write(filename2, os.path.basename(filename2))

        return send_file('wirelessCSVs.zip', as_attachment=True)
    else:
        return jsonify(response_data)

@app.route("/tiles/<zoom>/<x>/<y>.pbf")
def serve_tile(zoom, x, y):
    zoom = int(zoom)
    x = int(x)
    y = int(y)
    y = (2**zoom - 1) - y

    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    with db_lock:
            cursor.execute(
                """
                SELECT tile_data
                FROM "vt"
                WHERE zoom_level = %s AND tile_column = %s AND tile_row = %s
                """, 
                (int(zoom), int(x), int(y))
            )
    tile = cursor.fetchone()

    if tile is None:
        return Response('No tile found', status=404)
        
    response = make_response(bytes(tile[0]))    
    response.headers['Content-Type'] = 'application/x-protobuf'
    response.headers['Content-Encoding'] = 'gzip'  
    return response

@app.route('/toggle-markers', methods=['POST'])
def toggle_markers():
    markers = request.json
    conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
    cursor = conn.cursor()

    try:
        with db_lock:
            for marker in markers:
                cursor.execute(
                    """
                    UPDATE "KML"
                    SET "served" = %s
                    WHERE "location_id" = %s
                    """, 
                    (marker['served'], marker['id'],)
                )
        conn.commit()
        vectorTile.create_tiles()
        message = 'Markers toggled successfully'
        status_code = 200

    except Exception as e:
        conn.rollback()  # rollback transaction on error
        message = str(e)  # send the error message to client
        status_code = 500

    finally:
        cursor.close()
        conn.close()

    return jsonify(message=message), status_code

if __name__ == '__main__':
    Base.metadata.create_all(engine)
    app.run(port=8000, debug=True)