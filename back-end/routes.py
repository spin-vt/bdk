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
from celery import chain
from utils.settings import DATABASE_URL, COOKIE_EXP_TIME, backend_port
from database.sessions import Session
from controllers.database_controller import fabric_ops, kml_ops, user_ops, vt_ops, file_ops, folder_ops, mbtiles_ops, challenge_ops, editfile_ops
from utils.flask_app import app, jwt
from controllers.celery_controller.celery_config import celery 
from controllers.celery_controller.celery_tasks import process_data, deleteFiles, toggle_tiles, run_signalserver, raster2vector, preview_fabric_locaiton_coverage, async_folder_copy_for_import, add_files_to_folder
from utils.namingschemes import DATETIME_FORMAT, EXPORT_CSV_NAME_TEMPLATE, SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE
from controllers.signalserver_controller.signalserver_command_builder import runsig_command_builder
from controllers.database_controller.tower_ops import create_tower, get_tower_with_towername
from controllers.database_controller.towerinfo_ops import create_towerinfo
from controllers.database_controller.rasterdata_ops import create_rasterdata
from controllers.signalserver_controller.read_towerinfo import read_tower_csv
from utils.logger_config import logger
import json
from shapely.geometry import shape
# logger = logging.getLogger(__name__)



# logging.basicConfig(level=logging.DEBUG)
# app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
# app.config["JWT_SECRET_KEY"] = base64.b64encode(os.getenv('JWT_SECRET').encode())
# app.config["JWT_TOKEN_LOCATION"] = [os.getenv('JWT_TOKEN_LOCATION')]
# app.config['JWT_ACCESS_COOKIE_NAME'] = os.getenv('JWT_ACCESS_COOKIE_NAME')
# app.config['JWT_COOKIE_CSRF_PROTECT'] = False
# app.config['JWT_ACCESS_TOKEN_EXPIRES'] = COOKIE_EXP_TIME
# jwt = JWTManager(app)



db_name = os.environ.get("POSTGRES_DB")
db_user = os.environ.get("POSTGRES_USER")
db_password = os.environ.get("POSTGRES_PASSWORD")
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')

@app.route("/api/served-data/<folderid>", methods=['GET'])
@jwt_required()
def get_number_records(folderid):
    folderid = int(folderid)
    session = Session()
    try:
        identity = get_jwt_identity()
        if folderid < 0:
            return jsonify({'error': 'Filling ID is invalid'}), 400
        else:
            if not folder_ops.folder_belongs_to_organization(folderid, identity['id'], session):
                return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400

            return jsonify(kml_ops.get_kml_data(folderid=folderid, session=session)), 200
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()

@app.route('/api/submit-data/<folderid>', methods=['POST', 'GET'])
@jwt_required()
def submit_data(folderid):
    session = Session()
    try:
        identity = get_jwt_identity()
        folderid = int(folderid)
            
        if 'file' not in request.files:
            return jsonify({'Status': "Failed, no file uploaded"}), 400

        files = request.files.getlist('file')
        if len(files) <= 0:
            return jsonify({'Status': "Failed, no file uploaded"}), 400

        file_data_list = request.form.getlist('fileData')

        userVal = user_ops.get_user_with_id(identity['id'], session=session)
        import_folder_id = int(request.form.get('importFolder'))
        logger.debug(f"import folder id is {import_folder_id}")
        # Prepare data for the task
        file_contents = [(f.filename, base64.b64encode(f.read()).decode('utf-8'), data) for f, data in zip(files, file_data_list)]
        if folderid == -1:
            deadline = request.form.get('deadline')
            if not deadline:
                return jsonify({'Status': "Failed, no deadline provided"}), 400

            # Attempt to parse the deadline to ensure it's valid
            try:
                deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'Status': "Failed, invalid deadline format"}), 400
            
            if import_folder_id != -1:
                if not folder_ops.folder_belongs_to_organization(import_folder_id, identity['id'], session):
                    return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400
                # Asynchronous copy and create new folder with deadline
                logger.debug("here 1")
                task_chain = chain(
                    async_folder_copy_for_import.s(userVal.id, import_folder_id, deadline),
                    add_files_to_folder.s(file_contents=file_contents),
                    process_data.s(recompute=True)
                )
                
            else:
                # Create new folder with deadline
                logger.debug("here 2")
                new_folder_name = f"Filing for Deadline {deadline_date}"
                folderVal = folder_ops.create_folder(new_folder_name, userVal.organization_id, deadline_date, 'upload', session)
                session.commit()

                task_chain = chain(
                    add_files_to_folder.s(folderVal.id, file_contents),
                    process_data.s(recompute=False)
                )
            
        else:
            logger.debug("here 3")
            if not folder_ops.folder_belongs_to_organization(folderid, identity['id'], session):
                return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400
            task_chain = chain(
                add_files_to_folder.s(folderid, file_contents),
                process_data.s(recompute=False)
            )

        result = task_chain.apply_async()
        return jsonify({'Status': "OK", 'task_id': result.id}), 200 # return task id to the client
    
        
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    except ValueError as ve:
    # Handle specific errors, e.g., value errors
        logger.debug(ve)
        return jsonify({'Status': "Failed due to bad value", 'error': str(ve)}), 400
    except Exception as e:
        # General catch-all for other exceptions
        logger.debug(e)
        session.rollback()  # Rollback the session in case of error
        return jsonify({'Status': "Failed, server failed", 'error': str(e)}), 500
    finally:
        session.close()  # Always close the session at the end




@app.route('/api/status/<task_id>')
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
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'status': task.result
        }
    else:
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    return jsonify(response)

@app.route('/api')
def home():
    response_body = {
        "name": "Success!",
        "message": "Backend successfully connected to frontend"
    }

    return response_body


@app.route('/api/search/<folderid>', methods=['GET'])
@jwt_required()
def search_location(folderid):
    query = request.args.get('query').upper()
    folderid = int(folderid)
    try:
        identity = get_jwt_identity()
        session = Session()
        try:
            userVal = user_ops.get_user_with_id(identity['id'], session)
            if not folder_ops.folder_belongs_to_organization(folderid, identity['id'], session):
                return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400

            results_dict = fabric_ops.address_query(folderid, query, session)
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


@app.route('/api/exportFiling/<folderid>', methods=['GET'])
@jwt_required()
def exportFiling(folderid):
    try:
        identity = get_jwt_identity()
        folderid = int(folderid)
        session = Session()
        try:
            userVal = user_ops.get_user_with_id(identity['id'], session)
            if not folder_ops.folder_belongs_to_organization(folderid, identity['id'], session):
                return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400
            
            csv_output = kml_ops.export(userVal.id, folderid, userVal.provider_id, userVal.brand_name, session)

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
    
@app.route('/api/exportChallenge', methods=['GET'])
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


@app.route("/api/tiles/<folder_id>/<zoom>/<x>/<y>.pbf")
@jwt_required()
def serve_tile_with_folderid(folder_id, zoom, x, y):
    if not folder_id:
        return Response('No tile found', status=404)
    if folder_id == -1:
        return Response('No tile found', status=404)
    folder_id = int(folder_id)
    identity = get_jwt_identity()

    session = Session()
    if not folder_ops.folder_belongs_to_organization(folder_id, identity['id'], session):
        session.close()
        return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400
    session.close()

    zoom = int(zoom)
    x = int(x)
    y = int(y)
    y = (2**zoom - 1) - y

    tile = vt_ops.retrieve_tiles(zoom, x, y, identity['id'], folder_id)

    if tile is None:
        return Response('No tile found', status=404)
        
    response = make_response(bytes(tile[0]))    
    response.headers['Content-Type'] = 'application/x-protobuf'
    response.headers['Content-Encoding'] = 'gzip'  
    return response



@app.route('/api/toggle-markers', methods=['POST'])
@jwt_required()
def toggle_markers():
    try:
        request_data = request.json
        markers = request_data['marker']
        folderid = request_data['folderid']
        polygonfeatures = request_data['polygonfeatures']
        logger.info(polygonfeatures)
        if folderid == -1:
            return jsonify({'error': 'Invalid folder id'}), 400
        
        identity = get_jwt_identity()
        session = Session()
        if not folder_ops.folder_belongs_to_organization(folderid, identity['id'], session):
                session.close()
                return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400
        session.close()


        task = toggle_tiles.apply_async(args=[markers, identity['id'], folderid, polygonfeatures])
        return jsonify({'Status': "OK", 'task_id': task.id}), 200
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401


@app.route('/api/files', methods=['GET'])
@jwt_required()
def get_files():
    try:
        identity = get_jwt_identity()
        # Verify user own this folder
        folder_ID = int(request.args.get('folder_ID'))
        session = Session()

        if not folder_ops.folder_belongs_to_organization(folder_ID, identity['id'], session):
                return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400
        
        if folder_ID:
            filesinfo = file_ops.get_filesinfo_in_folder(folder_ID, session=session)
            if not filesinfo:
                return jsonify({'error': 'No files found'}), 404
            return jsonify(filesinfo), 200
        else:
            return jsonify({'error': 'No files found'}), 404
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()

@app.route('/api/editfiles', methods=['GET'])
@jwt_required()
def get_editfiles():
    try:
        identity = get_jwt_identity()
        # Verify user own this folder
        folder_ID = int(request.args.get('folder_ID'))
        session = Session()

        if not folder_ops.folder_belongs_to_organization(folder_ID, identity['id'], session):
            return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400

        if folder_ID:
            filesinfo = editfile_ops.get_editfilesinfo_in_folder(folder_ID, session=session)
            if not filesinfo:
                return jsonify({'error': 'No files found'}), 404
            return jsonify(filesinfo), 200
        else:
            return jsonify({'error': 'No files found'}), 404
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()

@app.route('/api/folders-with-deadlines', methods=['GET'])
@jwt_required()
def get_folders_with_deadlines():
    try:
        identity = get_jwt_identity()
        user_id = identity['id']
        session = Session()
        userVal = user_ops.get_user_with_id(userid=user_id, session=session)
        folders = folder_ops.get_folders_by_type_for_org(userVal.organization_id, 'upload', session)
        
        folder_info = [{
            'folder_id': folder.id,
            'name': folder.name,
            'deadline': folder.deadline.strftime('%Y-%m-%d') if folder.deadline else None
        } for folder in folders]

        return jsonify(folder_info), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/get-last-upload-folder', methods=['GET'])
@jwt_required()
def get_last_folder():
    try:
        identity = get_jwt_identity()
        session = Session()
        user_id = identity['id']
        userVal = user_ops.get_user_with_id(userid=user_id, session=session)
        # Hackey way to use this method to get the lastest filing of user
        folderVal = folder_ops.get_upload_folder(orgid=userVal.organization_id, session=session)
        if not folderVal:
            folderid = -1
        else:
            folderid = folderVal.id
        return jsonify(folderid), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Change database schema to fix bug of not able to edit file info for file with no coverage
@app.route('/api/networkfiles/<int:folder_id>', methods=['GET'])
@jwt_required()
def get_network_files(folder_id):
    try:
        identity = get_jwt_identity()
        session = Session()
        # Not using folder_id for now, it can be implemented along with
        # multi-filing support
        folder_id = int(folder_id) 

        if not folder_ops.folder_belongs_to_organization(folder_id, identity['id'], session):
            return jsonify({'error': 'You are accessing a filing not belong to your organization'}), 400
        
        files = file_ops.get_all_network_files_for_fileinfoedit_table(folder_id, session)
        files_data = []
        for file in files:
            # Assuming each file has at least one kml_data or it's an empty list
            kml_data = file.kml_data[0] if file.kml_data else None
            file_info = {
                'id': file.id,
                'name': file.name,
                'type': file.type,
            }
            if kml_data:
                file_info['network_info'] = {
                    'maxDownloadNetwork': kml_data.maxDownloadNetwork,
                    'maxDownloadSpeed': kml_data.maxDownloadSpeed,
                    'maxUploadSpeed': kml_data.maxUploadSpeed,
                    'techType': kml_data.techType,
                    'latency': kml_data.latency,
                    'category': kml_data.category
                }
            files_data.append(file_info)
        return jsonify(files_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/updateNetworkFile/<int:file_id>', methods=['POST'])
@jwt_required()
def update_network_file(file_id):
    try:
        data = request.json
        identity = get_jwt_identity()
        session = Session()
        file_id = int(file_id)
        
        if not file_ops.file_belongs_to_organization(file_id=file_id, user_id=identity['id'], session=session):
            return jsonify({'error': 'You are accessing a file not belong to your organization'}), 400

        file = file_ops.get_file_with_id(file_id, session)
        if not file:
            return jsonify({'error': 'File not found'}), 404

        kml_update = data.get('network_info', [])
        kml_entries = kml_ops.get_kml_data_by_file(file_id, session)
        for kml_entry in kml_entries:
            kml_entry.maxDownloadSpeed = kml_update['maxDownloadSpeed']
            kml_entry.maxUploadSpeed = kml_update['maxUploadSpeed']
            kml_entry.techType = kml_update['techType']
            kml_entry.latency = kml_update['latency']
            kml_entry.category = kml_update['category']

        session.commit()
        return jsonify({'success': True, 'message': 'File and its KML data updated successfully'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
    
@app.route('/api/delfiles/<int:fileid>', methods=['DELETE'])
@jwt_required()
def delete_files(fileid):
    fileid = int(fileid)
    try:
        identity = get_jwt_identity()
        
        session = Session()
        if not file_ops.file_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
            session.close()
            return jsonify({'error': 'You are accessing a file not belong to your organization'}), 400
        session.close()

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
        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)
        folders = folder_ops.get_folders_by_type_for_org(orgid=userVal.organization_id, foldertype='export', session=session)

        response_data = []
        for fldr in folders:
            exportcsv_in_folder = file_ops.get_files_by_type(folderid=fldr.id, filetype='export', session=session)
            # exportcsv_in_folder = file_ops.get_files_in_folder(folderid=fldr.id, session=session)

            # print(exportcsv_in_folder)
            for f in exportcsv_in_folder:
                file_data = {
                    "id": f.id,
                    "name": f.name,
                    "timestamp": f.timestamp,
                    "type": f.type,
                    "folder_id": f.folder_id
                }
                response_data.append(file_data)

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
    
@app.route('/api/submit-challenge', methods=['POST'])
def submit_challenge():
    data = request.json  # This will give you the entire JSON payload
    challenge_ops.writeToDB(data)
    return jsonify({"message": "Data processed!"}), 200

@app.route('/api/compute-challenge', methods=['GET', 'POST'])
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
        if not file_ops.file_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
            return jsonify({'error': 'You are accessing a file not belong to your organization'}), 400

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
        towerVal = create_tower(towername=data['towername'], userid=identity['id'])
        if isinstance(towerVal, str):  # In case create_tower returned an error message
            logger.debug(towerVal)
            return jsonify({'error': towerVal}), 400
        outfile_name = SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE.format(username=identity['username'], towername=data['towername'])
        del data['towername']
        command = runsig_command_builder(data, outfile_name)
        data['tower_id'] = towerVal.id

        tower_info_val = create_towerinfo(tower_info_data=data)
        if isinstance(tower_info_val, str):  # In case create_towerinfo returned an error message
            logger.debug(tower_info_val)
            return jsonify({'error': tower_info_val}), 400

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
        towerVal = get_tower_with_towername(tower_name=towername, user_id=identity['id'], session=session)
        if isinstance(towerVal, str):  # In case create_tower returned an error 
            logger.debug(towerVal)
            return jsonify({'error': towerVal}), 400
        
        if not towerVal:
            logger.debug('tower not found under towername')
            return jsonify({'error': 'File not found'}), 404

        rasterData = towerVal.raster_data
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

@app.route('/api/get-transparent-raster-image/<string:towername>', methods=['GET'])
@jwt_required()
def get_transparent_raster_image(towername):
    session = Session()
    try:
        identity = get_jwt_identity()
        towerVal = get_tower_with_towername(tower_name=towername, user_id=identity['id'], session=session)
        if isinstance(towerVal, str):  # In case create_tower returned an error 
            logger.debug(towerVal)
            return jsonify({'error': towerVal}), 400
        
        if not towerVal:
            logger.debug('tower not found under towername')
            return jsonify({'error': 'File not found'}), 404

        rasterData = towerVal.raster_data
        if rasterData:
            image_io = io.BytesIO(rasterData.transparent_image_data)
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
        towerVal = get_tower_with_towername(tower_name=towername, user_id=identity['id'], session=session)
        if isinstance(towerVal, str):  # In case create_tower returned an error message
            logger.debug(towerVal)
            return jsonify({'error': towerVal}), 400

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

@app.route('/api/get-loss-color-mapping/<string:towername>', methods=['GET'])
@jwt_required()
def get_loss_color_mapping(towername):
    session = Session()
    try:
        identity = get_jwt_identity()
        towerVal = get_tower_with_towername(tower_name=towername, user_id=identity['id'], session=session)
        if not towerVal:
            logger.debug('Tower not found under towername')
            return jsonify({'error': 'Mapping not found'}), 404

        rasterData = towerVal.raster_data
        if rasterData and rasterData.loss_color_mapping:
            # Now we can just return the JSON directly
            return jsonify(rasterData.loss_color_mapping), 200
        else:
            return jsonify({'error': 'Loss to color mapping not found'}), 404

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

        if file and file.filename.endswith('.csv'):
            # Read the file content
            tower_data = read_tower_csv(file)
            if not isinstance(tower_data, str):
                return jsonify(tower_data), 200
            else:
                return jsonify({'error': tower_data}), 400
        else:
            return jsonify({'error': 'Invalid file'}), 400
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    
@app.route('/api/downloadexport/<int:fileid>', methods=['GET'])
@jwt_required()
def download_export(fileid):
    fileid = int(fileid)
    session = Session()
    try:
        identity = get_jwt_identity()
        if not file_ops.file_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
            return jsonify({'error': 'You are accessing a file not belong to your organization'}), 400

        fileVal = file_ops.get_file_with_id(fileid=fileid, session=session)
        if not fileVal:
            return jsonify({'error': 'File not found'}), 404
        downfile = io.BytesIO(fileVal.data)
        downfile.seek(0)
        return send_file(
                downfile,
                download_name=fileVal.name,
                as_attachment=True,
                mimetype="text/csv"
            )
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()

@app.route('/api/compute-wireless-prediction-fabric-coverage', methods=['POST'])
@jwt_required()
def compute_wireless_prediction_fabric_coverage():
    try:
        identity = get_jwt_identity()
        data = request.json
        outfile_name = SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE.format(username=identity['username'], towername=data['towername'])
        task = raster2vector.apply_async(args=[data, identity['id'], outfile_name]) # store the AsyncResult instance
        kml_filename = outfile_name + '.kml'
        return jsonify({'Status': "OK", 'task_id': task.id, 'kml_filename': kml_filename}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    
@app.route('/api/preview-wireless-prediction-fabric-coverage', methods=['POST'])
@jwt_required()
def preview_wireless_prediction_fabric_coverage():
    try:
        identity = get_jwt_identity()
        data = request.json
        outfile_name = SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE.format(username=identity['username'], towername=data['towername'])
        task = preview_fabric_locaiton_coverage.apply_async(args=[data, identity['id'], outfile_name]) # store the AsyncResult instance
        kml_filename = outfile_name + '.kml'
        return jsonify({'Status': "OK", 'task_id': task.id, 'kml_filename': kml_filename}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401

@app.route('/api/download-kmlfile/<string:kml_filename>', methods=['GET'])
@jwt_required()
def download_kmlfile(kml_filename):
    session = Session()
    try:
        identity = get_jwt_identity()
        folderVal = folder_ops.get_upload_folder(userid=identity['id'], folderid=None, session=session)
        fileVal = file_ops.get_file_with_name(filename=kml_filename, folderid=folderVal.id, session=session)
        if isinstance(fileVal, str):  # In case create_tower returned an error message
            logger.debug(fileVal)
            return jsonify({'error': fileVal}), 400

        if not fileVal:
            return jsonify({'error': 'File not found'}), 404

        
        downfile = io.BytesIO(fileVal.data)
        downfile.seek(0)
        return send_file(
                downfile,
                download_name=fileVal.name,
                as_attachment=True,
                mimetype="text/kml"
            )
        
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()

@app.route('/api/get-preview-geojson/<string:filename>', methods=['GET'])
@jwt_required()
def get_preview_geojson(filename):
    try:
        identity = get_jwt_identity()
        with open(filename, 'r') as file:
            geojson_data = json.load(file)  # Read and parse the JSON file
        os.remove(filename)
        return jsonify(geojson_data)  # Return the JSON data
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401

@app.route('/api/get-edit-geojson/<int:fileid>', methods=['GET'])
@jwt_required()
def get_edit_geojson(fileid):
    session = Session()
    try:
        identity = get_jwt_identity()
        fileid = int(fileid)
        if not file_ops.file_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
            return jsonify({'error': 'You are accessing a file not belong to your organization'}), 400

        editfile = editfile_ops.get_editfile_with_id(fileid=fileid, session=session)
       
        if editfile is None:
            return jsonify({'error': 'File not found'}), 404
        
        # Decode the binary data to string assuming it's stored in UTF-8 encoded JSON format
        geojson_data = json.loads(editfile.data.decode('utf-8'))
        return jsonify(geojson_data), 200
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404
    except NoAuthorizationError:
        return jsonify({'error': 'Token is invalid or expired'}), 401
    finally:
        session.close()


@app.route('/api/get-edit-geojson-centroid/<int:fileid>', methods=['GET'])
@jwt_required()
def get_edit_geojson_centroid(fileid):
    session = Session()
    try:
        identity = get_jwt_identity()
        if not file_ops.file_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
            return jsonify({'error': 'You are accessing a file not belong to your organization'}), 400

        editfile = editfile_ops.get_editfile_with_id(fileid=fileid, session=session)

        if editfile is None:
            return jsonify({'error': 'File not found'}), 404

        # Decode the binary data to a JSON object
        geojson_object = json.loads(editfile.data.decode('utf-8'))
        
        # Calculate the centroid of the polygon
        polygon = shape(geojson_object['geometry'])
        centroid = polygon.centroid
        centroid_coords = {'latitude': centroid.y, 'longitude': centroid.x}
        # Include centroid coordinates in the response
        return jsonify(centroid_coords), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch file', 'details': str(e)}), 500
    finally:
        session.close()
    
# For docker
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=backend_port, debug=True)


# if __name__ == '__main__':
#     app.run(port=5000, debug=True)