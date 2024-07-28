from database.sessions import ScopedSession, Session
from database.models import celerytaskinfo
from threading import Lock
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
import os
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_celerytasksinfo_for_org(orgid, session):
    try:
        tasks = session.query(celerytaskinfo).filter(celerytaskinfo.organization_id == orgid).all()
        in_progress_tasks = []
        finished_tasks = []

        for task in tasks:
            task_info = {
                'task_id': task.task_id,
                'status': task.status,
                'result': task.result,
                'operation': task.operation,
                'user': task.user.email,
                'timestamp': task.timestamp
            }
            if task.status in ['PENDING', 'STARTED', 'RETRY']:  # Adjust statuses as per your Celery setup
                in_progress_tasks.append(task_info)
            else:
                finished_tasks.append(task_info)

        return (in_progress_tasks, finished_tasks)

    except Exception as e:
        session.rollback()

def create_celery_taskinfo(task_id, status, operation, user_id, organization_id, session, result=None):
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
    task_info = celerytaskinfo(
        task_id=task_id,
        status=status,
        operation=operation,
        timestamp=datetime.now(),
        user_id=user_id,
        organization_id=organization_id,
        result=result
    )
    
    session.add(task_info)
    session.commit()
    return task_info

       