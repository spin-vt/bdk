from database.models import kmz
from sqlalchemy.exc import IntegrityError
from utils.settings import BATCH_SIZE, DATABASE_URL
from sqlalchemy.exc import SQLAlchemyError
from database.sessions import ScopedSession, Session
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from io import BytesIO
import zipfile


def create_kmz(filename, folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        new_kmz = kmz(name=filename, folder_id=folderid)
        session.add(new_kmz)
        if owns_session:
            session.commit()
        return new_kmz
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()

def get_kmz_with_name(filename, folderid, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True

    try:
        existing_file = session.query(kmz).filter(kmz.name == filename, kmz.folder_id == folderid).first()
        return existing_file
    except NoResultFound:
        return None
    except MultipleResultsFound:
        print(f"Multiple files found with the same name: {filename}")
        return None
    except SQLAlchemyError as e:
        print(f"Error occurred during query: {str(e)}")
        return None
    finally:
        if owns_session:
            session.close()

def extract_kml_from_kmz(kmz_content):
    """
    Given the contents of a KMZ file, this function extracts all the KML files within it.
    Args:
    - kmz_content (bytes): The binary content of the KMZ file.

    Returns:
    - List[Dict[str, bytes]]: A list of dictionaries, each containing a 'filename' and 'data' of the KML file.
    """
    kml_entries = []

    # Convert bytes to a file-like object
    kmz_data = BytesIO(kmz_content)

    with zipfile.ZipFile(kmz_data) as z:
        for file_info in z.infolist():
            if file_info.filename.endswith('.kml'):
                kml_data = z.read(file_info.filename)
                kml_entries.append({'filename': file_info.filename, 'data': kml_data})

    return kml_entries


