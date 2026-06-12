"""Edit-apply flow: apply marker/polygon edits to a filing and retile.

Dispatched as a two-task chain: a fast DB apply (editfiles + kml_data, after
which exports are already correct) followed by the slow, debounced tile
rebuild. The recorded task id is the chain's final task, so a task reaching
SUCCESS still means "the map tiles include this edit".

replace_edit updates a saved edit IN PLACE (shape and/or per-tech picks) and
dispatches the op-4 recompute — the same full re-derivation an undo uses, so
points the old version excluded come back unless the new one still marks them.
"""

import json
import uuid

from celery import chain

from controllers.celery_controller.celery_tasks import (
    apply_edit_changes,
    process_data,
    regenerate_tiles,
)
from controllers.database_controller import (
    celerytaskinfo_ops,
    editfile_ops,
    file_ops,
    folder_ops,
    user_ops,
)
from services.exceptions import ServiceError
from utils.logger_config import logger


def apply_edit(user_id, folderid, markers, polygonfeatures, session):
    """Validate + dispatch a filing edit (toggle_tiles) and record an Edit
    task-info row. Returns the celery task id.

    Raises ServiceError(400) for an invalid folder id, an unverified user, a
    user without an org, a filing outside the user's org, or no valid edits.
    """
    if folderid == -1:
        raise ServiceError("Invalid folder id", 400)

    userVal = user_ops.get_user_with_id(user_id, session=session)
    if not userVal.verified:
        raise ServiceError("Please Verify your email to start working on a filing", 400)
    if not userVal.organization_id:
        raise ServiceError("Create or join an organization to start working on a filing", 400)
    if not folder_ops.folder_belongs_to_organization(folderid, user_id, session):
        raise ServiceError("You are accessing a filing not belong to your organization", 400)

    folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)

    # Filter out points where editedFile is empty.
    filtered_markers = []
    for polygon in markers:
        filtered_polygon = [
            point for point in polygon if point["editedFile"] and len(point["editedFile"]) > 0
        ]
        if filtered_polygon:
            filtered_markers.append(filtered_polygon)

    if len(filtered_markers) == 0:
        raise ServiceError("No valid edits submitted", 400)

    # Generate concatenated_filenames.
    all_filenames = set()
    for polygon in filtered_markers:
        for point in polygon:
            all_filenames.update(point["editedFile"])
    concatenated_filenames = ", ".join(sorted(all_filenames))
    logger.debug(polygonfeatures)
    result = chain(
        apply_edit_changes.s(filtered_markers, folderid, polygonfeatures),
        regenerate_tiles.si(folderid),
    ).apply_async()

    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=result.task_id,
        status="PENDING",
        operation_type="Edit",
        operation_detail="Edit a filing",
        user_email=userVal.email,
        organization_id=userVal.organization_id,
        folder_deadline=folderVal.deadline,
        session=session,
        files_changed=concatenated_filenames,
    )
    return result.task_id


def get_edit(user_id, folderid, editfile_id, session):
    """A saved edit's shape + per-point picks, org-scoped. Raises 404 for an
    edit outside the user's filing."""
    if not folder_ops.folder_belongs_to_organization(folderid, user_id, session):
        raise ServiceError("You are accessing a filing not belong to your organization", 400)
    ef = editfile_ops.get_editfile_with_id(fileid=editfile_id, session=session)
    if ef is None or ef.folder_id != folderid:
        raise ServiceError("Edit not found in this filing", 404)
    try:
        feature = json.loads(bytes(ef.data).decode("utf-8"))
    except Exception:
        raise ServiceError("This edit's shape can't be read", 500) from None
    return {"id": ef.id, "name": ef.name, "feature": feature, "markers": ef.markers or []}


def replace_edit(user_id, folderid, editfile_id, markers, polygonfeature, session):
    """Replace a saved edit in place: new shape and/or per-point picks on the
    SAME editfile row, then the op-4 recompute chain (recompute consults every
    editfile, so the old version's effect lifts and the new one applies — the
    same path an undo takes). Returns the recompute's task id."""
    from database.models import file_editfile_link

    userVal = user_ops.get_user_with_id(user_id, session=session)
    if not userVal.verified:
        raise ServiceError("Please Verify your email to start working on a filing", 400)
    if not userVal.organization_id:
        raise ServiceError("Create or join an organization to start working on a filing", 400)
    if not folder_ops.folder_belongs_to_organization(folderid, user_id, session):
        raise ServiceError("You are accessing a filing not belong to your organization", 400)
    folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
    ef = editfile_ops.get_editfile_with_id(fileid=editfile_id, session=session)
    if ef is None or ef.folder_id != folderid:
        raise ServiceError("Edit not found in this filing", 404)

    filtered = [m for m in (markers or []) if m.get("editedFile")]
    if not filtered:
        raise ServiceError("No valid edits submitted", 400)
    if not polygonfeature:
        raise ServiceError("The edit needs its shape", 400)

    ef.data = json.dumps(
        {**polygonfeature, "properties": {}},
    ).encode("utf-8")
    ef.markers = filtered

    # Relink to exactly the files the new picks name.
    session.query(file_editfile_link).filter(file_editfile_link.editfile_id == ef.id).delete(
        synchronize_session=False
    )
    names = set()
    for m in filtered:
        names.update(m["editedFile"])
    for filename in sorted(names):
        fileVal = file_ops.get_file_with_name(filename=filename, folderid=folderid, session=session)
        if fileVal is not None:
            session.add(file_editfile_link(file_id=fileVal.id, editfile_id=ef.id))

    # The tracking row's commit also persists the editfile changes — and the
    # row must exist BEFORE dispatch (task_postrun updates it by task id).
    task_id = str(uuid.uuid4())
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=task_id,
        status="PENDING",
        operation_type="Edit",
        operation_detail="Update an edit",
        user_email=userVal.email,
        organization_id=userVal.organization_id,
        folder_deadline=folderVal.deadline,
        session=session,
        files_changed=", ".join(sorted(names)),
    )
    process_data.apply_async(args=[folderid, 4], task_id=task_id)
    return task_id
