import logging, os, base64, uuid
from logging.handlers import RotatingFileHandler
from logging import getLogger
from werkzeug.security import check_password_hash
from flask import jsonify, request, make_response, send_file, Response
from flask_jwt_extended.exceptions import NoAuthorizationError
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    decode_token
)
from celery.result import AsyncResult
from utils.settings import DATABASE_URL, COOKIE_EXP_TIME
from database.sessions import Session
from database.models import file, user, folder
from controllers.database_controller import fabric_ops, kml_ops, user_ops, vt_ops, file_ops, folder_ops
from controllers.celery_controller.celery_config import app, celery 
from controllers.celery_controller.celery_tasks import process_data

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
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config['JWT_ACCESS_COOKIE_NAME'] = 'token'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
jwt = JWTManager(app)

@app.route("/served-data/<username>", methods=['GET'])
def get_number_records(username):

    userVal = user_ops.get_user_with_username(username)
    folderVal = folder_ops.get_folder(userVal.id)
    
    return jsonify(kml_ops.get_kml_data(userVal.id, folderVal.id)), 200

@app.route('/submit-data', methods=['POST', 'GET'])
def submit_data():
    try:
        username = request.form.get('username')
        
        if 'file' not in request.files:
            return jsonify({'Status': "Failed, no file uploaded"}), 400

        files = request.files.getlist('file')

        if len(files) <= 0:
            return jsonify({'Status': "Failed, no file uploaded"}), 400

        file_data_list = request.form.getlist('fileData')

        userVal = user_ops.get_user_with_username(username)
        # Retrieve the last folder of the user, if any, otherwise create a new one
        folderVal = folder_ops.get_folder(userVal.id)
        session = Session()
        if folderVal is None:
            folderVal = folder_ops.create_folder("user-1",userVal.id, session)
            session.commit()
            print(folderVal.id)
        session.close()

        file_names = []

        for f in files:
            existing_file = file_ops.get_file_with_name(f.filename, folderVal.id)
            if existing_file is not None:
                # If file already exists, append its name to file_names and skip to next file
                file_names.append(existing_file.name)
                continue
            
            data = f.read()
            if (f.filename.endswith('.csv')):
                file_ops.create_file(f.filename, data, folderVal.id, 'fabric')
            elif (f.filename.endswith('.kml')):
                file_ops.create_file(f.filename, data, folderVal.id)
            file_names.append(f.filename)

        task = process_data.apply_async(args=[file_names, file_data_list, userVal.id, folderVal.id]) # store the AsyncResult instance
        return jsonify({'Status': "OK", 'task_id': task.id}), 200 # return task id to the client
    
    except Exception as e:
        return jsonify({'Status': "Failed, server failed", 'error': str(e)}), 500

@app.route('/status/<task_id>')
def taskstatus(task_id):
    task = AsyncResult(task_id, app=celery)

    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'status': str(task.result)
        }
    else:
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    return jsonify(response)

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
    pword = data.get('password')

    # Needs a try catch to return the correct message
    user = user_ops.get_user_with_username(username)

    if user is not None and check_password_hash(user.password, pword):
        user_id = user.id
        access_token = create_access_token(identity={'id': user_id, 'username': username})
        response = make_response(jsonify({'status': 'success', 'token': access_token}))
        response.set_cookie('token', access_token, httponly=False, samesite='Lax', secure=False)
        return response
    else:
        return jsonify({'status': 'error', 'message': 'Invalid credentials'})


@app.route('/api/logout', methods=['POST'])
def logout():
    response = make_response(jsonify({'status': 'success', 'message': 'Logged out'}))
    response.delete_cookie('token')
    return response


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

    filename = kml_ops.export()
    if filename:
        response_data = {'Status': "Success"}
        return send_file(filename, as_attachment=True)
    else:
        return jsonify(response_data)
    

@app.route("/tiles/<mbtile_id>/<username>/<zoom>/<x>/<y>.pbf")
def serve_tile_withid(mbtile_id, username, zoom, x, y):
    username = str(username)
    mbtile_id = int(mbtile_id)

    zoom = int(zoom)
    x = int(x)
    y = int(y)
    y = (2**zoom - 1) - y

    tile = vt_ops.retrieve_tiles(zoom, x, y, username, mbtile_id)

    if tile is None:
        return Response('No tile found', status=404)
        
    response = make_response(bytes(tile[0]))    
    response.headers['Content-Type'] = 'application/x-protobuf'
    response.headers['Content-Encoding'] = 'gzip'  
    return response


@app.route("/tiles/<username>/<zoom>/<x>/<y>.pbf")
def serve_tile(username, zoom, x, y):
    username = str(username)

    zoom = int(zoom)
    x = int(x)
    y = int(y)
    y = (2**zoom - 1) - y

    tile = vt_ops.retrieve_tiles(zoom, x, y, username, None)

    if tile is None:
        return Response('No tile found', status=404)
        
    response = make_response(bytes(tile[0]))    
    response.headers['Content-Type'] = 'application/x-protobuf'
    response.headers['Content-Encoding'] = 'gzip'  
    return response

@app.route('/toggle-markers', methods=['POST'])
@jwt_required()
def toggle_markers():
    try:
        markers = request.json
        identity = get_jwt_identity()
        response = vt_ops.toggle_tiles(markers, identity['id'])

        return jsonify(message=response[0]), response[1]
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401


@app.route('/api/files', methods=['GET'])
@jwt_required()
def get_files():
    try:
        identity = get_jwt_identity()
        folderVal = folder_ops.get_folder(identity['id'])
        if folderVal:
            filesinfo = file_ops.get_filesinfo_in_folder(folderVal.id)
            if not filesinfo:
                return jsonify({'error': 'No files found'}), 404
            return jsonify(filesinfo), 200
        else:
            return jsonify({'error': 'No files found'}), 404
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    
@app.route('/api/delmbtiles/<int:mbtiles_id>', methods=['DELETE'])
@jwt_required()
def delete_mbtiles(mbtiles_id):
    try:
        identity = get_jwt_identity()
        vt_ops.delete_mbtiles(mbtiles_id, identity["id"])
        return jsonify({'message': 'mbtiles successfully deleted'}), 200
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401


if __name__ == '__main__':
    app.run(port=5000, debug=True)