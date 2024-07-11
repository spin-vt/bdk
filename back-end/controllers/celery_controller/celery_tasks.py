import logging, subprocess, os, json, uuid, cProfile
from controllers.celery_controller.celery_config import celery
from controllers.database_controller import user_ops, fabric_ops, kml_ops, mbtiles_ops, file_ops, folder_ops, vt_ops, editfile_ops, file_editfile_link_ops
from database.models import file, kml_data, editfile
from database.sessions import Session, ScopedSession
from controllers.database_controller.tower_ops import get_tower_with_towername
from controllers.database_controller.rasterdata_ops import create_rasterdata
from controllers.signalserver_controller.rasterprocessing import read_rasterkmz, filter_image_by_loss, load_loss_to_color_mapping, generate_transparent_image
from flask import jsonify
from datetime import datetime
from utils.namingschemes import DATETIME_FORMAT, EXPORT_CSV_NAME_TEMPLATE
from utils.logger_config import logger
from utils.wireless_form2args import wireless_raster_file_format, wireless_vector_file_format
from controllers.signalserver_controller.raster2vector import smooth_edges

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def process_data(self, file_names, file_data_list, userid, folderid): 
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

            task = kml_ops.add_network_data(folderid, existing_file.id, downloadSpeed, uploadSpeed, techType, networkType, userid, latency, category, session)
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

            task = kml_ops.add_network_data(folderid, existing_file.id, downloadSpeed, uploadSpeed, techType, networkType, userid, latency, category, session)
            tasks.append(task)
        
        # This is a temporary solution, we should try optimize to use tile-join
        all_kmls = session.query(file).filter(file.folder_id == folderid, file.name.endswith('kml')).all()
        for kml_f in all_kmls:
            geojson_array.append(vt_ops.read_kml(kml_f.id, session))
        
        all_geojsons = session.query(file).filter(file.folder_id == folderid, file.name.endswith('geojson')).all()
        for geojson_f in all_geojsons:
            geojson_array.append(vt_ops.read_geojson(geojson_f.id, session))
        
        mbtiles_ops.delete_mbtiles(folderid, session)
        session.commit()
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
    result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

    if result.stderr:
        print("Tippecanoe stderr:", result.stderr.decode())

    vt_ops.add_values_to_VT(mbtilepath, folderid)
    return result.returncode 

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_tippecanoe_tiles_join(self, command1, command2, folderid, mbtilepaths):
    
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
def deleteFiles(self, fileid, userid):
    try:
        session = Session()
        file_to_del = file_ops.get_file_with_id(fileid)
        folderid = file_to_del.folder_id
        file_ops.delete_file(file_to_del.id, session)
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
        return {'message': 'mbtiles successfully deleted'}  # Returning a dictionary
    except Exception as e:
        session.rollback()  # Rollback the session in case of error
        return jsonify({'Status': "Failed, server failed", 'error': str(e)}), 500
    finally:
        session.close()

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def toggle_tiles(self, markers, userid, folderid, polygonfeatures):
    message = ''
    status_code = 0
    session = Session()
    try:
        file_editfile_link_set = set()
        user_folder = folder_ops.get_folder_with_id(userid=userid, folderid=folderid, session=session)
        if user_folder:
            # Process each polygon feature
            for index, feature in enumerate(polygonfeatures):
                filenames = '-'.join(set(
                    filename for marker in markers[index] for filename in marker['editedFile']
                ))
                formatted_datetime = datetime.now().strftime(DATETIME_FORMAT)
                editfile_name = f"edit_on_{filenames}_at_{formatted_datetime}"
                
                feature_binary = json.dumps(feature).encode('utf-8')
                new_editfile = editfile_ops.create_editfile(filename=editfile_name, content=feature_binary, folderid=folderid, session=session)
                session.commit()

                # Link this editfile with relevant files
                for marker in markers[index]:
                    # Query kml_data_entries based on location_id and filenames from editedFile
                    for filename in marker['editedFile']:
                        kml_data_entries = session.query(kml_data).join(file).filter(kml_data.location_id == marker['id'], file.folder_id == user_folder.id, file.name == filename).all()
                        for entry in kml_data_entries:
                            file_instance = session.query(file).filter_by(id=entry.file_id).first()
                            if file_instance:
                                if (file_instance.id, new_editfile.id) not in file_editfile_link_set:
                                    file_editfile_link_ops.link_file_and_editfile(file_instance.id, new_editfile.id, session)
                                    file_editfile_link_set.add((file_instance.id, new_editfile.id))
                            session.delete(entry)
            session.commit()

        else:
            raise Exception('No folder for the user')
        
        geojson_data = []
        all_kmls = file_ops.get_files_with_postfix(user_folder.id, '.kml', session)
        for kml_f in all_kmls:
            geojson_data.append(vt_ops.read_kml(kml_f.id, session))
        
        all_geojsons = file_ops.get_files_with_postfix(folderid=user_folder.id, postfix='.geojson', session=session)
        for geojson_f in all_geojsons:
            geojson_data.append(vt_ops.read_geojson(geojson_f.id, session))

        mbtiles_ops.delete_mbtiles(user_folder.id, session)
        vt_ops.create_tiles(geojson_data, userid, user_folder.id, session)
        if user_folder.type == 'export':
            existing_csvs = file_ops.get_files_by_type(folderid=user_folder.id, filetype='export', session=session)
            for csv_file in existing_csvs:
                session.delete(csv_file)

            userVal = user_ops.get_user_with_id(userid=userid, session=session)
            # Generate and save a new CSV
            all_file_ids = [file.id for file in file_ops.get_files_with_postfix(user_folder.id, '.kml', session) + file_ops.get_files_with_postfix(user_folder.id, '.geojson', session)]

            results = session.query(kml_data).filter(kml_data.file_id.in_(all_file_ids)).all()
            availability_csv = kml_ops.generate_csv_data(results, userVal.provider_id, userVal.brand_name)

            csv_name = f"availability-{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.csv"
            csv_data_str = availability_csv.to_csv(index=False, encoding='utf-8')
            new_csv_file = file_ops.create_file(filename=csv_name, content=csv_data_str.encode('utf-8'), folderid=user_folder.id, filetype='export', session=session)
            session.add(new_csv_file)

        

        message = 'Markers toggled successfully'
        status_code = 200
        
        
        

    except Exception as e:
        session.rollback()  # rollback transaction on error
        message = str(e)  # send the error message to client
        status_code = 500

    finally:
        session.commit()
        session.close()

    return (message, status_code)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def async_folder_copy_for_export(self, userid, folderid, serialized_csv):
    session = Session()
    userVal = user_ops.get_user_with_id(userid)
    current_datetime = datetime.now().strftime(DATETIME_FORMAT)
    newfolder_name = f"export-{current_datetime}"


    csv_name = EXPORT_CSV_NAME_TEMPLATE.format(brand_name=userVal.brand_name, current_datetime=current_datetime)

    original_folder = folder_ops.get_folder_with_id(userid=userid, folderid=folderid, session=session)
    new_folder = original_folder.copy(name=newfolder_name,type='export', session=session)
    csv_file = file_ops.create_file(filename=csv_name, content=serialized_csv.encode('utf-8'), folderid=new_folder.id, filetype='export', session=session)
    session.add(csv_file)
    session.commit()
    session.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_signalserver(self, command, outfile_name, tower_id, data):
    session = Session()
    try:
        result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

        if result.stderr:
            print("SignalServer stderr:", result.stderr.decode())
        
        bbox = read_rasterkmz(outfile_name + '.kmz')
        filter_image_by_loss(outfile_name + '.png', int(data['floorLossRate']), outfile_name + '.lcf', outfile_name + '.png')
        with open(outfile_name + '.png', 'rb') as img_file:
            img_data = img_file.read()

        transparent_image_name = outfile_name + '-transparent' '.png'
        logger.debug("Generating trans image")
        generate_transparent_image(outfile_name + '.png', transparent_image_name)
        with open(transparent_image_name, 'rb') as transparent_img_file:
            transparent_img_data = transparent_img_file.read()
        logger.debug("Generated trans image")
        loss_color_mapping = load_loss_to_color_mapping(outfile_name + '.lcf')
        # Assume we have some way to get raster data after running the command
        raster_data_val = create_rasterdata(tower_id=tower_id, 
                                            image_data=img_data,
                                            transparent_image_data=transparent_img_data,
                                            loss_color_mapping=loss_color_mapping,
                                            nbound=bbox['nbound'],
                                            sbound=bbox['sbound'],
                                            ebound=bbox['ebound'],
                                            wbound=bbox['wbound'],
                                            session=session)
        if isinstance(raster_data_val, str):  # In case create_rasterdata returned an error message
            return {'error': raster_data_val}

        for f_extension in wireless_raster_file_format:
            os.remove(outfile_name + f_extension)
        os.remove(transparent_image_name)
        return result.returncode 
    except Exception as e:
        return {'error': str(e)}
    finally:
        session.commit()
        session.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def preview_fabric_locaiton_coverage(self, data, userid, outfile_name):
    session = Session()
    try:
        towerVal = get_tower_with_towername(tower_name=data['towername'], user_id=userid, session=session)
        if isinstance(towerVal, str):  # In case create_tower returned an error 
            logger.debug(towerVal)
            return {'error': towerVal}
        if not towerVal:
            logger.debug('tower not found under towername')
            return {'error': 'File not found'}

        rasterData = towerVal.raster_data

        # Specify the path for the .png file
        image_file_path = f"{outfile_name}.png"

        # Write the binary image data to a .png file
        with open(image_file_path, 'wb') as image_file:
            image_file.write(rasterData.image_data)

        smooth_edges(image_file_path, image_file_path, 2)
        gdal_translate_cmd = f"gdal_translate -a_ullr {rasterData.west_bound} {rasterData.north_bound} {rasterData.east_bound} {rasterData.south_bound} -a_srs EPSG:4326 {image_file_path} {outfile_name}.tif"
        logger.debug("Executing:", gdal_translate_cmd)
        subprocess.run(gdal_translate_cmd, shell=True)

        # Execute gdal_polygonize.py
        gdal_polygonize_cmd = f"gdal_polygonize.py {outfile_name}.tif -f \"KML\" {outfile_name}.kml"
        logger.debug("Executing:", gdal_polygonize_cmd)
        subprocess.run(gdal_polygonize_cmd, shell=True)

        folderVal = folder_ops.get_upload_folder(userid, session=session)
        if folderVal is None:
             return {'error': 'Folder not found'}

        logger.debug("Computing covered points")
        covered_points = kml_ops.preview_wireless_locations(folderVal.id, outfile_name + '.kml')
        for f_extension in wireless_vector_file_format:
            os.remove(outfile_name + f_extension)
        # Convert the GeoDataFrame to a JSON-friendly format, such as GeoJSON
        covered_points_geojson = covered_points.to_json()
        geojson_filename = outfile_name + '.geojson'
        with open(geojson_filename, 'w') as f:
            json.dump(covered_points_geojson, f)
        # Return a native Python dictionary
        return {"Status": "Ok", "geojson_filename": geojson_filename}
    except Exception as e:
        return {'error': str(e)}
    finally:
        session.close()

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def raster2vector(self, data, userid, outfile_name):
    session = Session()
    try:
        towerVal = get_tower_with_towername(tower_name=data['towername'], user_id=userid, session=session)
        if isinstance(towerVal, str):  # In case create_tower returned an error 
            logger.debug(towerVal)
            return {'error': towerVal}
        if not towerVal:
            logger.debug('tower not found under towername')
            return {'error': 'File not found'}

        rasterData = towerVal.raster_data

        # Specify the path for the .png file
        image_file_path = f"{outfile_name}.png"

        # Write the binary image data to a .png file
        with open(image_file_path, 'wb') as image_file:
            image_file.write(rasterData.image_data)

        smooth_edges(image_file_path, image_file_path, 2)
        gdal_translate_cmd = f"gdal_translate -a_ullr {rasterData.west_bound} {rasterData.north_bound} {rasterData.east_bound} {rasterData.south_bound} -a_srs EPSG:4326 {image_file_path} {outfile_name}.tif"
        logger.debug("Executing:", gdal_translate_cmd)
        subprocess.run(gdal_translate_cmd, shell=True)

        # Execute gdal_polygonize.py
        gdal_polygonize_cmd = f"gdal_polygonize.py {outfile_name}.tif -f \"KML\" {outfile_name}.kml"
        logger.debug("Executing:", gdal_polygonize_cmd)
        subprocess.run(gdal_polygonize_cmd, shell=True)

        userVal = user_ops.get_user_with_id(userid, session=session)
        folderVal = folder_ops.get_upload_folder(userVal.id, session=session)
        if folderVal is None:
            num_folders = folder_ops.get_number_of_folders_for_user(userVal.id, session=session)
            folder_name = f"{userVal.username}-{num_folders + 1}"
            deadline = "September 2024"
            folderVal = folder_ops.create_folder(folder_name, userVal.id, deadline, 'upload', session=session)
            session.commit()

        vector_file_name = outfile_name + '.kml'
        with open(vector_file_name, 'rb') as vector_file:
            kml_binarydata = vector_file.read()
            fileVal = file_ops.create_file(vector_file_name, kml_binarydata, folderVal.id, 'wireless', session=session)
            fileVal.computed = True
            session.commit()
            downloadSpeed = data['downloadSpeed']
            uploadSpeed = data['uploadSpeed']
            techType = data['techType']
            latency = data['latency']
            category = data['categoryCode']
        
            kml_ops.compute_wireless_locations(fileVal.folder_id, fileVal.id, downloadSpeed, uploadSpeed, techType, userid, latency, category, session)
            geojson_array = []
            all_kmls = file_ops.get_files_with_postfix(fileVal.folder_id, '.kml', session)
            for kml_f in all_kmls:
                geojson_array.append(vt_ops.read_kml(kml_f.id, session))
            all_geojsons = file_ops.get_files_with_postfix(fileVal.folder_id, '.geojson', session)
            for geojson_f in all_geojsons:
                geojson_array.append(vt_ops.read_geojson(geojson_f.id, session))
            
            logger.info("Creating Vector Tiles")
            mbtiles_ops.delete_mbtiles(fileVal.folder_id, session)
            session.commit()
            vt_ops.create_tiles(geojson_array, userid, fileVal.folder_id, session)

        for f_extension in wireless_vector_file_format:
            os.remove(outfile_name + f_extension)
        return {'Status': "Ok"}
    except Exception as e:
        return {'error': str(e)}
    finally:
        session.close()