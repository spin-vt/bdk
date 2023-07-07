import logging
import time
import os
import json
import uuid
from logging.handlers import RotatingFileHandler
from logging import getLogger
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, abort, jsonify, request, make_response, send_file
from flask_jwt_extended.exceptions import NoAuthorizationError
from flask_jwt_extended.exceptions import JWTExtendedException
from werkzeug.exceptions import HTTPException
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from flask_jwt_extended.exceptions import NoAuthorizationError
from flask import Response
import base64
from utils.settings import DATABASE_URL
from database_op import fabric_ops
from database_op import kml_ops
from database_op import user_ops
from database_op import vt_ops
from celery_setup.celery_config import app
from celery_setup.celery_tasks import process_input_file, provide_kml_locations



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


app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

logging.basicConfig(level=logging.DEBUG)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'ADFAKJFDLJEOQRIOPQ498689780')  # Use a default value for development if SECRET_KEY environment variable doesn't exist
app.config["JWT_SECRET_KEY"] = base64.b64encode(os.getenv('JWT_SECRET', 'ADFAKJFDLJEOQRI').encode())  # Use a default value for development if JWT_SECRET environment variable doesn't exist
jwt = JWTManager(app)



@app.route("/served-data", methods=['GET'])
def get_number_records():
    return jsonify(kml_ops.get_wired_data())

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
        
        fabricName = ""
        flag = False

        geojson_array = []

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
                if not fabric_ops.check_num_records_greater_zero():
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
                kmlfile_path = os.path.join(os.getcwd(), file_name)
                geojson_array.append(vt_ops.read_kml(kmlfile_path))

                if task is False:
                    logging.error("KML processing task %s failed with error: %s", task_id, task.traceback)
                    response_data = {'Status': 'Error'}
                else:
                    response_data = {'Status': 'Ok'}
                    
        vt_ops.create_tiles(geojson_array)
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


@app.route('/api/search', methods=['GET'])
def search_location():
    query = request.args.get('query').upper()
    results_dict = fabric_ops.address_query(query)
    return jsonify(results_dict)


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    new_user_id = user_ops.create_user_in_db(username, password)

    if not new_user_id:
        return jsonify({'status': 'error', 'message': 'Username already exists.'})

    access_token = create_access_token(identity={'id': new_user_id, 'username': username})

    response = make_response(jsonify({'status': 'success', 'token': access_token}))
    response.set_cookie('token', access_token, httponly=False, samesite='Lax', secure=False)
    return response


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = user_ops.get_user_from_db(username)

    if user is not None and check_password_hash(user[2], password):
        user_id = user[0]
        access_token = create_access_token(identity={'id': user_id, 'username': username})
        return jsonify({'status': 'success', 'token': access_token})
    else:
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

    filename = kml_ops.export(download_speed, upload_speed, tech_type)

    if filename:
        response_data = {'Status': "Success"}
        return send_file(filename, as_attachment=True)
    else:
        return jsonify(response_data)


@app.route("/tiles/<zoom>/<x>/<y>.pbf")
def serve_tile(zoom, x, y):
    zoom = int(zoom)
    x = int(x)
    y = int(y)
    y = (2**zoom - 1) - y

    tile = vt_ops.retrieve_tiles(zoom, x, y)

    if tile is None:
        return Response('No tile found', status=404)
        
    response = make_response(bytes(tile[0]))    
    response.headers['Content-Type'] = 'application/x-protobuf'
    response.headers['Content-Encoding'] = 'gzip'  
    return response

@app.route('/toggle-markers', methods=['POST'])
def toggle_markers():
    markers = request.json
    response = vt_ops.toggle_tiles(markers)

    return jsonify(message=response[0]), response[1]


@app.route('/api/mbtiles', methods=['GET'])
def get_mbtiles():
    mbtiles = vt_ops.get_mbt_info()
    if not mbtiles:
        Response('No mbtiles found', status=404)
    return jsonify(mbtiles)


if __name__ == '__main__':
    app.run(port=5000, debug=True)