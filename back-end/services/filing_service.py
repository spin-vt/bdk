"""Filing flows: create / copy / delete and related orchestration.

Extracted verbatim (behavior-preserving) from the routes.filings handlers.
"""

from controllers.celery_controller.celery_tasks import async_folder_delete
from controllers.database_controller import celerytaskinfo_ops, folder_ops, user_ops
from services.exceptions import ServiceError


def delete_filing(user_id, folderid, session):
    """Authorize the folder against the user's org, dispatch the async delete,
    and record a Delete task-info row. Returns the celery task id.

    Raises ServiceError(400) if the folder doesn't belong to the user's org.
    """
    if not folder_ops.folder_belongs_to_organization(
        folder_id=folderid, user_id=user_id, session=session
    ):
        raise ServiceError("You are accessing a filing not belong to your organization", 400)

    userVal = user_ops.get_user_with_id(userid=user_id, session=session)
    folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
    deadline = folderVal.deadline
    result = async_folder_delete.apply_async(args=[folderid])
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=result.task_id,
        status="PENDING",
        operation_type="Delete",
        operation_detail="Delete a filing",
        user_email=userVal.email,
        organization_id=userVal.organization_id,
        folder_deadline=deadline,
        session=session,
    )
    return result.task_id
