import logging, os, base64, uuid, io
from zipfile import ZipFile
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
from datetime import datetime
import shortuuid
from celery.result import AsyncResult
from utils.settings import DATABASE_URL, COOKIE_EXP_TIME, backend_port
from database.sessions import Session
from controllers.database_controller import fabric_ops, kml_ops, user_ops, vt_ops, file_ops, folder_ops, mbtiles_ops, challenge_ops, kmz_ops
from controllers.celery_controller.celery_config import app, celery 
from controllers.celery_controller.celery_tasks import process_data, deleteFiles, toggle_tiles, run_signalserver
from utils.namingschemes import DATETIME_FORMAT, EXPORT_CSV_NAME_TEMPLATE, SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE
from controllers.signalserver_controller.signalserver_command_builder import runsig_command_builder
from controllers.database_controller.tower_ops import create_tower, get_tower_with_towername
from controllers.database_controller.towerinfo_ops import create_towerinfo
from controllers.database_controller.rasterdata_ops import create_rasterdata
from controllers.signalserver_controller.read_towerinfo import read_tower_csv
from utils.logger_config import logger
import json
# logger = logging.getLogger(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

logging.basicConfig(level=logging.DEBUG)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config["JWT_SECRET_KEY"] = base64.b64encode(os.getenv('JWT_SECRET').encode())
app.config["JWT_TOKEN_LOCATION"] = [os.getenv('JWT_TOKEN_LOCATION')]
app.config['JWT_ACCESS_COOKIE_NAME'] = os.getenv('JWT_ACCESS_COOKIE_NAME')
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = COOKIE_EXP_TIME
jwt = JWTManager(app)



db_name = os.environ.get("POSTGRES_DB")
db_user = os.environ.get("POSTGRES_USER")
db_password = os.environ.get("POSTGRES_PASSWORD")
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')

@app.route("/served-data/<mbtid>", methods=['GET'])
@jwt_required()
def get_number_records(mbtid):
    mbtid = str(mbtid)
    session = Session()
    try:
        identity = get_jwt_identity()
        if mbtid != 'None':
            mbtid = int(mbtid)
            mbt_entry = mbtiles_ops.get_mbtiles_with_id(mbtid=mbtid, session=session)
            folderVal = folder_ops.get_export_folder(userid=identity['id'], folderid=mbt_entry.folder_id, session=session)
        else:
            folderVal = folder_ops.get_upload_folder(userid=identity['id'], folderid=None, session=session)
        return jsonify(kml_ops.get_kml_data(userid=identity['id'], folderid=folderVal.id, session=session)), 200
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401

@app.route('/submit-data', methods=['POST', 'GET'])
@jwt_required()
def submit_data():
    session = Session()
    try:
        identity = get_jwt_identity()
        
            
        if 'file' not in request.files:
            return jsonify({'Status': "Failed, no file uploaded"}), 400

        files = request.files.getlist('file')
        if len(files) <= 0:
            return jsonify({'Status': "Failed, no file uploaded"}), 400

        file_data_list = request.form.getlist('fileData')

        userVal = user_ops.get_user_with_id(identity['id'], session=session)
        # Retrieve the last folder of the user, if any, otherwise create a new one
        folderVal = folder_ops.get_upload_folder(userVal.id, session=session)
        if folderVal is None:
            num_folders = folder_ops.get_number_of_folders_for_user(userVal.id, session=session)
            folder_name = f"{userVal.username}-{num_folders + 1}"
            folderVal = folder_ops.create_folder(folder_name, userVal.id, 'upload', session=session)
            session.commit()
        file_names = []
        matching_file_data_list = []

        for index, f in enumerate(files):
            existing_file = file_ops.get_file_with_name(f.filename, folderVal.id, session=session)
            if existing_file is not None:
                # If file already exists, append its name to file_names and skip to next file
                continue
            existing_file = kmz_ops.get_kmz_with_name(f.filename, folderVal.id, session=session)
            if existing_file is not None:
                # If file already exists, append its name to file_names and skip to next file
                continue
            
            data = f.read()
            if (f.filename.endswith('.csv')):
                file_ops.create_file(f.filename, data, folderVal.id, None, 'fabric', session=session)
                file_names.append(f.filename)
                matching_file_data_list.append(file_data_list[index])
            elif (f.filename.endswith('.kml') or f.filename.endswith('.geojson')):
                file_ops.create_file(f.filename, data, folderVal.id, None, None, session=session)
                file_names.append(f.filename)
                matching_file_data_list.append(file_data_list[index])
            elif f.filename.endswith('.kmz'):
                kmz_entry = kmz_ops.create_kmz(f.filename, folderVal.id, session)
                session.commit()
                kml_entries = kmz_ops.extract_kml_from_kmz(data)
                prefix = f.filename.rsplit('.', 1)[0]  # This will give you the filename without the .kmz extension
                
                for entry in kml_entries:
                    kml_data = entry['data']
                    kml_filename = entry['filename']
                    new_kml_name = prefix + '-' + kml_filename
                    file_ops.create_file(new_kml_name, kml_data, folderVal.id, kmz_entry.id, None, session=session)
                    file_names.append(new_kml_name)
                    # Reuse the KMZ's associated data for each extracted KML
                    matching_file_data_list.append(file_data_list[index])
                

            session.commit()

        task = process_data.apply_async(args=[file_names, matching_file_data_list, userVal.id, folderVal.id]) # store the AsyncResult instance
        return jsonify({'Status': "OK", 'task_id': task.id}), 200 # return task id to the client
    
        
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    except ValueError as ve:
    # Handle specific errors, e.g., value errors
        return jsonify({'Status': "Failed due to bad value", 'error': str(ve)}), 400
    except Exception as e:
        # General catch-all for other exceptions
        session.rollback()  # Rollback the session in case of error
        return jsonify({'Status': "Failed, server failed", 'error': str(e)}), 500
    finally:
        session.close()  # Always close the session at the end


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
@jwt_required()
def search_location():
    query = request.args.get('query').upper()
    try:
        identity = get_jwt_identity()
        session = Session()
        try:
            userVal = user_ops.get_user_with_id(identity['id'], session)
            folderVal = folder_ops.get_upload_folder(userVal.id, None, session)
            results_dict = fabric_ops.address_query(folderVal.id, query, session)
            return jsonify(results_dict)
        except Exception as e:
                session.rollback()
                return {"error": str(e)}
        finally:
            session.close()
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401



@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    providerid = data.get('providerId')
    brandname = data.get('brandName')

    response = user_ops.create_user_in_db(username, password, providerid, brandname)

    if 'error' in response:
        return jsonify({'status': 'error', 'message': response["error"]}), 400

    access_token = create_access_token(identity={'id': response["success"], 'username': username})

    response = make_response(jsonify({'status': 'success', 'token': access_token}))
    response.set_cookie('token', access_token, httponly=False, samesite='Lax', secure=False)
    return response, 200


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


@app.route('/exportFiling', methods=['GET'])
@jwt_required()
def exportFiling():
    try:
        identity = get_jwt_identity()

        session = Session()
        try:
            userVal = user_ops.get_user_with_id(identity['id'], session)
            folderVal = folder_ops.get_upload_folder(userVal.id, None, session)
            
            csv_output = kml_ops.export(userVal.id, folderVal.id, userVal.provider_id, userVal.brand_name, session)

            if csv_output:
                current_time = datetime.now().strftime(DATETIME_FORMAT)
                
                download_name = EXPORT_CSV_NAME_TEMPLATE.format(brand_name=userVal.brand_name, current_datetime=current_time)
                
                csv_output.seek(0)
                return send_file(csv_output, as_attachment=True, download_name=download_name, mimetype="text/csv")
            else:
                return jsonify({'Status': 'Failure'})
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    
@app.route('/exportChallenge', methods=['GET'])
def exportChallenge():
    csv_output = challenge_ops.export()
    if csv_output:
        csv_output.seek(0)  # rewind the stream back to the start
        current_time = datetime.now()
        formatted_time = current_time.strftime('%Y_%B')
        download_name = "BDC_BulkChallenge_" + formatted_time + "_" + shortuuid.uuid()[:4] + '.csv'
        return send_file(csv_output, as_attachment=True, download_name=download_name, mimetype="text/csv")
    else:
        return jsonify({'Status': 'Failure'})

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
        request_data = request.json
        markers = request_data['marker']
        mbtid = request_data['mbtid']
        identity = get_jwt_identity()
        task = toggle_tiles.apply_async(args=[markers, identity['id'], mbtid])

        return jsonify({'Status': "OK", 'task_id': task.id}), 200
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401


@app.route('/api/files', methods=['GET'])
@jwt_required()
def get_files():
    try:
        identity = get_jwt_identity()
        session = Session()
        folderVal = folder_ops.get_upload_folder(identity['id'], None, session=session)
        if folderVal:
            filesinfo = file_ops.get_filesinfo_in_folder(folderVal.id, session=session)
            if not filesinfo:
                return jsonify({'error': 'No files found'}), 404
            return jsonify(filesinfo), 200
        else:
            return jsonify({'error': 'No files found'}), 404
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()
    
@app.route('/api/delfiles/<int:fileid>', methods=['DELETE'])
@jwt_required()
def delete_files(fileid):
    fileid = int(fileid)
    try:
        identity = get_jwt_identity()
        task = deleteFiles.apply_async(args=[fileid, identity['id']])
        return jsonify({'Status': "OK", 'task_id': task.id}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    
@app.route('/api/export', methods=['GET'])
@jwt_required()
def get_exported_folders():
    session = Session()
    try:
        identity = get_jwt_identity()
        folders = folder_ops.get_folders_by_type_for_user(userid=identity['id'], foldertype='export', session=session)

        response_data = []
        for fldr in folders:
            exportcsv_in_folder = file_ops.get_files_by_type(folderid=fldr.id, filetype='export', session=session)
            # exportcsv_in_folder = file_ops.get_files_in_folder(folderid=fldr.id, session=session)
            mbt_in_folder = mbtiles_ops.get_latest_mbtiles(folderid=fldr.id, session=session)

            # print(exportcsv_in_folder)
            for f in exportcsv_in_folder:
                file_data = {
                    "id": f.id,
                    "name": f.name,
                    "timestamp": f.timestamp,
                    "type": f.type,
                    "mbt_id": mbt_in_folder.id
                }
                response_data.append(file_data)

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
    
@app.route('/submit-challenge', methods=['POST'])
def submit_challenge():
    data = request.json  # This will give you the entire JSON payload
    challenge_ops.writeToDB(data)
    return jsonify({"message": "Data processed!"}), 200

@app.route('/compute-challenge', methods=['GET', 'POST'])
def compute_challenge():
    #this will be a POST request in the future, but for now we just use files in our file system for testing
    challenge_ops.import_to_postgis("./Idaho.geojson", "./filled_full_poly.kml", "./activeBSL.csv", "./activeNOBSL.csv", db_name, db_user, db_password, db_host)
    return jsonify({"message": "Data Computed!"}), 200

@app.route('/api/delexport/<int:fileid>', methods=['DELETE'])
@jwt_required()
def delete_export(fileid):
    fileid = int(fileid)
    session = Session()
    try:
        identity = get_jwt_identity()
        fileVal = file_ops.get_file_with_id(fileid=fileid, session=session)
        print(f'file id is {fileVal.id}', flush=True)
        folder_ops.delete_folder(folderid=fileVal.folder_id, session=session)
        return jsonify({'Status': "OK"}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.commit()
        session.close()

@app.route('/api/compute-wireless-coverage', methods=['POST'])
@jwt_required()
def compute_wireless_coverage():
    try:
        identity = get_jwt_identity()
        data = request.json
        logger.debug('towername       ' + data['towername'])
        towerVal = create_tower(towername=data['towername'], userid=identity['id'])
        if isinstance(towerVal, str):  # In case create_tower returned an error message
            return jsonify({'error': towerVal}), 400
        logger.info('created tower in db')
        outfile_name = SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE.format(userid=identity['id'], towername=data['towername'])
        logger.debug('check outfile name    ' + outfile_name)
        del data['towername']
        command = runsig_command_builder(data, outfile_name)
        logger.debug('check signalserver command    ' + command)

        logger.debug(towerVal.id)
        task = run_signalserver.apply_async(args=[command, outfile_name, towerVal.id, data]) # store the AsyncResult instance
        return jsonify({'Status': "OK", 'task_id': task.id}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401

@app.route('/api/get-raster-image/<string:towername>', methods=['GET'])
@jwt_required()
def get_raster_image(towername):
    session = Session()
    try:
        identity = get_jwt_identity()
        logger.debug(towername)
        towerVal = get_tower_with_towername(tower_name=towername, user_id=identity['id'], session=session)
        if isinstance(towerVal, str):  # In case create_tower returned an error message
            return jsonify({'error': towerVal}), 400
        logger.debug(towerVal)

        if not towerVal:
            return jsonify({'error': 'File not found'}), 404

        rasterData = towerVal.raster_data
        logger.debug(rasterData)
        if rasterData:
            image_io = io.BytesIO(rasterData.image_data)
            image_io.seek(0)
            response = send_file(image_io, mimetype='image/png')
            return response
        else:
            return jsonify({'error': 'Raster data not found'}), 404
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()

@app.route('/api/get-raster-bounds/<string:towername>', methods=['GET'])
@jwt_required()
def get_raster_bounds(towername):
    session = Session()
    try:
        identity = get_jwt_identity()
        logger.debug(towername)
        towerVal = get_tower_with_towername(tower_name=towername, user_id=identity['id'], session=session)
        if isinstance(towerVal, str):  # In case create_tower returned an error message
            return jsonify({'error': towerVal}), 400
        logger.debug(towerVal)

        if not towerVal:
            return jsonify({'error': 'File not found'}), 404

        rasterData = towerVal.raster_data
        if rasterData:
            bounds = {
                "north": rasterData.north_bound,
                "south": rasterData.south_bound,
                "east": rasterData.east_bound,
                "west": rasterData.west_bound,
            }
            return jsonify({'Status': 'OK', 'bounds': bounds}), 200 
        else:
            return jsonify({'error': 'Raster data not found'}), 404
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()

@app.route('/api/upload-tower-csv', methods=['POST'])
@jwt_required()
def upload_csv():
    try:
        identity = get_jwt_identity()
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        logger.debug('reached file check')
        if file and file.filename.endswith('.csv'):
            # Read the file content
            tower_data = read_tower_csv(file)
            logger.debug(tower_data)
            if not isinstance(tower_data, str):
                return jsonify(tower_data), 200
            else:
                return jsonify({'error': tower_data}), 400
        else:
            return jsonify({'error': 'Invalid file'}), 400
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401

# For docker
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=backend_port, debug=True)


# if __name__ == '__main__':
#     app.run(port=5000, debug=True)