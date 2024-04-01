from database.models import folder
from sqlalchemy.exc import IntegrityError
from utils.settings import DATABASE_URL
from multiprocessing import Lock
from database.sessions import ScopedSession, Session


session = Session()

def update_folders_deadline():

    try:
        folders = session.query(folder).filter(folder.deadline == None)

        for folder1 in folders:
            folder1.deadline = "September 2024"

        session.commit()

        print("Deadlines updated successfully")
    except Exception as e:
        print(f"Error occured: {e}")
        session.rollback()
    finally:
        session.close()
if __name__ == "__main__":
    update_folders_deadline()

    
