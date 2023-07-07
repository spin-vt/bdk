from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from database.base import Base
from sqlalchemy import inspect
from utils.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)

inspector = inspect(engine)
if not inspector.has_table('fabric'):
    Base.metadata.create_all(engine)
    
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)