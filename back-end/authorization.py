from flask import request, jsonify
from flask_jwt_extended import decode_token
import psycopg2
import os

db_host = os.getenv('postgres', 'localhost')

def user_exists(username): 
    try:
        # Assuming db_host is a variable that contains your database host
        conn = psycopg2.connect(f'postgresql://postgres:db123@{db_host}:5432/postgres')
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