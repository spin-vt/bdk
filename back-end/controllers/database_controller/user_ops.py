from database.models import user
from sqlalchemy.exc import IntegrityError
from utils.settings import DATABASE_URL
from multiprocessing import Lock
from database.sessions import ScopedSession
import psycopg2
from werkzeug.security import generate_password_hash

def get_user_from_db(username):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM \"user\" WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return user

def create_user_in_db(username, password):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("SELECT username FROM \"user\" WHERE username = %s", (username,))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        conn.close()
        return None

    hashed_password = generate_password_hash(password, method='sha256')

    cursor.execute("INSERT INTO \"user\" (username, password) VALUES (%s, %s) RETURNING id", (username, hashed_password))
    new_user_id = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return new_user_id