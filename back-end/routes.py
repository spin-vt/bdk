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
from jwt import ExpiredSignatureError
from datetime import datetime, timedelta
import shortuuid
from celery.result import AsyncResult
from celery import chain
from utils.settings import DATABASE_URL, COOKIE_EXP_TIME, backend_port, IN_PRODUCTION
from database.sessions import Session
from controllers.database_controller import organization_ops, fabric_ops, kml_ops, user_ops, vt_ops, file_ops, folder_ops, mbtiles_ops, challenge_ops, editfile_ops, celerytaskinfo_ops
from utils.flask_app import app, mail
from controllers.celery_controller.celery_config import celery 
from controllers.celery_controller.celery_tasks import process_data, async_delete_files, toggle_tiles, run_signalserver, raster2vector, preview_fabric_locaiton_coverage, async_folder_copy_for_import, add_files_to_folder, async_folder_delete
from utils.namingschemes import DATETIME_FORMAT, DATE_FORMAT, EXPORT_CSV_NAME_TEMPLATE, SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE
from controllers.signalserver_controller.signalserver_command_builder import runsig_command_builder
from controllers.database_controller.tower_ops import create_tower, get_tower_with_towername
from controllers.database_controller.towerinfo_ops import create_towerinfo
from controllers.database_controller.rasterdata_ops import create_rasterdata
from controllers.signalserver_controller.read_towerinfo import read_tower_csv
from utils.logger_config import logger
import json
from shapely.geometry import shape
from flask_mail import Message
import jwt


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
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
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
            return jsonify({'status': "error", 'message': "no file uploaded"}), 400

        files = request.files.getlist('file')
        if len(files) <= 0:
            return jsonify({'status': "error", 'message': "no file uploaded"}), 400

        operation_detail = "Added more files to a filing"
        file_data_list = request.form.getlist('fileData')
        filenames = []
        for file_data_str in file_data_list:
            try:
                file_data = json.loads(file_data_str)  # Decode JSON string to Python dictionary
                filename, file_extension = os.path.splitext(file_data['name'])
                if file_extension not in ['.csv', '.kml', '.geojson']:
                    return jsonify({'status': 'error', 'message': "Invalid file extension. Allowed extensions are .csv, .kml, and .geojson"}), 400
                
                if not file_data['name'].endswith('.csv'):  # Validate speeds only for non-csv files
                    try:
                        # Parse speeds as integers
                        download_speed = int(file_data['downloadSpeed'])
                        upload_speed = int(file_data['uploadSpeed'])
                    except (ValueError, KeyError):
                        return jsonify({'status': 'error', 'message': "Please enter valid integer values for download and upload speeds"}), 400
                    try:
                        latency = int(file_data['latency'])
                        techType = int(file_data['techType'])
                    except (ValueError, KeyError):
                        return jsonify({'status': 'error', 'message': "Please enter valid values for latency and techTypes"}), 400
                
                filenames.append(file_data['name'])  # Collect the filename
            except json.JSONDecodeError:
                return jsonify({'status': 'error', 'message': "Invalid JSON format in file data"}), 400

        userVal = user_ops.get_user_with_id(identity['id'], session=session)

        if not userVal.verified:
            return jsonify({'status': 'error', 'message': "Please Verify your email to start working on a filing"}), 400
        if not userVal.organization_id:
            return jsonify({'status': 'error', 'message': "Create or join an organization to start working on a filing"}), 400
        import_folder_id = int(request.form.get('importFolder'))
        # Prepare data for the task
        file_contents = [(f.filename, base64.b64encode(f.read()).decode('utf-8'), data) for f, data in zip(files, file_data_list)]
        if folderid == -1:
            deadline = request.form.get('deadline')
            if not deadline:
                return jsonify({'status': "error", "message": "operation failed, no deadline provided"}), 400

            # Attempt to parse the deadline to ensure it's valid
            try:
                deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'status': "error", "message": "invalid deadline format"}), 400
            
            if import_folder_id != -1:
                if not folder_ops.folder_belongs_to_organization(import_folder_id, identity['id'], session):
                    return jsonify({'status': 'error', "message": 'Operation failed because you are accessing a filing not belong to your organization'}), 400
                # Asynchronous copy and create new folder with deadline
                logger.info("In operation 3 of upload: create a new filing by importing from previous filings")
                task_chain = chain(
                    async_folder_copy_for_import.s(import_folder_id, deadline_date),
                    add_files_to_folder.s(file_contents=file_contents),
                    process_data.s(operation=3)
                )

                import_folderval = folder_ops.get_folder_with_id(import_folder_id, session=session)
                operation_detail = f"Create a new Filing by importing from filing with deadline {import_folderval.deadline.strftime('%Y-%m')}"
                
            else:
                # Create new folder with deadline
                logger.info("In operation 2 of upload: create a new filing from scratch")
                new_folder_name = f"Filing for Deadline {deadline_date}"
                folderVal = folder_ops.create_folder(new_folder_name, userVal.organization_id, deadline_date, 'upload', session)
                session.commit()

                task_chain = chain(
                    add_files_to_folder.s(folderVal.id, file_contents),
                    process_data.si(folderid=folderVal.id, operation=2)
                )

                operation_detail = f"Create a new filing"
            
        else:
            logger.info("In operation 1 of upload: adding more files to a filing")
            if not folder_ops.folder_belongs_to_organization(folderid, identity['id'], session):
                return jsonify({'status': 'error', "message": 'Operation failed because you are accessing a filing not belong to your organization'}), 400
            task_chain = chain(
                add_files_to_folder.s(folderid, file_contents),
                process_data.si(folderid=folderid, operation=1)
            )

            operation_detail = "Add more files to a filing"

        result = task_chain.apply_async()

        if folderid != -1:
            deadline = folderVal.deadline
        else:
            deadline_str = request.form.get('deadline')
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()

        concatenated_filenames = ", ".join(filenames)
        celerytaskinfo_ops.create_celery_taskinfo(task_id=result.task_id, status='PENDING', operation_type="Upload", operation_detail=operation_detail, user_email=userVal.email, organization_id=userVal.organization_id, folder_deadline=deadline, session=session, files_changed=concatenated_filenames)
        return jsonify({'status': "success", 'task_id': result.id}), 200 # return task id to the client
    
        
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except ValueError as ve:
    # Handle specific errors, e.g., value errors
        logger.debug(ve)
        return jsonify({'status': "error", 'message': str(ve)}), 400
    except Exception as e:
        # General catch-all for other exceptions
        logger.debug(e)
        session.rollback()  # Rollback the session in case of error
        session.close()
        return jsonify({'status': "error", 'message': str(e)}), 500
    finally:
        session.close()  # Always close the session at the end

@app.route('/api/user-tasks', methods=['GET'])
@jwt_required()
def get_user_tasks():
    session = Session()
    try:
        identity = get_jwt_identity()
        
        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)
        if not userVal:
            return jsonify({'status': 'error', 'message': 'User not found'}), 400
        if not userVal.organization:
            return jsonify({'status': 'error', 'message': 'User not associated with organization'}), 400

        in_progress_tasks, finished_tasks = celerytaskinfo_ops.get_celerytasksinfo_for_org(orgid=userVal.organization_id, session=session)
        
        return jsonify({
            'status': 'success',
            'in_progress_tasks': in_progress_tasks,
            'finished_tasks': finished_tasks
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()

@app.route('/api/estimated-task-runtime/<taskid>', methods=['GET'])
@jwt_required()
def get_estimated_task_runtime(taskid):
    session = Session()
    try:
        identity = get_jwt_identity()
        taskid = str(taskid)
        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)
        if not userVal:
            return jsonify({'status': 'error', 'message': 'User not found'}), 400
        if not userVal.organization:
            return jsonify({'status': 'error', 'message': 'User not associated with organization'}), 400
        if not celerytaskinfo_ops.task_belongs_to_organization(task_id=taskid, user_id=userVal.id, session=session):
            return jsonify({'status': 'error', 'message': 'You are accessing a task not belong to your organization'}), 400

        estimated_runtime_seconds = celerytaskinfo_ops.get_estimated_runtime_for_task(task_id=taskid, session=session)
        
        return jsonify({
            'status': 'success',
            'estimated_runtime': estimated_runtime_seconds
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()

@app.route('/api/update-task-status/<taskid>', methods=['POST'])
@jwt_required()
def update_task_status(taskid):
    session = Session()
    try:
        identity = get_jwt_identity()
        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)
        taskid = str(taskid)
        if not userVal:
            return jsonify({'status': 'error', 'message': 'User not found'}), 400
        
        if not userVal.organization:
            return jsonify({'status': 'error', 'message': 'User not associated with organization'}), 400
        
        if not celerytaskinfo_ops.task_belongs_to_organization(task_id=taskid, user_id=userVal.id, session=session):
            return jsonify({'status': 'error', 'message': 'You are accessing a task not belonging to your organization'}), 400
        
        # Get the new status from the request body
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'status': 'error', 'message': 'Status is required'}), 400
        
        # Update the task status
        celerytaskinfo_ops.update_task_status(task_id=taskid, status=new_status, session=session)
        
        return jsonify({'status': 'success', 'message': 'Task status updated successfully'}), 200
    
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
    finally:
        session.close()

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
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401





def create_email_token(userid, email, operation, org_id=-1):
    expiration = datetime.now() + timedelta(minutes=15)
    email_token = jwt.encode(
        {'sub': {'id': userid, 'email': email, 'operation': operation, 'org_id': org_id}, 'exp': expiration},
        app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )
    return email_token

def send_verification_email_with_token(email, token, title, content, join_org=False, joining_email=""):
    msg = Message(title, recipients=[email])
    msg.content_subtype = "html"  # This sets the message content type to HTML

    if join_org:
        message_start = f'Dear BDK User,<br><br>A user has requested to join your organization. Please forward the following token to {joining_email} and request them to enter it on the BDK website to '
    else:
        message_start = 'Dear BDK User,<br><br>Please enter the following token on the BDK website to '

    message_body = f'{message_start}{content}.<br><br><strong>Verification Token:</strong><br><pre style="color: #00AAFF; background-color: #f0f0f0; padding: 10px; border-radius: 5px;">{token}</pre><br><br>Thank you,<br>BDK Team'
    
    msg.html = message_body.strip()  # Use msg.html for HTML content
    mail.send(msg)

@app.route('/api/request_password_reset', methods=['POST'])
def request_password_reset():
    session = Session()
    data = request.get_json()
    email = data.get('email')
    user = user_ops.get_user_with_email(email, session)

    if not user:
        session.close()
        return jsonify({'status': 'error', 'message': 'Email address not found.'}), 400

    email_token = create_email_token(userid=user.id, email=user.email, operation="reset_password")
    send_verification_email_with_token(email=email, token=email_token, title='Reset Your Password for BDK', content='reset your password')
    session.close()
    return jsonify({'status': 'success', 'message': 'Verification email resent.'}), 200

@app.route('/api/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('newPassword')

    try:
        session = Session()
        decoded_token = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        user_id = decoded_token['sub']['id']
        email = decoded_token['sub']['email']
        if user_ops.verify_user_email(user_id, email, session, False):
            user_ops.reset_user_password(user_id, new_password)
            return jsonify({'status': 'success', 'message': 'Password reset successfully.'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid token.'}), 400
    except jwt.ExpiredSignatureError:
        return jsonify({'status': 'error', 'message': 'The token has expired.'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Invalid token.'}), 400
    finally:
        session.close()


@app.route('/api/verify_token', methods=['POST'])
def verify_token():
    try:
        session = Session()
        data = request.get_json()
        token = data.get('token')

        # Decode the token using pyjwt directly
        decoded_token = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])

        user_id = decoded_token['sub']['id']
        email = decoded_token['sub']['email']
        operation = decoded_token['sub']['operation']

        logger.debug(operation)

        setVerified = True if operation == 'email_address_verification' else False
        if user_ops.verify_user_email(user_id, email, session, setVerified):
            if operation == "join_organization":
                org_id = int(decoded_token['sub']['org_id'])
                logger.debug(org_id)
                if org_id < 0:
                    return jsonify({'status': 'error', 'message': 'Invalid organization id.'}), 400
                user_ops.add_user_to_organization(user_id, org_id, session)
                    

            access_token = create_access_token(identity={'id': user_id})
            response = make_response(jsonify({'status': 'success', 'token': access_token}))
            if IN_PRODUCTION:
                response.set_cookie('token', access_token, httponly=True, samesite='Lax', secure=True)
            else:
                response.set_cookie('token', access_token, httponly=False, samesite='Lax', secure=False)
            return response, 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid token.'}), 400
    except ExpiredSignatureError:
        return jsonify({'status': 'error', 'message': 'The token has expired.'}), 400
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid token.'}), 400
    finally:
        session.close()

@app.route('/api/send_email_verification', methods=['POST'])
def send_email_verification():
    session = Session()
    data = request.get_json()
    email = data.get('email')
    user = user_ops.get_user_with_email(email, session)

    if not user:
        session.close()
        return jsonify({'status': 'error', 'message': 'Email address not found.'}), 400

    email_token = create_email_token(userid=user.id, email=user.email, operation="email_address_verification")
    send_verification_email_with_token(email=email, token=email_token, title='Verify Your Email Address for BDK', content='verify your email address')
    session.close()
    return jsonify({'status': 'success', 'message': 'Verification email sent.'}), 200

@app.route('/api/create_organization', methods=['POST'])
@jwt_required()
def create_organization():
    try:
        current_user = get_jwt_identity()
        session = Session()
        data = request.get_json()
        org_name = data.get('orgName')
        user = user_ops.get_user_with_id(current_user['id'], session)

        if not user.verified:
            return jsonify({'status': 'error', 'message': 'Please verify your email address before creating an organization.'}), 400

        if not org_name:
            return jsonify({'status': 'error', 'message': 'Please enter an organization name.'}), 400

        existing_org = organization_ops.get_organization_with_orgname(org_name=org_name, session=session)
        if existing_org:
            return jsonify({'status': 'error', 'message': 'Organization name already exists.'}), 400

        new_org = organization_ops.create_organization(org_name=org_name, session=session)
        
        user.organization_id = new_org.id
        user.is_admin = True
        session.commit()

        return jsonify({'status': 'success', 'message': 'Organization created successfully!'}), 200
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        logger.error(f"Error creating organization: {e}")
        session.rollback()
        return jsonify({'status': 'error', 'message': 'An error occurred while creating the organization.'}), 500
    finally:
        session.close()

@app.route('/api/join_organization', methods=['POST'])
@jwt_required()
def join_organization():
    try:
        current_user = get_jwt_identity()

        session = Session()
        data = request.get_json()
        org_name = data.get('name')
        user = user_ops.get_user_with_id(current_user['id'], session)
        
        if not user.verified:
            return jsonify({'status': 'error', 'message': 'Please verify your email address before joining an organization.'}), 400

        if not org_name:
            return jsonify({'status': 'error', 'message': 'Please enter an organization name.'}), 400

        org = organization_ops.get_organization_with_orgname(org_name=org_name, session=session)
        if not org:
            return jsonify({'status': 'error', 'message': 'Organization not found.'}), 400

        admin = organization_ops.get_admin_user_for_organization(org_id=org.id, session=session)
        if not admin:
            return jsonify({'status': 'error', 'message': 'Organization admin not found.'}), 400

        email_token = create_email_token(userid=user.id, email=user.email, operation="join_organization", org_id=org.id)
        send_verification_email_with_token(email=admin.email, token=email_token, title='Organization Join Request for BDK', content=f'finish their organization join request', join_org=True, joining_email=user.email)

        return jsonify({'status': 'success', 'message': 'Join request sent to organization admin.'}), 200
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        logger.error(f"Error joining organization: {e}")
        session.rollback()
        return jsonify({'status': 'error', 'message': 'An error occurred while trying to join the organization.'}), 500
    finally:
        session.close()

@app.route('/api/delete_organization', methods=['DELETE'])
@jwt_required()
def delete_organization():
    try:
        identity = get_jwt_identity()
        session = Session()
        data = request.get_json()
        orgName = data.get('organizationName')

        userVal = user_ops.get_user_with_id(identity['id'], session=session)
        organization = userVal.organization

        if not organization:
            return jsonify({'status': 'error', 'message': 'Organization not found'}), 400
        
        if not organization.name == orgName:
            return jsonify({'status': 'error', 'message': 'Organization not found'}), 400
        
        users = organization_ops.get_all_users_for_organization(org_id=organization.id, session=session)
        for user in users:
            user.organization_id = None
        
        session.delete(organization)
        session.commit()
        

        return jsonify({'status': 'success', 'message': 'Organization deleted successfully'}), 200
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401

@app.route('/api/exit_organization', methods=['POST'])
@jwt_required()
def exit_organization():
    try:
        identity = get_jwt_identity()
        session = Session()

        user = user_ops.get_user_with_id(userid=identity['id'], session=session)
        data = request.get_json()
        orgName = data.get('organizationName')

        logger.debug(orgName)

        userVal = user_ops.get_user_with_id(identity['id'], session=session)
        organization = userVal.organization

        if not organization:
            return jsonify({'status': 'error', 'message': 'Organization not found'}), 400
        
        if not organization.name == orgName:
            return jsonify({'status': 'error', 'message': 'Organization not found'}), 400
        
        user.organization_id = None
        session.commit()

        return jsonify({'status': 'success', 'message': 'Exited organization successfully'}), 200
    
    except NoAuthorizationError:
            return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
        session.close()

@app.route('/api/register', methods=['POST'])
def register():
    session = Session()
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    response = user_ops.create_user_in_db(email, password, session)

    if 'error' in response:
        return jsonify({'status': 'error', 'message': response["error"]}), 400

    userVal = response["success"]
    access_token = create_access_token(identity={'id': userVal.id})

    response = make_response(jsonify({'status': 'success', 'token': access_token}))
    if IN_PRODUCTION:
        response.set_cookie('token', access_token, httponly=True, samesite='Lax', secure=True)
    else:
        response.set_cookie('token', access_token, httponly=False, samesite='Lax', secure=False)

    session.close()
    return response, 200


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    pword = data.get('password')

    # Needs a try catch to return the correct message
    user = user_ops.get_user_with_email(email)

    if user is not None and check_password_hash(user.password, pword):
        user_id = user.id
        access_token = create_access_token(identity={'id': user_id})
        response = make_response(jsonify({'status': 'success', 'token': access_token}))
        if IN_PRODUCTION:
            response.set_cookie('token', access_token, httponly=True, samesite='Lax', secure=True)
        else:
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
    session = Session()
    try:
        identity = get_jwt_identity()

        userVal = user_ops.get_user_with_id(identity['id'], session=session)
        if not userVal:
            return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
        userinfo = user_ops.get_userinfo_with_id(identity['id'], session=session)
        return jsonify({'status': 'success', 'userinfo': userinfo}), 200
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
        session.close()


@app.route('/api/exportFiling/<folderid>', methods=['GET'])
@jwt_required()
def exportFiling(folderid):
    try:
        identity = get_jwt_identity()
        folderid = int(folderid)
        session = Session()
        try:
            if folderid == -1:
                return jsonify({'status': 'error', 'message': 'Invalid filing requested'}), 400
            
            if not folder_ops.folder_belongs_to_organization(folderid, identity['id'], session):
                return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400
            

            folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
            providerid = folderVal.organization.provider_id
            brandname = folderVal.organization.brand_name
            deadline = folderVal.deadline.strftime(DATE_FORMAT)

            if not providerid or not brandname:
                return jsonify({'status': 'error', 'message': 'Please provide your provider ID and brand name'}), 400


            csv_output = kml_ops.export(folderid, providerid, brandname, deadline, session)

            if csv_output:
                download_name = EXPORT_CSV_NAME_TEMPLATE.format(brand_name=brandname, deadline=deadline)
                
                csv_output.seek(0)
                response = make_response(send_file(csv_output, as_attachment=True, download_name=download_name, mimetype="text/csv"))
                response.headers['Access-Control-Expose-Headers'] = "Content-Disposition"
                return response
            else:
                return jsonify({'status': 'error', "message": "internal server error"})
        except Exception as e:
            session.rollback()
            return {'status': 'error', 'message': str(e)}
        finally:
            session.close()
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    
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
        return jsonify({'status': 'error'})


@app.route("/api/tiles/<folder_id>/<zoom>/<x>/<y>.pbf")
@jwt_required()
def serve_tile_with_folderid(folder_id, zoom, x, y):
    if not folder_id:
        return Response('No tile found', status=404)
    try:
        folder_id = int(folder_id)
    except ValueError:
        return Response('No tile found', status=404)
    if folder_id == -1:
        return Response('No tile found', status=404)
    
    identity = get_jwt_identity()


    session = Session()
    if not folder_ops.folder_belongs_to_organization(folder_id, identity['id'], session):
        session.close()
        return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400
    session.close()

    zoom = int(zoom)
    x = int(x)
    y = int(y)
    y = (2**zoom - 1) - y

    tile = vt_ops.retrieve_tiles(zoom, x, y, folder_id)

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
        identity = get_jwt_identity()
        session = Session()
        request_data = request.json
        markers = request_data['marker']
        folderid = request_data['folderid']
        polygonfeatures = request_data['polygonfeatures']
        if folderid == -1:
            return jsonify({'status': 'error', 'message': 'Invalid folder id'}), 400
        
        userVal = user_ops.get_user_with_id(identity['id'], session=session)

        if not userVal.verified:
            return jsonify({'status': 'error', 'message': "Please Verify your email to start working on a filing"}), 400
        if not userVal.organization_id:
            return jsonify({'status': 'error', 'message': "Create or join an organization to start working on a filing"}), 400
        if not folder_ops.folder_belongs_to_organization(folderid, identity['id'], session):
            session.close()
            return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400
        

        folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        
        # Filter out points where editedFile is empty
        filtered_markers = []
        for polygon in markers:
            filtered_polygon = [point for point in polygon if point['editedFile'] and len(point['editedFile']) > 0]
            if filtered_polygon:
                filtered_markers.append(filtered_polygon)


        if len(filtered_markers) == 0:
            return jsonify({'status': 'error', 'message': "No valid edits submitted"}), 400
        
        # Generate concatenated_filenames
        all_filenames = set()
        for polygon in filtered_markers:
            for point in polygon:
                all_filenames.update(point['editedFile'])
        concatenated_filenames = ', '.join(sorted(all_filenames))
        logger.debug(polygonfeatures)
        result = toggle_tiles.apply_async(args=[filtered_markers, folderid, polygonfeatures])

        celerytaskinfo_ops.create_celery_taskinfo(task_id=result.task_id, status='PENDING', operation_type="Edit", operation_detail="Edit a filing", user_email=userVal.email, organization_id=userVal.organization_id, folder_deadline=folderVal.deadline, session=session, files_changed=concatenated_filenames)
        return jsonify({'status': "success"}), 200
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
        session.close()


@app.route('/api/files', methods=['GET'])
@jwt_required()
def get_files():
    try:
        identity = get_jwt_identity()
        # Verify user own this folder
        session = Session()
        try:
            folder_ID = int(request.args.get('folder_ID'))
        except ValueError:
            return jsonify({'status': 'error', 'message': 'folderID must be integer'}), 400

        if not folder_ops.folder_belongs_to_organization(folder_ID, identity['id'], session):
                return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400
        
        if folder_ID:
            filesinfo = file_ops.get_filesinfo_in_folder(folder_ID, session=session)
            return jsonify(filesinfo), 200
        else:  
            return jsonify({'status': 'error', 'message': 'Invalid request'}), 404
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
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
            return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400

        if folder_ID:
            filesinfo = editfile_ops.get_editfilesinfo_in_folder(folder_ID, session=session)
            
            return jsonify(filesinfo), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid request'}), 404
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
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
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
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
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Change database schema to fix bug of not able to edit file info for file with no coverage
@app.route('/api/networkfiles/<int:folder_id>', methods=['GET'])
@jwt_required()
def get_network_files(folder_id):
    try:
        identity = get_jwt_identity()
        session = Session()
        
        folder_id = int(folder_id) 

        if not folder_ops.folder_belongs_to_organization(folder_id, identity['id'], session):
            return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400
        
        files = file_ops.get_all_network_files_for_fileinfoedit_table(folder_id, session)
        files_data = []
        for file in files:
            filename_without_extension = os.path.splitext(file.name)[0]
            file_info = {
                'id': file.id,
                'name': filename_without_extension,
                'type': file.type,
                'maxDownloadSpeed': file.maxDownloadSpeed,
                'maxUploadSpeed': file.maxUploadSpeed,
                'techType': file.techType,
                'latency': file.latency,
                'category': file.category
            }
            
            files_data.append(file_info)
        return jsonify({'status': 'success', 'files_data': files_data})
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
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
            return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400

        file = file_ops.get_file_with_id(file_id, session)
        if not file:
            return jsonify({'status': 'error', 'message': 'File not found'}), 400

        try:
            int(data['maxDownloadSpeed']) if 'maxDownloadSpeed' in data else file.maxDownloadSpeed
            int(data['maxUploadSpeed']) if 'maxUploadSpeed' in data else file.maxUploadSpeed
        except ValueError:
            return jsonify({'status': 'error', 'message': 'maxDownloadSpeed and maxUploadSpeed must be integers'}), 400
        
        try:
            int(data['latency']) if 'latency' in data else file.latency
            int(data['techType']) if 'techType' in data else file.techType
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Please select valid tech types and latency'}), 400
        
        logger.debug(data)
        lowercase_type = data['type'].lower()
        if lowercase_type not in ['wired', 'wireless']:
            return jsonify({'status': 'error', 'message': 'Please select a valid type'}), 400
        name_or_type_changed = False

        # Separate the filename and extension
        file_root, file_ext = os.path.splitext(file.name)

        if file_root != data['name'] or file.type != lowercase_type:
            name_or_type_changed = True

        # Update the filename while keeping the original extension
        new_filename = data['name'] + file_ext

        file.name = new_filename
        file.type = lowercase_type
        file.maxDownloadSpeed = data['maxDownloadSpeed']
        file.maxUploadSpeed = data['maxUploadSpeed']
        file.techType = data['techType']
        file.latency = data['latency']
        file.category = data['category']
        kml_entries = kml_ops.get_kml_data_by_file(file_id, session)
        for kml_entry in kml_entries:
            kml_entry.maxDownloadSpeed = data['maxDownloadSpeed']
            kml_entry.maxUploadSpeed = data['maxUploadSpeed']
            kml_entry.techType = data['techType']
            kml_entry.latency = data['latency']
            kml_entry.category = data['category']

        session.commit()

        if name_or_type_changed:
            userVal = user_ops.get_user_with_id(identity['id'], session=session)
            result = process_data.apply_async(args=[file.folder_id, 4])
            folderVal = folder_ops.get_folder_with_id(folderid=file.folder_id, session=session)
            celerytaskinfo_ops.create_celery_taskinfo(task_id=result.task_id, status='PENDING', operation_type="Update", operation_detail="Update filename or filetype in a filing", user_email=userVal.email, organization_id=userVal.organization_id, folder_deadline=folderVal.deadline, session=session, files_changed=file.name)
        return jsonify({'status': 'success', 'message': 'File and its KML data updated successfully'}), 200
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    finally:
        session.close()

@app.route('/api/regenerate_map', methods=['POST'])
@jwt_required()
def regenerate_map():
    session = Session()
    try:
        identity = get_jwt_identity()
        request_data = request.json
        folderid = request_data['folderID']
        if not folder_ops.folder_belongs_to_organization(folder_id=folderid, user_id=identity['id'], session=session):
            return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400

        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)
        folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        deadline = folderVal.deadline
        result = process_data.apply_async(args=[folderid, 4])
        celerytaskinfo_ops.create_celery_taskinfo(task_id=result.task_id, status='PENDING', operation_type="Update", operation_detail="Regenerate Map", user_email=userVal.email, organization_id=userVal.organization_id, folder_deadline=deadline, session=session)
        return jsonify({'status': "success"}), 200 
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
        session.close()


    
@app.route('/api/delfiles', methods=['DELETE'])
@jwt_required()
def delete_files():
    try:
        data = request.get_json()
        file_ids = data.get('file_ids', [])
        editfile_ids = data.get('editfile_ids', [])
        identity = get_jwt_identity()
        

        logger.debug(file_ids)
        logger.debug(editfile_ids)

        if not file_ids and not editfile_ids:
            return jsonify({'status': 'error', 'message': 'Please check the files to delete'}), 400

        session = Session()

        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)
        
        if not userVal.verified:
            return jsonify({'status': 'error', 'message': "Please Verify your email to start working on a filing"}), 400
        if not userVal.organization_id:
            return jsonify({'status': 'error', 'message': "Create or join an organization to start working on a filing"}), 400
        
        for fileid in file_ids:
            fileid = int(fileid)
            if not file_ops.file_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
                session.close()
                return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400

        for editfileid in editfile_ids:
            editfileid = int(editfileid)
            if not editfile_ops.editfile_belongs_to_organization(file_id=editfileid, user_id=identity['id'], session=session):
                session.close()
                return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400
        
        filenames = []
        if file_ids:
            fileVal = file_ops.get_file_with_id(fileid=file_ids[0], session=session)
            folderid = fileVal.folder_id

            for fileid in file_ids:
                fileVal = file_ops.get_file_with_id(fileid=fileid, session=session)
                filenames.append(fileVal.name)

        else:
            editfileVal = editfile_ops.get_editfile_with_id(fileid=editfile_ids[0], session=session)
            folderid = editfileVal.folder_id

            for editfileid in editfile_ids:
                fileVal = editfile_ops.get_editfile_with_id(fileid=editfileid, session=session)
                filenames.append(fileVal.name)
        
        folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        deadline = folderVal.deadline
        concatenated_filenames = ", ".join(filenames)
        

        logger.info(f"folderid in delete files {folderid}")
        task_chain = chain(
            async_delete_files.s(file_ids=file_ids, editfile_ids=editfile_ids),
            process_data.si(folderid=folderid, operation=4)
        )
        result = task_chain.apply_async()
        celerytaskinfo_ops.create_celery_taskinfo(task_id=result.task_id, status='PENDING', operation_type="Delete", operation_detail="Delete files in a filing", user_email=userVal.email, organization_id=userVal.organization_id, folder_deadline=deadline, session=session, files_changed=concatenated_filenames)
        return jsonify({'status': "success", 'task_id': result.id}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
        session.close()

    
@app.route('/api/export', methods=['GET'])
@jwt_required()
def get_exported_folders():
    try:
        identity = get_jwt_identity()
        session = Session()
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
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
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
            return jsonify({'status': 'error', 'message': 'You are accessing a file not belong to your organization'}), 400
        
        fileVal = file_ops.get_file_with_id(fileid=fileid, session=session)
        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)
        
        folderVal = folder_ops.get_folder_with_id(fileVal.folder_id, session=session)
        deadline = folderVal.deadline
        result = async_folder_delete.apply_async(args=[fileVal.folder_id])
        celerytaskinfo_ops.create_celery_taskinfo(task_id=result.task_id, status='PENDING', operation_type="Delete", operation_detail="Delete a filing export snapshot", user_email=userVal.email, organization_id=userVal.organization_id, folder_deadline=deadline, session=session)
        return jsonify({'status': "success"}), 200 
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
        session.close()

@app.route('/api/delfiling', methods=['DELETE'])
@jwt_required()
def delete_filing():
    session = Session()
    try:
        identity = get_jwt_identity()
        request_data = request.json
        folderid = request_data['folderID']
        if not folder_ops.folder_belongs_to_organization(folder_id=folderid, user_id=identity['id'], session=session):
            return jsonify({'status': 'error', 'message': 'You are accessing a filing not belong to your organization'}), 400

        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)
        folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        deadline = folderVal.deadline
        result = async_folder_delete.apply_async(args=[folderid])
        celerytaskinfo_ops.create_celery_taskinfo(task_id=result.task_id, status='PENDING', operation_type="Delete", operation_detail="Delete a filing", user_email=userVal.email, organization_id=userVal.organization_id, folder_deadline=deadline, session=session)
        return jsonify({'status': "success"}), 200 
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
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
        return jsonify({'status': "success", 'task_id': task.id}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401

@app.route('/api/get-raster-image/<string:towername>', methods=['GET'])
@jwt_required()
def get_raster_image(towername):
    session = Session()
    try:
        identity = get_jwt_identity()
        towerVal = get_tower_with_towername(tower_name=towername, user_id=identity['id'], session=session)
        if isinstance(towerVal, str):  # In case create_tower returned an error 
            logger.debug(towerVal)
            return jsonify({'status': 'error', 'message': towerVal}), 400
        
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
            return jsonify({'status': 'error', 'message': 'Raster data not found'}), 404
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
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
            return jsonify({'status': 'error', 'message': 'File not found'}), 404

        rasterData = towerVal.raster_data
        if rasterData:
            image_io = io.BytesIO(rasterData.transparent_image_data)
            image_io.seek(0)
            response = send_file(image_io, mimetype='image/png')
            return response
        else:
            return jsonify({'status': 'error', 'message': 'Raster data not found'}), 404
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
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
            return jsonify({'status': 'error', 'message': towerVal}), 400

        if not towerVal:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404

        rasterData = towerVal.raster_data
        if rasterData:
            bounds = {
                "north": rasterData.north_bound,
                "south": rasterData.south_bound,
                "east": rasterData.east_bound,
                "west": rasterData.west_bound,
            }
            return jsonify({'status': 'success', 'bounds': bounds}), 200 
        else:
            return jsonify({'status': 'error', 'message': 'Raster data not found'}), 404
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
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
            return jsonify({'status': 'error', 'messsage': 'Mapping not found'}), 404

        rasterData = towerVal.raster_data
        if rasterData and rasterData.loss_color_mapping:
            # Now we can just return the JSON directly
            return jsonify(rasterData.loss_color_mapping), 200
        else:
            return jsonify({'status': 'error', 'message': 'Loss to color mapping not found'}), 404

    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
        session.close()

@app.route('/api/upload-tower-csv', methods=['POST'])
@jwt_required()
def upload_csv():
    try:
        identity = get_jwt_identity()
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No selected file'}), 400

        if file and file.filename.endswith('.csv'):
            # Read the file content
            tower_data = read_tower_csv(file)
            if not isinstance(tower_data, str):
                return jsonify(tower_data), 200
            else:
                return jsonify({'status': 'error', 'message': tower_data}), 400
        else:
            return jsonify({'status': 'error', 'message': 'Invalid CSV file'}), 400
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    
@app.route('/api/downloadexport/<int:fileid>', methods=['GET'])
@jwt_required()
def download_export(fileid):
    fileid = int(fileid)
    session = Session()
    try:
        identity = get_jwt_identity()
        if not file_ops.file_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
            return jsonify({'status': 'error', 'message': 'You are accessing a file not belong to your organization'}), 400

        fileVal = file_ops.get_file_with_id(fileid=fileid, session=session)
        if not fileVal:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        downfile = io.BytesIO(fileVal.data)
        downfile.seek(0)
        return send_file(
                downfile,
                download_name=fileVal.name,
                as_attachment=True,
                mimetype="text/csv"
            )
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
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
        return jsonify({'status': "success", 'task_id': task.id, 'kml_filename': kml_filename}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    
@app.route('/api/preview-wireless-prediction-fabric-coverage', methods=['POST'])
@jwt_required()
def preview_wireless_prediction_fabric_coverage():
    try:
        identity = get_jwt_identity()
        data = request.json
        outfile_name = SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE.format(username=identity['username'], towername=data['towername'])
        task = preview_fabric_locaiton_coverage.apply_async(args=[data, identity['id'], outfile_name]) # store the AsyncResult instance
        kml_filename = outfile_name + '.kml'
        return jsonify({'status': "success", 'task_id': task.id, 'kml_filename': kml_filename}), 200 # return task id to the client
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401

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
            return jsonify({'status': 'error', 'message': fileVal}), 400

        if not fileVal:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404

        
        downfile = io.BytesIO(fileVal.data)
        downfile.seek(0)
        return send_file(
                downfile,
                download_name=fileVal.name,
                as_attachment=True,
                mimetype="text/kml"
            )
        
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
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
        return jsonify({'status': 'error', 'message': 'File not found'}), 404
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401

@app.route('/api/get-edit-geojson/<int:fileid>', methods=['GET'])
@jwt_required()
def get_edit_geojson(fileid):
    session = Session()
    try:
        identity = get_jwt_identity()
        fileid = int(fileid)
        if not editfile_ops.editfile_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
            return jsonify({'status': 'error', 'message': 'You are accessing a file not belong to your organization'}), 400

        editfile = editfile_ops.get_editfile_with_id(fileid=fileid, session=session)
       
        if editfile is None:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        
        # Decode the binary data to string assuming it's stored in UTF-8 encoded JSON format
        geojson_data = json.loads(editfile.data.decode('utf-8'))
        return jsonify(geojson_data), 200
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    finally:
        session.close()


@app.route('/api/get-edit-geojson-centroid/<int:fileid>', methods=['GET'])
@jwt_required()
def get_edit_geojson_centroid(fileid):
    session = Session()
    try:
        identity = get_jwt_identity()
        if not editfile_ops.editfile_belongs_to_organization(file_id=fileid, user_id=identity['id'], session=session):
            return jsonify({'status': 'error', 'message': 'You are accessing a file not belong to your organization'}), 400

        editfile = editfile_ops.get_editfile_with_id(fileid=fileid, session=session)

        if editfile is None:
            return jsonify({'status': 'error', 'message': 'File not found'}), 400

        # Decode the binary data to a JSON object
        geojson_object = json.loads(editfile.data.decode('utf-8'))
        
        # Calculate the centroid of the polygon
        polygon = shape(geojson_object['geometry'])
        centroid = polygon.centroid
        centroid_coords = {'latitude': centroid.y, 'longitude': centroid.x}
        # Include centroid coordinates in the response
        return jsonify(centroid_coords), 200
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to fetch file', 'details': str(e)}), 500
    finally:
        session.close()


@app.route('/api/update_profile', methods=['POST'])
@jwt_required()
def update_profile():
    try:
        identity = get_jwt_identity()
        data = request.get_json()
        provider_id = data.get('providerId')
        brand_name = str(data.get('brandName'))
        email = str(data.get('email'))
        org_name = str(data.get('organizationName'))
        
        session = Session()
        userVal = user_ops.get_user_with_id(userid=identity['id'], session=session)

        if email and email != userVal.email:
            userVal.email = email
            userVal.verified = False
            

        organization = userVal.organization
        if organization:
            if provider_id:
                organization.provider_id = provider_id
            if brand_name:
                organization.brand_name = brand_name
            if org_name:
                organization.name = org_name
        session.commit()
        return jsonify({'status': 'success', 'message': 'User profile updated successfully.'}), 200
    except NoAuthorizationError:
        return jsonify({'status': 'error', 'message': 'Please login to your account'}), 401
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()
    
# For docker
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=backend_port, debug=True)


# if __name__ == '__main__':
#     app.run(port=5000, debug=True)