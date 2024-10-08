from database.sessions import ScopedSession, Session
from database.models import celerytaskinfo, user
from threading import Lock
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import desc
import os
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_celerytasksinfo_for_org(orgid, session):
    try:
        tasks = session.query(celerytaskinfo).filter(celerytaskinfo.organization_id == orgid).order_by(desc(celerytaskinfo.start_time)).all()
        in_progress_tasks = []
        finished_tasks = []

        for task in tasks:
            task_info = {
                'task_id': task.task_id,
                'status': task.status,
                'result': task.result,
                'operation_type': task.operation_type,
                'operation_detail': task.operation_detail,
                'user_email': task.user_email,
                'start_time': task.start_time,
                'folder_deadline': task.folder_deadline.strftime('%Y-%m'),
                'files_changed': task.files_changed
            }
            if task.status in ['PENDING', 'STARTED', 'RETRY']:  # Adjust statuses as per your Celery setup
                in_progress_tasks.append(task_info)
            else:
                finished_tasks.append(task_info)

        return (in_progress_tasks, finished_tasks)

    except Exception as e:
        logger.error(e)
        session.rollback()

def get_estimated_runtime_for_task(task_id, session):
    try:
        # Fetch the task to get its operation type
        task = session.query(celerytaskinfo).filter(celerytaskinfo.task_id == task_id).first()
        
        if not task or task.status not in ['PENDING', 'STARTED', 'RETRY']:
            return 0  # Only estimate runtime for in-progress tasks

        # Fetch the last 5 finished tasks of the same operation
        recent_tasks = session.query(celerytaskinfo.runtime).filter(
            celerytaskinfo.operation_type == task.operation_type,
            celerytaskinfo.status == 'SUCCESS',
            celerytaskinfo.runtime.isnot(None)
        ).order_by(celerytaskinfo.start_time.desc()).limit(5).all()

        if not recent_tasks:
            return 600  # Default a estimate 10 minutes runtime

        # Calculate the average runtime
        avg_runtime = sum([t.runtime for t in recent_tasks]) / len(recent_tasks)
        return avg_runtime * 1.5

    except Exception as e:
        logger.error(e)
        session.rollback()

def update_task_status(task_id, status, session):
    try:
        # Fetch the task to get its operation type
        task = session.query(celerytaskinfo).filter(celerytaskinfo.task_id == task_id).first()
        
        if task:
           task.status = status
           session.commit()

    except Exception as e:
        logger.error(e)
        session.rollback()

def create_celery_taskinfo(task_id, status, operation_type, operation_detail, user_email, organization_id, folder_deadline, session, files_changed=None, result=None):
    """
    Helper function to create a new celery task info entry.

    :param session: SQLAlchemy session
    :param task_id: ID of the task
    :param status: Status of the task
    :param operation: Operation performed by the task
    :param user_id: ID of the user who initiated the task
    :param organization_id: ID of the organization associated with the task
    :param result: Result of the task, if any
    :return: The created CeleryTaskInfo object
    """
    try:
        task_info = celerytaskinfo(
            task_id=task_id,
            status=status,
            operation_type=operation_type,
            operation_detail=operation_detail,
            start_time=datetime.now(),
            user_email=user_email,
            organization_id=organization_id,
            result=result,
            folder_deadline=folder_deadline,
            files_changed=files_changed
        )

        session.add(task_info)
        session.commit()
        return task_info
    except Exception as e:
        logger.error(e)
        session.rollback()


def task_belongs_to_organization(task_id, user_id, session):
    # Retrieve the user based on user_id
    userVal = session.query(user).filter(user.id == user_id).first()
    if not userVal:
        return False

    # Get the user's organization
    user_organization = userVal.organization
    if not user_organization:
        return False

    # Check if the file belongs to this organization
    taskVal = session.query(celerytaskinfo).filter(celerytaskinfo.task_id == task_id).first()
    if not taskVal:
        return False


    return taskVal.organization_id == user_organization.id
