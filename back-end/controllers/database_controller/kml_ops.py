import io
import json
import logging
from io import StringIO

import geopandas
import pandas
from shapely.geometry import shape
from sqlalchemy.exc import SQLAlchemyError

from database.models import fabric_data, kml_data
from database.sessions import Session
from utils.logger_config import logger

from .file_editfile_link_ops import get_editfiles_for_file
from .file_ops import get_file_with_id, get_files_by_type, get_files_with_postfix
from .geo_io import read_geo_bytes, suffix_for


def get_kml_data(folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        # Query the File records related to the folder_id
        fabric_files = get_files_by_type(folderid, "fabric", session)
        kml_files = get_files_with_postfix(folderid, ".kml", session)
        geojson_files = get_files_with_postfix(folderid, ".geojson", session)
        coverage_files = kml_files + geojson_files

        # Query all locations in fabric_data
        all_data = {}
        if len(fabric_files) > 0:
            for fabric_file in fabric_files:
                all_locations = (
                    session.query(
                        fabric_data.location_id,
                        fabric_data.latitude,
                        fabric_data.address_primary,
                        fabric_data.longitude,
                        fabric_data.bsl_flag,
                    )
                    .filter(fabric_data.file_id == fabric_file.id)
                    .all()
                )  # Change to fabric_file.id

                # Initialize a dictionary to hold location_id as key and its data as value, including location_id itself
                all_data.update(
                    {
                        r[0]: {
                            "location_id": r[0],
                            "latitude": r[1],
                            "address": r[2],
                            "longitude": r[3],
                            "bsl": r[4],
                        }
                        for r in all_locations
                    }
                )

            default_data = {
                "served": False,
                "wireless": False,
                "lte": False,
                "coveredLocations": "",
                "maxDownloadNetwork": -1,
                "maxDownloadSpeed": -1,
            }

            for kml_file in coverage_files:
                # Query all locations that are served
                resultsServed = (
                    session.query(
                        kml_data.location_id,
                        kml_data.served,
                        kml_data.wireless,
                        kml_data.lte,
                        kml_data.coveredLocations,
                        kml_data.maxDownloadNetwork,
                        kml_data.maxDownloadSpeed,
                    )
                    .filter(
                        kml_data.file_id == kml_file.id  # Change to kml_file.id
                    )
                    .all()
                )

                # Add served data to the respective location in all_data, merge two file that served the same point,
                # record the maxdownloadnetwork and maxuploadspeed
                for r in resultsServed:
                    if r[0] in all_data:
                        existing_data = all_data[r[0]]
                        new_data = {
                            "served": r[1],
                            "wireless": r[2] or existing_data.get("wireless", False),
                            "lte": r[3] or existing_data.get("lte", False),
                            "coveredLocations": ", ".join(
                                filter(None, [r[4], existing_data.get("coveredLocations", "")])
                            ),
                            "maxDownloadNetwork": r[5]
                            if r[6] > existing_data.get("maxDownloadSpeed", -1)
                            else existing_data.get("maxDownloadNetwork", ""),
                            "maxDownloadSpeed": max(
                                r[6], existing_data.get("maxDownloadSpeed", -1)
                            ),
                        }
                        # Merge the existing and new data
                        all_data[r[0]].update(new_data)
                    else:
                        # The location was not in the fabric file, but it is in one of the KML files
                        # You need to decide how to handle this situation.
                        pass

                # For all other locations, fill with default values
            for loc in all_data.values():
                for key, value in default_data.items():
                    loc.setdefault(key, value)
        else:
            for kml_file in coverage_files:
                print(kml_file.name)
                # Query all locations that are served
                resultsServed = (
                    session.query(
                        kml_data.location_id,
                        kml_data.served,
                        kml_data.wireless,
                        kml_data.lte,
                        kml_data.coveredLocations,
                        kml_data.maxDownloadNetwork,
                        kml_data.maxDownloadSpeed,
                        kml_data.address_primary,
                        kml_data.latitude,
                        kml_data.longitude,
                    )
                    .filter(
                        kml_data.file_id == kml_file.id  # Change to kml_file.id
                    )
                    .all()
                )

                # Add served data to the respective location in all_data, merge two file that served the same point,
                # record the maxdownloadnetwork and maxuploadspeed
                for r in resultsServed:
                    existing_data = all_data.get(r[0], {})
                    new_data = {
                        "location_id": r[0],
                        "served": r[1],
                        "wireless": r[2] or existing_data.get("wireless", False),
                        "lte": r[3] or existing_data.get("lte", False),
                        "coveredLocations": ", ".join(
                            filter(None, [r[4], existing_data.get("coveredLocations", "")])
                        ),
                        "maxDownloadNetwork": r[5]
                        if r[6] > existing_data.get("maxDownloadSpeed", -1)
                        else existing_data.get("maxDownloadNetwork", ""),
                        "maxDownloadSpeed": max(r[6], existing_data.get("maxDownloadSpeed", -1)),
                        "address": r[7],
                        "latitude": r[8],
                        "longitude": r[9],
                        "bsl": "False",
                    }
                    # Merge the existing and new data
                    all_data[r[0]] = new_data

        # Convert dictionary values to a list
        data = list(all_data.values())
    except SQLAlchemyError:
        print("Error when querying the database")
        return None
    finally:
        if owns_session:
            session.close()

        return data


def get_kml_data_by_file(fileid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        kml_entries = session.query(kml_data).filter_by(file_id=fileid).all()
        return kml_entries
    finally:
        if owns_session:
            session.close()


def add_to_db(pandaDF, kmlid, download, upload, tech, wireless, latency, category, session):
    """Write one coverage file's computed rows via COPY (one statement on the
    session's own connection, so it commits with the session) — orders of
    magnitude faster than per-row ORM objects for the big result sets."""
    fileVal = get_file_with_id(kmlid)

    try:
        rows = pandaDF[pandaDF.location_id != ""]
        if download == "":
            download = 0

        columns = [
            "location_id",
            "served",
            "wireless",
            "lte",
            "coveredLocations",
            "maxDownloadNetwork",
            "maxDownloadSpeed",
            "maxUploadSpeed",
            "techType",
            "file_id",
            "address_primary",
            "longitude",
            "latitude",
            "latency",
            "category",
        ]
        out = pandas.DataFrame(
            {
                "location_id": rows.location_id.astype(int).values,
                "served": True,
                "wireless": bool(wireless),
                "lte": False,
                "coveredLocations": fileVal.name,
                "maxDownloadNetwork": fileVal.name,
                "maxDownloadSpeed": int(download),
                "maxUploadSpeed": int(upload),
                "techType": tech,
                "file_id": fileVal.id,
                "address_primary": rows.address_primary.values,
                "longitude": rows.longitude.values,
                "latitude": rows.latitude.values,
                "latency": latency,
                "category": category,
            },
            columns=columns,
        )

        if len(out):
            buf = StringIO()
            out.to_csv(buf, index=False, header=False, na_rep="\\N")
            buf.seek(0)
            cols_sql = ", ".join(f'"{c}"' for c in columns)
            cursor = session.connection().connection.cursor()
            cursor.copy_expert(
                f"COPY kml_data ({cols_sql}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf
            )
        session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"Error occurred while inserting data: {e}")
        return False

    return True


def generate_csv_data(results, provider_id, brand_name):
    availability_csv = pandas.DataFrame()

    availability_csv["location_id"] = [row.location_id for row in results]
    availability_csv["provider_id"] = provider_id
    availability_csv["brand_name"] = brand_name
    availability_csv["technology"] = [row.techType for row in results]
    availability_csv["max_advertised_download_speed"] = [row.maxDownloadSpeed for row in results]
    availability_csv["max_advertised_upload_speed"] = [row.maxUploadSpeed for row in results]
    availability_csv["low_latency"] = [row.latency for row in results]
    availability_csv["business_residential_code"] = [row.category for row in results]

    availability_csv.drop_duplicates(
        subset=["location_id", "technology"], keep="first", inplace=True
    )
    availability_csv = availability_csv[
        [
            "provider_id",
            "brand_name",
            "location_id",
            "technology",
            "max_advertised_download_speed",
            "max_advertised_upload_speed",
            "low_latency",
            "business_residential_code",
        ]
    ]

    return availability_csv


def export(folderid, providerid, brandname, deadline, session, dispatch_copy=True):
    """Build the availability CSV. dispatch_copy=True (the legacy /api path)
    hands snapshot creation to a detached Celery task; the generate-submission
    job passes False and snapshots inline so "job done" means downloadable."""
    from controllers.celery_controller.celery_tasks import async_folder_copy_for_export

    all_files = get_files_with_postfix(folderid, ".kml", session) + get_files_with_postfix(
        folderid, ".geojson", session
    )
    all_file_ids = [file.id for file in all_files]
    results = session.query(kml_data).filter(kml_data.file_id.in_(all_file_ids)).all()

    availability_csv = generate_csv_data(results, providerid, brandname)

    output = io.BytesIO()
    availability_csv.to_csv(output, index=False, encoding="utf-8")

    if dispatch_copy:
        csv_data_str = availability_csv.to_csv(index=False, encoding="utf-8")
        async_folder_copy_for_export.apply_async(args=[folderid, csv_data_str, brandname, deadline])

    return output


def rename_conflicting_columns(gdf):
    """Rename 'index_left' and 'index_right' columns if they exist in a GeoDataFrame."""
    rename_dict = {}
    if "index_left" in gdf.columns:
        rename_dict["index_left"] = "index_left_original"
    if "index_right" in gdf.columns:
        rename_dict["index_right"] = "index_right_original"
    return gdf.rename(columns=rename_dict)


def filter_points_within_editfile_polygons(points_gdf, coverage_file, session):
    """Drop the points this coverage file's linked editfiles exclude.

    Editfiles that carry per-point markers are applied exactly: only the
    marked location_ids whose pick names this coverage file are dropped.
    Editfiles without markers (created before markers were persisted) fall
    back to the geometric rule: every point inside the polygon is dropped.
    """
    all_polygons = []
    excluded_ids = set()

    editfiles = get_editfiles_for_file(coverage_file.id, session)
    for editfile in editfiles:
        if editfile.markers:
            for marker in editfile.markers:
                # Only exclude markers drop points. A marker carrying a
                # plan_id SETS a plan instead — the point stays computed and
                # reapply_plan_markers stamps it after add_to_db.
                if marker.get("plan_id"):
                    continue
                if coverage_file.name in (marker.get("editedFile") or []):
                    excluded_ids.add(int(marker["id"]))
            continue
        try:
            geojson_feature = json.loads(editfile.data.decode("utf-8"))
            if geojson_feature["geometry"]["type"] == "Polygon":
                polygon = shape(geojson_feature["geometry"])
                all_polygons.append(polygon)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON data")
            continue

    if excluded_ids:
        points_gdf = points_gdf[~points_gdf["location_id"].astype(int).isin(excluded_ids)]

    if all_polygons:
        polygons_gdf = geopandas.GeoDataFrame(geometry=all_polygons, crs="EPSG:4326")
        # Rename conflicting columns before the spatial join
        points_gdf = rename_conflicting_columns(points_gdf)
        polygons_gdf = rename_conflicting_columns(polygons_gdf)

        # Perform spatial join
        points_gdf = geopandas.sjoin(points_gdf, polygons_gdf, how="left", predicate="within")
        # Keep only points that are NOT within any polygon
        points_gdf = points_gdf[points_gdf.index_right.isna()]

    return points_gdf


def reapply_plan_markers(coverage_file, session):
    """Re-stamp set-plan area edits after a recompute rewrote this coverage
    file's kml rows. Exclude markers are honored by
    filter_points_within_editfile_polygons BEFORE the rows are written; plan
    markers run here AFTER, so both kinds survive a full recompute exactly."""
    from database.models import service_plan

    plans = {}
    for editfile in get_editfiles_for_file(coverage_file.id, session):
        for marker in editfile.markers or []:
            plan_id = marker.get("plan_id")
            if not plan_id or coverage_file.name not in (marker.get("editedFile") or []):
                continue
            if plan_id not in plans:
                plans[plan_id] = (
                    session.query(service_plan)
                    .filter(
                        service_plan.id == plan_id,
                        service_plan.folder_id == coverage_file.folder_id,
                    )
                    .one_or_none()
                )
            plan = plans[plan_id]
            if plan is None:
                continue  # plan since deleted -> the location keeps file values
            session.query(kml_data).filter(
                kml_data.file_id == coverage_file.id,
                kml_data.location_id == int(marker["id"]),
            ).update(
                {
                    kml_data.maxDownloadSpeed: plan.max_download,
                    kml_data.maxUploadSpeed: plan.max_upload,
                    kml_data.latency: 1 if plan.low_latency else 0,
                    kml_data.category: plan.category,
                }
            )
    session.commit()


def load_fabric_gdf(folderid):
    """Parse a folder's active-fabric CSVs into ONE point GeoDataFrame.

    This is the heavy, per-folder-constant part of every coverage compute
    (an ~80 MB CSV parse + point construction), so callers recomputing
    several coverage files should load it once and pass it to
    add_network_data instead of paying it per file. Only the active (BSL)
    fabric drives coverage — non_bsl and supplemental CSVs live in the
    folder too but never enter computation. Returns None with no fabric."""
    fabric_files = get_files_by_type(folderid, "fabric")
    if not fabric_files:
        return None
    df = pandas.concat([pandas.read_csv(StringIO(ff.data.decode())) for ff in fabric_files])
    return geopandas.GeoDataFrame(
        df,
        crs="EPSG:4326",
        geometry=geopandas.points_from_xy(df.longitude, df.latitude),
    )


def compute_wireless_locations(
    folderid, kmlid, download, upload, tech, latency, category, session, fabric=None
):
    coverage_file = get_file_with_id(kmlid)
    if fabric is None:
        fabric = load_fabric_gdf(folderid)
    if fabric is None or coverage_file is None:
        raise FileNotFoundError("Fabric or coverage file not found in the database")

    wireless_coverage = read_geo_bytes(coverage_file.data, suffix_for(coverage_file.name))

    wireless_coverage = wireless_coverage.to_crs("EPSG:4326")
    fabric = rename_conflicting_columns(fabric)
    wireless_coverage = rename_conflicting_columns(wireless_coverage)
    fabric_in_wireless = geopandas.sjoin(fabric, wireless_coverage, how="inner")
    bsl_fabric_in_wireless = fabric_in_wireless[fabric_in_wireless["bsl_flag"]]
    bsl_fabric_in_wireless = bsl_fabric_in_wireless.drop_duplicates(
        subset="location_id", keep="first"
    )

    bsl_fabric_in_wireless = filter_points_within_editfile_polygons(
        bsl_fabric_in_wireless, coverage_file, session
    )
    bsl_fabric_in_wireless = bsl_fabric_in_wireless.drop_duplicates(
        subset="location_id", keep="first"
    )

    logger.debug(f"number of points computed: {len(bsl_fabric_in_wireless)}")
    res = add_to_db(
        bsl_fabric_in_wireless, kmlid, download, upload, tech, True, latency, category, session
    )
    reapply_plan_markers(coverage_file, session)
    return res


def preview_wireless_locations(folderid, kml_filename):
    with open(kml_filename, "rb") as file:  # Open the file in binary mode
        coverage_data = file.read()  # Read the entire content of the file into memory

    fabric = load_fabric_gdf(folderid)
    if fabric is None:
        raise FileNotFoundError("Fabric or coverage file not found in the database")

    wireless_coverage = read_geo_bytes(coverage_data, ".kml")

    wireless_coverage = wireless_coverage.to_crs("EPSG:4326")
    fabric = rename_conflicting_columns(fabric)
    wireless_coverage = rename_conflicting_columns(wireless_coverage)
    fabric_in_wireless = geopandas.sjoin(fabric, wireless_coverage, how="inner")
    bsl_fabric_in_wireless = fabric_in_wireless[fabric_in_wireless["bsl_flag"]]
    bsl_fabric_in_wireless = bsl_fabric_in_wireless.drop_duplicates(
        subset="location_id", keep="first"
    )

    logger.debug(f"number of points computed: {len(bsl_fabric_in_wireless)}")
    return bsl_fabric_in_wireless


def compute_wired_locations(
    folderid, kmlid, download, upload, tech, latency, category, session, fabric=None
):
    if fabric is None:
        fabric = load_fabric_gdf(folderid)
    if fabric is None:
        raise ValueError("No fabric file found")

    # Fetch Fiber file from database
    fiber_file_record = get_file_with_id(kmlid)
    if not fiber_file_record:
        raise ValueError(
            f"No file found with name {fiber_file_record.name} and id {fiber_file_record.id}"
        )

    # Per-file override (files & plans "advanced" setting); NULL keeps the
    # pipeline's longstanding 100 m default.
    buffer_meters = fiber_file_record.coverage_buffer_m or 100
    gdf_fiber = read_geo_bytes(fiber_file_record.data, suffix_for(fiber_file_record.name))

    fiber_paths = gdf_fiber[gdf_fiber.geom_type == "LineString"]

    fiber_paths = fiber_paths.to_crs("epsg:4326")

    fiber_paths_buffer = fiber_paths.to_crs("EPSG:5070")
    fiber_paths_buffer["geometry"] = fiber_paths_buffer.buffer(buffer_meters)
    fiber_paths_buffer = fiber_paths_buffer.to_crs("EPSG:4326")

    fabric_near_fiber = geopandas.sjoin(fabric, fiber_paths_buffer, how="inner")

    bsl_fabric_near_fiber = fabric_near_fiber[fabric_near_fiber["bsl_flag"]]

    bsl_fabric_near_fiber = bsl_fabric_near_fiber.drop_duplicates(
        subset="location_id", keep="first"
    )
    bsl_fabric_near_fiber = filter_points_within_editfile_polygons(
        bsl_fabric_near_fiber, fiber_file_record, session
    )
    bsl_fabric_near_fiber = bsl_fabric_near_fiber.drop_duplicates(
        subset="location_id", keep="first"
    )

    res = add_to_db(
        bsl_fabric_near_fiber, kmlid, download, upload, tech, False, latency, category, session
    )
    reapply_plan_markers(fiber_file_record, session)
    return res


def add_network_data(
    folderid, kmlid, download, upload, tech, type, latency, category, session, fabric=None
):
    """Compute one coverage file's served locations. `fabric` is the optional
    preloaded load_fabric_gdf() frame — pass it when computing several files
    so the fabric is parsed once, not per file."""
    res = False
    if type == 0:
        res = compute_wired_locations(
            folderid, kmlid, download, upload, tech, latency, category, session, fabric=fabric
        )
    elif type == 1:
        res = compute_wireless_locations(
            folderid, kmlid, download, upload, tech, latency, category, session, fabric=fabric
        )
    return res
