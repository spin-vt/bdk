import logging
import subprocess
import os
import json
import uuid
from flask import jsonify
from .celery_config import celery
from ..database_controller import vt_ops, fabric_ops, kml_ops

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def process_input_file(self, file_name, task_id):
    result = fabric_ops.write_to_db(file_name)
    self.update_state(state='PROCESSED')
    return result

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def process_data(files, file_data_list): 
    fabricName = ""
    flag = False
    names = []
    geojson_array = []
    tasks = []  

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
            tasks.append(task)

        elif file_name.endswith('.kml'):
            if not fabric_ops.check_num_records_greater_zero():
                return False
            
            file.save(file_name)
            task_id = str(uuid.uuid4())  

            if networkType == "Wired": 
                networkType = 0
            else: 
                networkType = 1

            task = provide_kml_locations.apply_async(args=[fabricName, file_name, downloadSpeed, uploadSpeed, techType, flag, networkType])
            tasks.append(task)
            flag = True
            kmlfile_path = os.path.join(os.getcwd(), file_name)
            geojson_array.append(vt_ops.read_kml(kmlfile_path))
        
    vt_ops.create_tiles(geojson_array)
    for name in names:
        os.remove(name)

    return jsonify({'Status': "Ok"}), 200

@celery.task(bind=True)
def provide_kml_locations(self, fabric, network, downloadSpeed, uploadSpeed, techType, flag, networkType):
    try:
        result = kml_ops.add_network_data(fabric, network, flag, downloadSpeed, uploadSpeed, techType, networkType)
        self.update_state(state='PROCESSED')
        return result
    except Exception as e:
        logging.exception("Error processing KML file: %s", str(e))
        self.update_state(state='FAILED')
        raise

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_tippecanoe(self, command):
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
        print("Tippecanoe stderr:", result.stderr.decode())
    
    return result.returncode  # return the return code of the subprocess command

