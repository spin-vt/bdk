"""Edit-apply flow: apply marker/polygon edits to a filing and retile.

Extracted verbatim (behavior-preserving) from routes.edit.toggle_markers.
"""

from controllers.celery_controller.celery_tasks import toggle_tiles
from controllers.database_controller import celerytaskinfo_ops, folder_ops, user_ops
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
    result = toggle_tiles.apply_async(args=[filtered_markers, folderid, polygonfeatures])

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
