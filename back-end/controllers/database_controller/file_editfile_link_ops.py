from database.models import file_editfile_link, file, editfile
from database.sessions import ScopedSession, Session


def link_file_and_editfile(file_id, editfile_id, session):
    new_link = file_editfile_link(file_id=file_id, editfile_id=editfile_id)
    session.add(new_link)
    session.commit()
    return new_link


def get_editfiles_for_file(file_id, session):
    file_instance = session.query(file).filter_by(id=file_id).one()
    editfiles = [link.editfile for link in file_instance.editfile_links]
    return editfiles

def get_files_for_editfile(editfile_id, session):
    file_instance = session.query(editfile).filter_by(id=editfile_id).one()
    files = [link.file for link in file_instance.file_links]
    return files