import logging, subprocess, os, json, uuid, cProfile
from controllers.celery_controller.celery_config import celery
from controllers.database_controller import fabric_ops, kml_ops
from database.models import File, user
from database.sessions import Session

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def process_data(self, file_names, file_data_list, username): 
    from controllers.database_controller import vt_ops
    print(file_names)
    try:
        # Start profiling
        profiler = cProfile.Profile()
        profiler.enable()

        fabricName = ""
        names = []
        geojson_array = []
        tasks = []  

        session = Session()
        userVal = session.query(user).filter(user.username == username).one()

        for file_name, file_data_str in zip(file_names, file_data_list):
            # # Check if file name already exists in the database for this user
            # existing_file = session.query(File).filter(File.file_name == file_name, File.user_id == userVal.id).first()

            # # If file name exists, skip to the next iteration
            # if existing_file:
            #     continue
            
            names.append(file_name)

            file_data = json.loads(file_data_str)

            downloadSpeed = file_data.get('downloadSpeed', '')
            uploadSpeed = file_data.get('uploadSpeed', '')
            techType = file_data.get('techType', '')
            networkType = file_data.get('networkType', '')

            if file_name.endswith('.csv'):
                fabricName = file_name

                task_id = str(uuid.uuid4())

                task = fabric_ops.write_to_db(file_name, userVal.id)
                tasks.append(task)

            elif file_name.endswith('.kml'):
                print(file_name)
                if not fabric_ops.check_num_records_greater_zero():
                    raise ValueError('No records found in fabric operations')
                
                task_id = str(uuid.uuid4())  

                if networkType == "Wired": 
                    networkType = 0
                else: 
                    networkType = 1

                task = kml_ops.add_network_data(fabricName, file_name, downloadSpeed, uploadSpeed, techType, networkType, userVal.id)
                tasks.append(task)
                geojson_array.append(vt_ops.read_kml(file_name, userVal.id))
        
        print("finished kml processing, now creating tiles")
        vt_ops.create_tiles(geojson_array, userVal.id)
        
        # try:
        #     for name in names:
        #         file_to_delete = session.query(File).filter_by(file_name=name, user_id=userVal.id).first()  # get the file
        #         if file_to_delete:
        #             session.delete(file_to_delete)  # delete the file
        #             session.commit()  # commit the transaction
        # except Exception as e:
        #     session.rollback()  # rollback the transaction in case of error
        #     raise e  # propagate the error further
        
        session.close()

        # Stop profiling
        profiler.disable()
        filepath = f'profiler_output_{os.getpid()}_{self.request.id}.txt'
        profiler.dump_stats(filepath)


        return {'Status': "Ok"}
    
    except Exception as e:
        session.close()
        self.update_state(state='FAILURE')
        raise e

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_tippecanoe(self, command, user_id, mbtilepath):
    from controllers.database_controller import vt_ops
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
        print("Tippecanoe stderr:", result.stderr.decode())

    vt_ops.add_values_to_VT(mbtilepath, user_id)
    return result.returncode 

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_tippecanoe_tiles_join(self, command1, command2, user_id, mbtilepaths):
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
    vt_ops.add_values_to_VT(mbtilepaths[0], user_id)
    for i in range(1, len(mbtilepaths)):
        os.remove(mbtilepaths[i])
        
    return result2.returncode


