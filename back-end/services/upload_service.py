"""Upload dispatch + filing create/copy.

Extracted verbatim (behavior-preserving) from routes.filings.submit_data. The
route keeps the request parsing (request.files / request.form); this service
takes the already-extracted plain inputs and reproduces the validation and the
three upload operations in the same order:

  op 1 — add files to an existing filing (folderid != -1)
  op 2 — create a new filing from scratch (folderid == -1, no import)
  op 3 — create a new filing by importing/copying a previous one

Validation failures raise ServiceError(message, 400) with the same messages the
route returned. ValueError/TypeError from int()/strptime propagate unchanged, so
the route's existing `except ValueError`/`except Exception` handlers behave as
before.
"""

import base64
import json
import os
from datetime import datetime

from celery import chain

from controllers.celery_controller.celery_tasks import (
    add_files_to_folder,
    async_folder_copy_for_import,
    process_data,
)
from controllers.database_controller import celerytaskinfo_ops, folder_ops, user_ops
from services.audit import log_action
from services.exceptions import ServiceError
from utils.logger_config import logger


def dispatch_upload(
    user_id, folderid, raw_files, file_data_list, import_folder_raw, deadline_raw, session
):
    """Validate the upload, dispatch the appropriate task chain, and record an
    Upload task-info row. Returns the celery task id."""
    operation_detail = "Added more files to a filing"
    filenames = []
    for file_data_str in file_data_list:
        try:
            file_data = json.loads(file_data_str)  # Decode JSON string to Python dictionary
            filename, file_extension = os.path.splitext(file_data["name"])
            if file_extension not in [".csv", ".kml", ".geojson"]:
                raise ServiceError(
                    "Invalid file extension. Allowed extensions are .csv, .kml, and .geojson",
                    400,
                )

            if not file_data["name"].endswith(".csv"):  # Validate speeds only for non-csv files
                try:
                    # Parse speeds as integers
                    download_speed = int(file_data["downloadSpeed"])  # noqa: F841
                    upload_speed = int(file_data["uploadSpeed"])  # noqa: F841
                except (ValueError, KeyError):
                    raise ServiceError(
                        "Please enter valid integer values for download and upload speeds",
                        400,
                    ) from None
                try:
                    latency = int(file_data["latency"])  # noqa: F841
                    techType = int(file_data["techType"])  # noqa: F841
                except (ValueError, KeyError):
                    raise ServiceError(
                        "Please enter valid values for latency and techTypes",
                        400,
                    ) from None

            filenames.append(file_data["name"])  # Collect the filename
        except json.JSONDecodeError:
            raise ServiceError("Invalid JSON format in file data", 400) from None

    userVal = user_ops.get_user_with_id(user_id, session=session)

    if not userVal.verified:
        raise ServiceError("Please Verify your email to start working on a filing", 400)
    if not userVal.organization_id:
        raise ServiceError("Create or join an organization to start working on a filing", 400)
    import_folder_id = int(import_folder_raw)
    # Prepare data for the task
    file_contents = [
        (filename, base64.b64encode(content).decode("utf-8"), data)
        for (filename, content), data in zip(raw_files, file_data_list)
    ]
    if folderid == -1:
        deadline = deadline_raw
        if not deadline:
            raise ServiceError("operation failed, no deadline provided", 400)

        # Attempt to parse the deadline to ensure it's valid
        try:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
        except ValueError:
            raise ServiceError("invalid deadline format", 400) from None

        # One filing per org per BDC window (both create-from-scratch and
        # create-by-import make a new filing for this deadline).
        from services.filing_service import assert_window_available

        assert_window_available(userVal.organization_id, deadline_date, session)

        if import_folder_id != -1:
            if not folder_ops.folder_belongs_to_organization(import_folder_id, user_id, session):
                raise ServiceError(
                    "Operation failed because you are accessing a filing not belong to your organization",
                    400,
                )
            # Asynchronous copy and create new folder with deadline
            logger.info(
                "In operation 3 of upload: create a new filing by importing from previous filings"
            )
            task_chain = chain(
                async_folder_copy_for_import.s(import_folder_id, deadline_date),
                add_files_to_folder.s(file_contents=file_contents),
                process_data.s(operation=3),
            )

            import_folderval = folder_ops.get_folder_with_id(import_folder_id, session=session)
            operation_detail = f"Create a new Filing by importing from filing with deadline {import_folderval.deadline.strftime('%Y-%m')}"

        else:
            # Create new folder with deadline
            logger.info("In operation 2 of upload: create a new filing from scratch")
            new_folder_name = f"Filing for Deadline {deadline_date}"
            folderVal = folder_ops.create_folder(
                new_folder_name, userVal.organization_id, deadline_date, "upload", session
            )
            session.commit()

            task_chain = chain(
                add_files_to_folder.s(folderVal.id, file_contents),
                process_data.si(folderid=folderVal.id, operation=2),
            )

            operation_detail = "Create a new filing"

    else:
        logger.info("In operation 1 of upload: adding more files to a filing")
        if not folder_ops.folder_belongs_to_organization(folderid, user_id, session):
            raise ServiceError(
                "Operation failed because you are accessing a filing not belong to your organization",
                400,
            )
        task_chain = chain(
            add_files_to_folder.s(folderid, file_contents),
            process_data.si(folderid=folderid, operation=1),
        )

        operation_detail = "Add more files to a filing"

    result = task_chain.apply_async()

    if folderid != -1:
        folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        deadline = folderVal.deadline
    else:
        deadline = datetime.strptime(deadline_raw, "%Y-%m-%d").date()

    concatenated_filenames = ", ".join(filenames)
    # Record the dispatch's CURRENT backend state, not a hardcoded PENDING:
    # a near-instant chain can finish before this row exists (task_postrun
    # then finds nothing to update and the row would say running forever).
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=result.task_id,
        status=result.state or "PENDING",
        operation_type="Upload",
        operation_detail=operation_detail,
        user_email=userVal.email,
        organization_id=userVal.organization_id,
        folder_deadline=deadline,
        session=session,
        files_changed=concatenated_filenames,
    )
    # The audit row is the tamper-evident record (celerytaskinfo is
    # operational state); every ingest of provider data must land here.
    log_action(
        "upload",
        user_id=user_id,
        resource_type="folder",
        resource_id=folderid if folderid != -1 else None,
        details={"kind": "coverage", "task_id": result.id, "files": filenames},
    )
    return result.id


def guess_geometry(filename, data):
    """Sniff a coverage upload's geometry and guess its technology (the files
    page's one-tap-correctable default): lines -> wired Fiber (50), polygons ->
    wireless Unlicensed FW (70). Files the geo readers can't parse get no
    guess; mixed files prefer lines, matching what the wired compute extracts.
    Returns {"geom": "lines"|"polygons"|None, "type": ..., "techType": ...}."""
    from controllers.database_controller.geo_io import read_geo_bytes, suffix_for

    try:
        gdf = read_geo_bytes(data, suffix_for(filename))
        geoms = set(gdf.geom_type.unique()) if len(gdf) else set()
    except Exception:
        geoms = set()
    if geoms & {"LineString", "MultiLineString"}:
        return {"geom": "lines", "type": "wired", "techType": 50}
    if geoms & {"Polygon", "MultiPolygon"}:
        return {"geom": "polygons", "type": "wireless", "techType": 70}
    return {"geom": None, "type": None, "techType": None}
