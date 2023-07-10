import logging
import subprocess
import os
import json
import uuid
from controllers.celery_controller.celery_config import celery
from controllers.database_controller import fabric_ops, kml_ops
from database.models import File, user
from database.sessions import Session

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def process_data(self, file_names, file_data_list, username): 
    from controllers.database_controller import vt_ops
    print(file_names)
    try:
        fabricName = ""
        flag = False
        names = []
        geojson_array = []
        tasks = []  

        session = Session()
        userVal = session.query(user).filter(user.username == username).one()

        for file_name, file_data_str in zip(file_names, file_data_list):
            names.append(file_name)

            file_data = json.loads(file_data_str)

            downloadSpeed = file_data.get('downloadSpeed', '')
            uploadSpeed = file_data.get('uploadSpeed', '')
            techType = file_data.get('techType', '')
            networkType = file_data.get('networkType', '')

            if file_name.endswith('.csv'):
                fabricName = file_name

                task_id = str(uuid.uuid4())

                task = fabric_ops.write_to_db(file_name)
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

                task = kml_ops.add_network_data(fabricName, file_name, flag, downloadSpeed, uploadSpeed, techType, networkType)
                tasks.append(task)
                flag = True
                geojson_array.append(vt_ops.read_kml(file_name))

        vt_ops.create_tiles(geojson_array, userVal.id)
        
        # try:
        #     for name in names:
        #         file_to_delete = session.query(File).filter_by(file_name=name).first()  # get the file
        #         if file_to_delete:
        #             session.delete(file_to_delete)  # delete the file
        #             session.commit()  # commit the transaction
        # except Exception as e:
        #     session.rollback()  # rollback the transaction in case of error
        #     raise e  # propagate the error further
        session.close()
        return {'Status': "Ok"}
    
    except Exception as e:
        session.close()
        self.update_state(state='FAILURE')
        raise e

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_tippecanoe(self, command, user_id):
    from controllers.database_controller import vt_ops
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
        print("Tippecanoe stderr:", result.stderr.decode())

    vt_ops.add_values_to_VT("./output.mbtiles", user_id)
    return result.returncode 

