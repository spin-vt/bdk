from flask import request, jsonify
from flask_jwt_extended import decode_token
import psycopg2
import os

db_user = os.getenv('POSTGRES_USER')
db_password = os.getenv('POSTGRES_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
DATABASE_URL = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres'

def user_exists(username): 
    try:
        # Assuming db_host is a variable that contains your database host
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Query the User table
        cursor.execute("SELECT * FROM User WHERE username = %s", (username,))
        user = cursor.fetchone()  # fetchone() returns None if no data is available

        # Close the cursor and connection
        cursor.close()
        conn.close()

        if user is not None: 
            return True 
        else: 
            return False 
    
    except psycopg2.Error as e:
        return jsonify({'message': 'Error querying db'}), 404