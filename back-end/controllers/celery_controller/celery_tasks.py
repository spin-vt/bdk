import logging, subprocess, os, json, uuid, cProfile
from controllers.celery_controller.celery_config import celery
from controllers.database_controller import fabric_ops, kml_ops, mbtiles_ops, file_ops, folder_ops, vt_ops
from database.models import file, user, folder
from database.sessions import Session
from flask import jsonify

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def process_data(self, file_names, file_data_list, userid, folderid): 
    from controllers.database_controller import vt_ops
    print(file_names)
    try:
        geojson_array = []
        tasks = []  
        session = Session()

        csv_file_data = []
        kml_file_data = []
        geojson_file_data = []
        # Separate file data into csv and kml
        for file_name, file_data_str in zip(file_names, file_data_list):
            if file_name.endswith('.csv'):
                csv_file_data.append((file_name, file_data_str))
            elif (file_name.endswith('.kml')):
                kml_file_data.append((file_name, file_data_str))
            elif file_name.endswith('.geojson'):
                geojson_file_data.append((file_name, file_data_str))

        for file_name, file_data_str in csv_file_data:
            # Check if file name already exists in the database for this user
            existing_file = session.query(file).filter(file.name==file_name, file.folder_id==folderid).first()
            print(existing_file)
            # If file name exists, skip to the next iteration
            if existing_file and existing_file.computed:
                print("skip")
                continue
            
            # names.append(file_name)
            existing_file.computed = True 
            session.commit() #commit the change 

            file_data = json.loads(file_data_str)
            
            #i don't think we need to do this here, fix later 
            downloadSpeed = file_data.get('downloadSpeed', '')
            uploadSpeed = file_data.get('uploadSpeed', '')
            techType = file_data.get('techType', '')
            networkType = file_data.get('networkType', '')
            latency = file_data.get('latency', '')
            categoryCode = file_data.get('categoryCode', '')
            
            fabricid = existing_file.id

            task_id = str(uuid.uuid4())
            task = fabric_ops.write_to_db(fabricid)
            tasks.append(task)

        for file_name, file_data_str in kml_file_data:

            existing_file = session.query(file).filter(file.name==file_name, file.folder_id==folderid).first()
            print(existing_file)
            # If file name exists, skip to the next iteration
            if existing_file and existing_file.computed:
                print("skip")
                continue
            
            # names.append(file_name)
            existing_file.computed = True 
            session.commit() #commit the change 

            file_data = json.loads(file_data_str)

            downloadSpeed = file_data.get('downloadSpeed', '')
            uploadSpeed = file_data.get('uploadSpeed', '')
            techType = file_data.get('techType', '')
            networkType = file_data.get('networkType', '')
            latency = file_data.get('latency', '')
            category = file_data.get('categoryCode', '')
            
            task_id = str(uuid.uuid4())

            if networkType == "Wired": 
                networkType = 0
            else: 
                networkType = 1

            task = kml_ops.add_network_data(folderid, existing_file.id, downloadSpeed, uploadSpeed, techType, networkType, userid, latency, category)
            tasks.append(task)

        for file_name, file_data_str in geojson_file_data:

            existing_file = session.query(file).filter(file.name==file_name, file.folder_id==folderid).first()
            print(existing_file)
            # If file name exists, skip to the next iteration
            if existing_file and existing_file.computed:
                print("skip")
                continue
            
            # names.append(file_name)
            existing_file.computed = True 
            session.commit() #commit the change 

            file_data = json.loads(file_data_str)

            downloadSpeed = file_data.get('downloadSpeed', '')
            uploadSpeed = file_data.get('uploadSpeed', '')
            techType = file_data.get('techType', '')
            networkType = file_data.get('networkType', '')
            latency = file_data.get('latency', '')
            category = file_data.get('categoryCode', '')

            if networkType == "Wired": 
                networkType = 0
            else: 
                networkType = 1

            task = kml_ops.add_network_data(folderid, existing_file.id, downloadSpeed, uploadSpeed, techType, networkType, userid, latency, category)
            tasks.append(task)
        
        # This is a temporary solution, we should try optimize to use tile-join
        all_kmls = session.query(file).filter(file.folder_id == folderid, file.name.endswith('kml')).all()
        for kml_f in all_kmls:
            geojson_array.append(vt_ops.read_kml(kml_f.id, session))
        
        all_geojsons = session.query(file).filter(file.folder_id == folderid, file.name.endswith('geojson')).all()
        for geojson_f in all_geojsons:
            geojson_array.append(vt_ops.read_geojson(geojson_f.id, session))
        
        mbtiles_ops.delete_mbtiles(folderid, session)
        print("finished kml processing, now creating tiles")
        
        vt_ops.create_tiles(geojson_array, userid, folderid, session)
        
        
        session.close()
        return {'Status': "Ok"}
    
    except Exception as e:
        session.close()
        self.update_state(state='FAILURE')
        raise e

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_tippecanoe(self, command, folderid, mbtilepath):
    from controllers.database_controller import vt_ops
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
        print("Tippecanoe stderr:", result.stderr.decode())

    vt_ops.add_values_to_VT(mbtilepath, folderid)
    return result.returncode 

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_tippecanoe_tiles_join(self, command1, command2, folderid, mbtilepaths):
    from controllers.database_controller import vt_ops
    
    # run first command
    result1 = subprocess.run(command1, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result1.returncode != 0:
        raise Exception(f"Command '{command1}' failed with return code {result1.returncode}")

    # run second command
    result2 = subprocess.run(command2, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result2.returncode != 0:
        raise Exception(f"Command '{command2}' failed with return code {result2.returncode}")

    # print outputs if any
    if result1.stdout:
        print("Tippecanoe stdout:", result1.stdout.decode())
    if result1.stderr:
        print("Tippecanoe stderr:", result1.stderr.decode())
    if result2.stdout:
        print("Tile-join stdout:", result2.stdout.decode())
    if result2.stderr:
        print("Tile-join stderr:", result2.stderr.decode())

    # handle the result
    vt_ops.add_values_to_VT(mbtilepaths[0], folderid)
    for i in range(1, len(mbtilepaths)):
        os.remove(mbtilepaths[i])
        
    return result2.returncode

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def deleteFiles(self, fileid, userid, session):
    try:
        file_to_del = file_ops.get_file_with_id(fileid)
        folderid = file_to_del.folder_id
        file_ops.delete_file(fileid, session)
        mbtiles_ops.delete_mbtiles(folderid, session)
        session.commit()
        
        geojson_array = []
        all_kmls = file_ops.get_files_with_postfix(folderid, '.kml', session)
        for kml_f in all_kmls:
            geojson_array.append(vt_ops.read_kml(kml_f.id, session))

        all_geojsons = file_ops.get_files_with_postfix(folderid, '.geojson', session)
        for geojson_f in all_geojsons:
            geojson_array.append(vt_ops.read_geojson(geojson_f.id, session))
        vt_ops.create_tiles(geojson_array, userid, folderid, session)
        return jsonify({'message': 'mbtiles successfully deleted'}), 200
    except Exception as e:
        session.rollback()  # Rollback the session in case of error
        return jsonify({'Status': "Failed, server failed", 'error': str(e)}), 500
    finally:
        session.close()