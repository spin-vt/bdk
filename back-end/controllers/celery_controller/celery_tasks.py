import base64
import json
import os
import subprocess
import time
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from controllers.celery_controller.celery_config import celery
from controllers.database_controller import (
    editfile_ops,
    fabric_ops,
    file_editfile_link_ops,
    file_ops,
    folder_ops,
    kml_ops,
    mbtiles_ops,
    organization_ops,
    user_ops,
    vt_ops,
)
from controllers.database_controller.rasterdata_ops import create_rasterdata
from controllers.database_controller.tower_ops import get_tower_with_towername
from controllers.signalserver_controller.raster2vector import smooth_edges
from controllers.signalserver_controller.rasterprocessing import (
    filter_image_by_loss,
    generate_transparent_image,
    load_loss_to_color_mapping,
    read_rasterkmz,
)
from database.models import file, kml_data, service_plan
from database.sessions import Session
from utils.config import Config
from utils.logger_config import logger
from utils.namingschemes import DATETIME_FORMAT
from utils.wireless_form2args import wireless_raster_file_format, wireless_vector_file_format


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def add_files_to_folder(self, folderid, file_contents):
    logger.debug(f"folder id in add files to folder is {folderid}")
    try:
        session = Session()
        batch_names = set()
        for filename, content, metadata_json in file_contents:
            metadata = json.loads(metadata_json)
            content_bytes = base64.b64decode(content)
            if filename.endswith(".csv"):
                fileVal = file_ops.create_file(
                    filename=filename,
                    content=content_bytes,
                    folderid=folderid,
                    filetype="fabric",
                    session=session,
                )
            elif filename.endswith(".kml") or filename.endswith(".geojson"):
                # Filenames key tiles/edits/layers — never store a duplicate.
                filename = file_ops.unique_filename(folderid, filename, session, taken=batch_names)
                batch_names.add(filename)
                downloadSpeed = metadata.get("downloadSpeed", "")
                uploadSpeed = metadata.get("uploadSpeed", "")
                techType = metadata.get("techType", "")
                networkType = metadata.get("networkType", "").strip().lower()
                latency = metadata.get("latency", "")
                category = metadata.get("categoryCode", "")

                fileVal = file_ops.create_file(
                    filename=filename,
                    content=content_bytes,
                    folderid=folderid,
                    filetype=networkType,
                    maxDownloadSpeed=downloadSpeed,
                    maxUploadSpeed=uploadSpeed,
                    techType=techType,
                    latency=latency,
                    category=category,
                    session=session,
                )
                # The tech's default plan governs an unassigned file: inherit
                # its values instead of the upload's placeholder speeds, so
                # the first compute stamps the right numbers into kml_data.
                from services import plan_service

                try:
                    tech_int = int(techType)
                except (TypeError, ValueError):
                    tech_int = None
                if tech_int is not None:
                    default = plan_service.default_plan_for(folderid, tech_int, session)
                    if default is not None:
                        fileVal.maxDownloadSpeed = default.max_download
                        fileVal.maxUploadSpeed = default.max_upload
                        fileVal.latency = 1 if default.low_latency else 0
                        fileVal.category = default.category

        session.commit()
        return folderid
    except Exception as e:
        session.rollback()  # Rollback any changes if there's an exception
        raise e
    finally:
        session.close()  # Ensure session is closed even if there's an exception


"""
    There are four types of operation that makes use of this methods
    1. Upload more files to an existing filing
    2. Create new filing from scratch
    3. Create a new filing by importing from previous filings
    4. Regenrate map for file deletion or file info change
"""


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def process_data(self, folderid, operation):
    try:
        logger.debug(f"folder id in process data is {folderid}")
        logger.debug(f"operation is {operation}")
        session = Session()

        recompute_coverage = operation in [3, 4]

        coverage_files = file_ops.get_files_with_postfix(
            folderid, ".kml", session
        ) + file_ops.get_files_with_postfix(folderid, ".geojson", session)
        logger.debug(coverage_files)
        # Ingest fabric CSVs routed by role (active/non_bsl -> fabric_data,
        # supplemental -> the address index); import (op 3) re-ingests.
        fabric_ops.write_folder_fabric(folderid, session, reimport=(operation == 3))

        # Delete all kml_data associated with the coverage_files if operation == 4
        if operation == 4:
            logger.info(f"Deleting all KML data for folder {folderid}")
            for file in coverage_files:
                # Delete all kml_data associated with each file
                session.query(kml_data).filter(kml_data.file_id == file.id).delete()
            session.commit()  # Commit the deletions

        # A recompute derives kml rows from the files' legacy columns — make
        # those match the governing plans first (no-op for plan-less legacy
        # filings, so the golden replays are untouched). This is also the
        # self-heal for filings whose plans predate default write-through.
        if recompute_coverage:
            from services import plan_service

            plan_service.restamp_folder(folderid, session)
            session.commit()

        # No fabric yet (a fresh filing, or a carry-forward — the import copy
        # deliberately drops the old fabric): nothing to match coverage
        # against, so leave the files uncomputed instead of crashing. The
        # fabric intake dispatches the recompute when the new fabric lands.
        has_fabric = bool(file_ops.get_files_by_type(folderid, "fabric", session))

        # The fabric is the same for every coverage file — parse it once for
        # the whole run, not once per file (it's an ~80 MB CSV).
        fabric_gdf = kml_ops.load_fabric_gdf(folderid) if has_fabric else None

        for file in coverage_files:
            if not has_fabric:
                file.computed = False
                continue
            if file.computed:
                if not recompute_coverage:
                    continue

            downloadSpeed = file.maxDownloadSpeed
            uploadSpeed = file.maxUploadSpeed
            techType = file.techType
            networkType = file.type
            latency = file.latency
            category = file.category

            if networkType.strip().lower() == "wired":
                networkType = 0
            else:
                networkType = 1

            task = kml_ops.add_network_data(
                folderid,
                file.id,
                downloadSpeed,
                uploadSpeed,
                techType,
                networkType,
                latency,
                category,
                session,
                fabric=fabric_gdf,
            )

            file.computed = True

        session.commit()
        logger.info("finished coverage points computation, now creating vector tiles")
        session.close()

        # Tile building goes through the same per-folder single-flight path as
        # edit retiles, so upload/delete/regenerate rebuilds coalesce with (and
        # never race) edit rebuilds. Returns once the tiles cover this change.
        _mark_tiles_dirty(folderid)
        _coalesced_tile_rebuild(folderid, self.request.id)

    except Exception as e:
        session.close()
        self.update_state(state="FAILURE")
        raise e


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def import_fabric_data(self, folderid):
    """Ingest a folder's not-yet-computed fabric CSVs without touching
    coverage — the dispatch target for deliveries with only non_bsl /
    supplemental parts (those roles never feed computation, so no recompute
    and no retile)."""
    session = Session()
    try:
        fabric_ops.write_folder_fabric(folderid, session)
        session.commit()
        return folderid
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def async_delete_files(self, file_ids, editfile_ids):
    session = Session()
    try:
        for fileid in file_ids:
            file_ops.delete_file(fileid, session)

        for editfileid in editfile_ids:
            editfile_ops.delete_editfile(editfileid, session)

        session.commit()

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error occurred during file deletion: {str(e)}")
        raise
    finally:
        session.close()


# --- edit flow: fast DB apply + debounced tile regeneration -------------------
# An edit used to be one task (editfile + kml_data changes + a full retile).
# It is now dispatched as a chain (see services/edit_service.py):
#   apply_edit_changes  — seconds; after it commits, kml_data (and therefore
#                         exports) is correct and only the tiles are stale;
#   regenerate_tiles    — the slow tippecanoe rebuild, single-flight per folder
#                         with a dirty flag so rapid edits coalesce.

TILES_DIRTY_KEY = "bdk:tiles-dirty:{folderid}"
TILES_DIRTY_BBOX_KEY = "bdk:tiles-dirty-bbox:{folderid}"
TILES_SETTLE_KEY = "bdk:tiles-settle:{folderid}"
TILES_LOCK_KEY = "bdk:tiles-lock:{folderid}"
TILES_LOCK_TTL = 3600  # safety expiry on the lock; no rebuild should take this long
TILES_LOCK_WAIT = 1800  # max time a regenerate waits behind another rebuild
TILES_SETTLE_QUIET = 600  # settle the stale z0-8 only after edits go quiet this long


def _tiles_redis():
    """Redis client for the tile dirty/lock flags, or None when redis isn't
    reachable (e.g. the tests' in-memory broker). Callers must treat None as
    'no debounce' and always rebuild — correct, just less efficient."""
    try:
        import redis

        client = redis.Redis.from_url(Config.CELERY_BROKER_URL, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None


def _mark_tiles_dirty(folderid, bbox=None):
    """Record that the folder's tiles no longer match DB truth. With a bbox
    ([minx, miny, maxx, maxy] lon/lat) the dirt is scoped to that region and
    the rebuild may splice just its tiles; without one the whole tileset is
    stale. A bbox never downgrades already-recorded whole-tileset dirt."""
    r = _tiles_redis()
    if r is None:
        return
    dirty_key = TILES_DIRTY_KEY.format(folderid=folderid)
    if bbox is None:
        r.set(dirty_key, "full")
    else:
        r.rpush(TILES_DIRTY_BBOX_KEY.format(folderid=folderid), json.dumps(bbox))
        r.set(dirty_key, "bbox", nx=True)


def _pop_tiles_dirt(r, folderid):
    """Atomically consume the folder's recorded dirt -> (flag, [bbox, ...]).
    Atomic so a mark racing this pop is either fully consumed now or fully
    left for the next rebuild — never half-eaten."""
    pipe = r.pipeline(transaction=True)
    pipe.lrange(TILES_DIRTY_BBOX_KEY.format(folderid=folderid), 0, -1)
    pipe.delete(TILES_DIRTY_BBOX_KEY.format(folderid=folderid))
    pipe.get(TILES_DIRTY_KEY.format(folderid=folderid))
    pipe.delete(TILES_DIRTY_KEY.format(folderid=folderid))
    raw_bboxes, _, dirty, _ = pipe.execute()
    return dirty, [json.loads(b) for b in raw_bboxes]


def _features_bbox(features):
    """[minx, miny, maxx, maxy] over every coordinate of the given GeoJSON
    features, or None when there are no coordinates."""
    coords = []

    def walk(node):
        if isinstance(node, (list, tuple)):
            if (
                len(node) >= 2
                and isinstance(node[0], (int, float))
                and isinstance(node[1], (int, float))
            ):
                coords.append((node[0], node[1]))
            else:
                for item in node:
                    walk(item)

    for feature in features or []:
        walk(((feature or {}).get("geometry") or {}).get("coordinates"))
    if not coords:
        return None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return [min(xs), min(ys), max(xs), max(ys)]


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def apply_edit_changes(self, markers, folderid, polygonfeatures):
    session = Session()
    try:
        user_folder = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        if user_folder:
            # Process each polygon feature
            for index, feature in enumerate(polygonfeatures):
                formatted_datetime = datetime.now().strftime(DATETIME_FORMAT)
                editfile_name = f"edit_at_{formatted_datetime}"

                feature_binary = json.dumps(feature).encode("utf-8")
                new_editfile = editfile_ops.create_editfile(
                    filename=editfile_name,
                    content=feature_binary,
                    folderid=folderid,
                    session=session,
                    # the exact per-point picks, so recomputes re-apply this
                    # edit exactly instead of geometrically
                    markers=markers[index] or None,
                )
                session.commit()

                file_ids = set()
                if markers[index]:
                    for filename in markers[index][0]["editedFile"]:
                        fileVal = file_ops.get_file_with_name(
                            filename=filename, folderid=user_folder.id, session=session
                        )
                        file_ids.add(fileVal.id)

                for file_id in file_ids:
                    file_editfile_link_ops.link_file_and_editfile(file_id, new_editfile.id, session)

                for marker in markers[index]:
                    # A marker with a plan_id SETS that plan on the location
                    # (stamping its values onto the kml rows); without one it
                    # EXCLUDES the location (deletes the rows) — the original
                    # semantics, unchanged.
                    plan = None
                    if marker.get("plan_id"):
                        plan = (
                            session.query(service_plan)
                            .filter(
                                service_plan.id == marker["plan_id"],
                                service_plan.folder_id == user_folder.id,
                            )
                            .one_or_none()
                        )
                        if plan is None:
                            continue  # plan since deleted -> leave the location be
                    for filename in marker["editedFile"]:
                        kml_data_entries = (
                            session.query(kml_data)
                            .join(file)
                            .filter(
                                kml_data.location_id == marker["id"],
                                file.folder_id == user_folder.id,
                                file.name == filename,
                            )
                            .all()
                        )
                        for entry in kml_data_entries:
                            if plan is not None:
                                entry.maxDownloadSpeed = plan.max_download
                                entry.maxUploadSpeed = plan.max_upload
                                entry.latency = 1 if plan.low_latency else 0
                                entry.category = plan.category
                            else:
                                session.delete(entry)

            session.commit()

        else:
            raise Exception("No folder for the user")

        # The availability CSV derives from kml_data, so it can refresh now —
        # exports are correct without waiting for the retile.
        if user_folder.type == "export":
            existing_csvs = file_ops.get_files_by_type(
                folderid=user_folder.id, filetype="export", session=session
            )
            for csv_file in existing_csvs:
                session.delete(csv_file)

            # Generate and save a new CSV
            all_file_ids = [
                file.id
                for file in file_ops.get_files_with_postfix(user_folder.id, ".kml", session)
                + file_ops.get_files_with_postfix(user_folder.id, ".geojson", session)
            ]

            from controllers.database_controller.setting_ops import export_max_service_only

            results = session.query(kml_data).filter(kml_data.file_id.in_(all_file_ids)).all()
            availability_csv = kml_ops.generate_csv_data(
                results,
                user_folder.organization.provider_id,
                user_folder.organization.brand_name,
                max_service_only=export_max_service_only(session),
            )

            csv_name = f"availability-{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.csv"
            csv_data_str = availability_csv.to_csv(index=False, encoding="utf-8")
            new_csv_file = file_ops.create_file(
                filename=csv_name,
                content=csv_data_str.encode("utf-8"),
                folderid=user_folder.id,
                filetype="export",
                session=session,
            )
            session.add(new_csv_file)

    except Exception:
        logger.exception(f"apply_edit_changes failed for folder {folderid}")
        session.rollback()  # rollback transaction on error

    finally:
        session.commit()
        session.close()

    # An edit only changes points inside its drawn polygons, so the dirt is
    # scoped: the rebuild can splice just that region's z9-16 tiles.
    _mark_tiles_dirty(folderid, bbox=_features_bbox(polygonfeatures))


def _rebuild_folder_tiles(folderid):
    """Rebuild a folder's vector tiles from current DB truth (the slow part)."""
    session = Session()
    try:
        geojson_data = vt_ops.folder_coverage_features(folderid, session)
        mbtiles_ops.delete_mbtiles(folderid, session)
        vt_ops.create_tiles(geojson_data, folderid, session)
    finally:
        session.commit()
        session.close()


def _splice_folder_tiles(folderid, bboxes):
    """Splice the dirty regions' z9-16 tiles into the live tileset. True on
    success; False (fall back to a full rebuild) on any failure."""
    try:
        session = Session()
        try:
            return vt_ops.splice_tiles(folderid, bboxes, session)
        finally:
            session.close()
    except Exception:
        logger.exception(f"tile splice failed for folder {folderid}; doing a full rebuild")
        return False


def _coalesced_tile_rebuild(folderid, owner_id):
    """Refresh a folder's tiles, single-flight + coalescing. Callers mark the
    folder dirty after changing its data; the refresh that runs after that
    consumes the dirt. A caller that finds the folder clean no-ops (an
    earlier refresh already covered its change), so N rapid changes cost ~1
    refresh. Returns only once the tiles cover the caller's change.

    Dirt scoped to bboxes (edits) is SPLICED — only the dirty regions' z9-16
    tiles are regenerated, into the current tileset — leaving the z0-8
    overview tiles slightly stale (sub-pixel at those zooms); the settle
    task full-rebuilds once the folder goes quiet. Whole-tileset dirt, a
    splice failure, or no redis means a full rebuild."""
    r = _tiles_redis()
    if r is None:
        _rebuild_folder_tiles(folderid)
        return "tiles rebuilt"

    lock_key = TILES_LOCK_KEY.format(folderid=folderid)
    waited = 0
    while not r.set(lock_key, str(owner_id), nx=True, ex=TILES_LOCK_TTL):
        if waited >= TILES_LOCK_WAIT:
            raise Exception(f"timed out waiting for the tile-rebuild lock on folder {folderid}")
        time.sleep(5)
        waited += 5
    try:
        dirty, bboxes = _pop_tiles_dirt(r, folderid)
        if not dirty:
            return "tiles fresh (an earlier rebuild covered this edit)"
        if dirty == b"bbox" and bboxes and _splice_folder_tiles(folderid, bboxes):
            r.set(TILES_SETTLE_KEY.format(folderid=folderid), str(time.time()))
            return "tiles spliced"
        _rebuild_folder_tiles(folderid)
        r.delete(TILES_SETTLE_KEY.format(folderid=folderid))
        return "tiles rebuilt"
    finally:
        r.delete(lock_key)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def regenerate_tiles(self, folderid):
    """The slow half of an edit chain: refresh the folder's tiles via the
    shared coalescing path (a splice when the dirt is edit-scoped, a full
    rebuild otherwise). 'Task SUCCESS' always means 'the tiles include this
    chain's edit'."""
    return _coalesced_tile_rebuild(folderid, self.request.id)


@celery.task
def settle_stale_tiles():
    """Beat housekeeping: splices leave a folder's z0-8 overview tiles
    slightly stale (an edited dot is sub-pixel at those zooms). Once a
    spliced folder has been quiet for TILES_SETTLE_QUIET, run one full
    rebuild to reconcile. Background work — no job row, so no pill."""
    r = _tiles_redis()
    if r is None:
        return "no redis; nothing to settle"
    settled = []
    for key in r.scan_iter(match=TILES_SETTLE_KEY.format(folderid="*")):
        key = key.decode() if isinstance(key, bytes) else key
        try:
            folderid = int(key.rsplit(":", 1)[1])
            last_splice = float(r.get(key) or 0)
        except (ValueError, AttributeError):
            r.delete(key)
            continue
        if time.time() - last_splice < TILES_SETTLE_QUIET:
            continue
        # Consume the flag first: if the rebuild fails the next edit's splice
        # re-flags, and the dirty mark below survives for the retry anyway.
        r.delete(key)
        _mark_tiles_dirty(folderid)
        regenerate_tiles.apply_async(args=[folderid])
        settled.append(folderid)
    return f"settling folders {settled}" if settled else "nothing to settle"


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def async_folder_copy_for_export(self, folderid, serialized_csv, brandname, deadline):
    from services import export_service

    session = Session()
    try:
        export_service.create_export_snapshot(
            folderid, serialized_csv, brandname, deadline, session
        )
    except Exception as e:
        session.rollback()  # Rollback any changes if there's an exception
        raise e
    finally:
        session.close()  # Ensure session is closed even if there's an exception


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def async_folder_copy_for_import(self, folderid, deadline):
    try:
        session = Session()
        newfolder_name = f"Filing for Deadline {deadline}"

        original_folder = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        new_folder = original_folder.copy(
            name=newfolder_name, type="upload", deadline=deadline, export=False, session=session
        )
        session.commit()
        return new_folder.id
    except Exception as e:
        session.rollback()  # Rollback any changes if there's an exception
        raise e
    finally:
        session.close()  # Ensure session is closed even if there's an exception


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def async_folder_delete(self, folderid):
    try:
        session = Session()
        folder_to_delete = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        session.delete(folder_to_delete)
        session.commit()
    except Exception as e:
        session.rollback()  # Rollback any changes if there's an exception
        raise e
    finally:
        session.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def run_signalserver(self, command, outfile_name, tower_id, data):
    session = Session()
    try:
        result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

        if result.stderr:
            print("SignalServer stderr:", result.stderr.decode())

        bbox = read_rasterkmz(outfile_name + ".kmz")
        filter_image_by_loss(
            outfile_name + ".png",
            int(data["floorLossRate"]),
            outfile_name + ".lcf",
            outfile_name + ".png",
        )
        with open(outfile_name + ".png", "rb") as img_file:
            img_data = img_file.read()

        transparent_image_name = outfile_name + "-transparent.png"
        logger.debug("Generating trans image")
        generate_transparent_image(outfile_name + ".png", transparent_image_name)
        with open(transparent_image_name, "rb") as transparent_img_file:
            transparent_img_data = transparent_img_file.read()
        logger.debug("Generated trans image")
        loss_color_mapping = load_loss_to_color_mapping(outfile_name + ".lcf")
        # Assume we have some way to get raster data after running the command
        raster_data_val = create_rasterdata(
            tower_id=tower_id,
            image_data=img_data,
            transparent_image_data=transparent_img_data,
            loss_color_mapping=loss_color_mapping,
            nbound=bbox["nbound"],
            sbound=bbox["sbound"],
            ebound=bbox["ebound"],
            wbound=bbox["wbound"],
            session=session,
        )

        for f_extension in wireless_raster_file_format:
            os.remove(outfile_name + f_extension)
        os.remove(transparent_image_name)
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.commit()
        session.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def preview_fabric_locaiton_coverage(self, data, userid, outfile_name):
    session = Session()
    try:
        towerVal = get_tower_with_towername(
            tower_name=data["towername"], user_id=userid, session=session
        )
        if isinstance(towerVal, str):  # In case create_tower returned an error
            logger.debug(towerVal)
            return {"error": towerVal}
        if not towerVal:
            logger.debug("tower not found under towername")
            return {"error": "File not found"}

        rasterData = towerVal.raster_data

        # Specify the path for the .png file
        image_file_path = f"{outfile_name}.png"

        # Write the binary image data to a .png file
        with open(image_file_path, "wb") as image_file:
            image_file.write(rasterData.image_data)

        smooth_edges(image_file_path, image_file_path, 2)
        gdal_translate_cmd = f"gdal_translate -a_ullr {rasterData.west_bound} {rasterData.north_bound} {rasterData.east_bound} {rasterData.south_bound} -a_srs EPSG:4326 {image_file_path} {outfile_name}.tif"
        logger.debug("Executing:", gdal_translate_cmd)
        subprocess.run(gdal_translate_cmd, shell=True)

        # Execute gdal_polygonize.py
        gdal_polygonize_cmd = f'gdal_polygonize.py {outfile_name}.tif -f "KML" {outfile_name}.kml'
        logger.debug("Executing:", gdal_polygonize_cmd)
        subprocess.run(gdal_polygonize_cmd, shell=True)

        userVal = user_ops.get_user_with_id(userid=userid)
        folderVal = folder_ops.get_upload_folder(userVal.organization_id, session=session)
        if folderVal is None:
            return {"error": "Folder not found"}

        logger.debug("Computing covered points")
        covered_points = kml_ops.preview_wireless_locations(folderVal.id, outfile_name + ".kml")
        for f_extension in wireless_vector_file_format:
            os.remove(outfile_name + f_extension)
        # Convert the GeoDataFrame to a JSON-friendly format, such as GeoJSON
        covered_points_geojson = covered_points.to_json()
        geojson_filename = outfile_name + ".geojson"
        with open(geojson_filename, "w") as f:
            json.dump(covered_points_geojson, f)
        # Return a native Python dictionary
        return {"Status": "Ok", "geojson_filename": geojson_filename}
    except Exception as e:
        return {"error": str(e)}
    finally:
        session.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def raster2vector(self, data, userid, outfile_name):
    session = Session()
    try:
        towerVal = get_tower_with_towername(
            tower_name=data["towername"], user_id=userid, session=session
        )
        if isinstance(towerVal, str):  # In case create_tower returned an error
            logger.debug(towerVal)
            return {"error": towerVal}
        if not towerVal:
            logger.debug("tower not found under towername")
            return {"error": "File not found"}

        rasterData = towerVal.raster_data

        # Specify the path for the .png file
        image_file_path = f"{outfile_name}.png"

        # Write the binary image data to a .png file
        with open(image_file_path, "wb") as image_file:
            image_file.write(rasterData.image_data)

        smooth_edges(image_file_path, image_file_path, 2)
        gdal_translate_cmd = f"gdal_translate -a_ullr {rasterData.west_bound} {rasterData.north_bound} {rasterData.east_bound} {rasterData.south_bound} -a_srs EPSG:4326 {image_file_path} {outfile_name}.tif"
        logger.debug("Executing:", gdal_translate_cmd)
        subprocess.run(gdal_translate_cmd, shell=True)

        # Execute gdal_polygonize.py
        gdal_polygonize_cmd = f'gdal_polygonize.py {outfile_name}.tif -f "KML" {outfile_name}.kml'
        logger.debug("Executing:", gdal_polygonize_cmd)
        subprocess.run(gdal_polygonize_cmd, shell=True)

        userVal = user_ops.get_user_with_id(userid, session=session)
        folderVal = folder_ops.get_upload_folder(userVal.organization_id, session=session)
        if folderVal is None:
            num_folders = folder_ops.get_number_of_folders_for_user(userVal.id, session=session)
            folder_name = f"{userVal.username}-{num_folders + 1}"
            deadline = "September 2024"
            folderVal = folder_ops.create_folder(
                folder_name, userVal.organization_id, deadline, "upload", session=session
            )
            session.commit()

        vector_file_name = outfile_name + ".kml"
        with open(vector_file_name, "rb") as vector_file:
            kml_binarydata = vector_file.read()
            fileVal = file_ops.create_file(
                vector_file_name, kml_binarydata, folderVal.id, "wireless", session=session
            )
            session.commit()
            downloadSpeed = data["downloadSpeed"]
            uploadSpeed = data["uploadSpeed"]
            techType = data["techType"]
            latency = data["latency"]
            category = data["categoryCode"]

            kml_ops.compute_wireless_locations(
                fileVal.folder_id,
                fileVal.id,
                downloadSpeed,
                uploadSpeed,
                techType,
                latency,
                category,
                session,
            )
            geojson_array = []
            all_kmls = file_ops.get_files_with_postfix(fileVal.folder_id, ".kml", session)
            for kml_f in all_kmls:
                geojson_array.extend(vt_ops.read_kml(kml_f.id, session))
            all_geojsons = file_ops.get_files_with_postfix(fileVal.folder_id, ".geojson", session)
            for geojson_f in all_geojsons:
                geojson_array.extend(vt_ops.read_geojson(geojson_f.id, session))

            logger.info("Creating Vector Tiles")
            mbtiles_ops.delete_mbtiles(fileVal.folder_id, session)
            session.commit()
            vt_ops.create_tiles(geojson_array, fileVal.folder_id, session)

        for f_extension in wireless_vector_file_format:
            os.remove(outfile_name + f_extension)
        return {"Status": "Ok"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        session.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True)
def async_org_delete(self, orgid):
    try:
        session = Session()
        organization = organization_ops.get_organization_with_orgid(org_id=orgid, session=session)
        users = organization_ops.get_all_users_for_organization(org_id=orgid, session=session)
        for user in users:
            user.organization_id = None

        session.delete(organization)
        session.commit()
    except Exception as e:
        session.rollback()  # Rollback any changes if there's an exception
        raise e
    finally:
        session.close()


@celery.task
def sweep_stuck_tasks():
    """Periodic (Celery Beat) stuck-task sweep: an active task-info row older
    than the threshold is presumed dead and marked FAILURE so the job tray can
    tell the user instead of showing it as running forever."""
    from services import job_service

    session = Session()
    try:
        marked = job_service.sweep_stuck_tasks(session)
        if marked:
            logger.info(f"sweep_stuck_tasks: marked {marked} stale task(s) as FAILURE")
        return marked
    finally:
        session.close()


@celery.task(bind=True)
def generate_submission(self, user_id, folderid):
    """Generate a submission as a background job: build the filing's BDC
    availability CSV and freeze it into an export snapshot, inline in this
    task — when the job reports finished the snapshot is downloadable (the
    page's completion modal relies on that). The submissions page serves the
    snapshot's stored bytes, so downloads are byte-stable by construction.
    No autoretry: a refused generate (e.g. provider id removed mid-job)
    shouldn't loop."""
    from services import export_service

    session = Session()
    try:
        csv_output, download_name = export_service.export_filing(
            user_id=user_id, folderid=folderid, session=session, snapshot_inline=True
        )
        if csv_output is None:
            raise ValueError("The filing produced no availability rows")
        return download_name
    finally:
        session.close()
