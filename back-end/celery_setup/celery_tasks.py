from .celery_config import celery
from database_op import fabric_ops
from database_op import kml_ops
import logging
import subprocess

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def process_input_file(self, file_name, task_id):
    result = fabric_ops.write_to_db(file_name)
    self.update_state(state='PROCESSED')
    return result

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