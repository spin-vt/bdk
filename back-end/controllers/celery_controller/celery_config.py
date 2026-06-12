import time
from datetime import datetime

from celery import Celery, signals
from sqlalchemy.exc import OperationalError

from database.models import celerytaskinfo
from database.sessions import Session
from utils.config import Config

MAX_RETRIES = 5
RETRY_DELAY = 1  # Initial delay in seconds


def make_celery():
    celery = Celery(
        __name__,
        backend=Config.CELERY_RESULT_BACKEND,
        broker=Config.CELERY_BROKER_URL,
        include=["controllers.celery_controller.celery_tasks"],
    )
    celery.conf.update(
        # Stuck-task detection: a chain's task-info row is keyed by its FINAL
        # task id, so a crash in an earlier link leaves the row PENDING forever.
        # Beat (the worker runs with -B) periodically sweeps stale active rows
        # to FAILURE so the job tray can say so. See services.job_service.
        beat_schedule={
            "sweep-stuck-tasks": {
                "task": "controllers.celery_controller.celery_tasks.sweep_stuck_tasks",
                "schedule": 300.0,
            },
            # Edit retiles splice only the dirty region (z9-16); this settles
            # the deliberately stale z0-8 overview tiles once a folder has
            # been quiet for a while.
            "settle-stale-tiles": {
                "task": "controllers.celery_controller.celery_tasks.settle_stale_tiles",
                "schedule": 300.0,
            },
        },
    )
    return celery


celery = make_celery()


@signals.task_postrun.connect
def task_postrun_handler(task_id, **kwargs):
    session = Session()
    retries = 0
    try:
        task = session.query(celerytaskinfo).filter(celerytaskinfo.task_id == task_id).first()
        if task:
            task.status = kwargs["state"]
            task.result = str(kwargs["retval"])
            end_time = datetime.now()
            runtime = (end_time - task.start_time).total_seconds() if task.start_time else None
            task.runtime = runtime
            session.commit()
    except OperationalError:
        if session:
            session.rollback()
        while retries <= MAX_RETRIES:
            time.sleep(RETRY_DELAY * (2 * retries))
            retries += 1
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
