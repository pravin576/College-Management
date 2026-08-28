import os
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 3306)),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", "root123"),
            database=os.environ.get("DB_NAME", "college_erp"),
            auth_plugin='mysql_native_password'
        )
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_db():
    try:
        # Connect without database first to create it if it doesn't exist
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 3306)),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", "root123")
        )
        if conn.is_connected():
            cursor = conn.cursor()
            db_name = os.environ.get("DB_NAME", "college_erp")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            cursor.execute(f"USE {db_name}")

            # Define deterministic order for table creation to satisfy foreign keys
            ordered_schemas = [
                "departments.sql",
                "students.sql",
                "faculty.sql",
                "hods.sql",
                "users.sql",
                "subjects.sql",
                "attendance.sql",
                "fees.sql",
                "results.sql",
                "timetable.sql",
                "notices.sql",
                "documents.sql",
                "contact_messages.sql"
            ]
            
            schema_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'database', 'schema')
            if os.path.exists(schema_dir):
                for filename in ordered_schemas:
                    filepath = os.path.join(schema_dir, filename)
                    if os.path.exists(filepath):
                        with open(filepath, 'r') as file:
                            sql = file.read()
                            try:
                                # execute handles multiple statements if split correctly, but we'll execute one by one
                                for statement in sql.split(';'):
                                    statement = statement.strip()
                                    if statement:
                                        cursor.execute(statement)
                            except Error as e:
                                print(f"CRITICAL ERROR executing {filename}: {e}")
                                os._exit(1)
            conn.commit()
            cursor.close()
            conn.close()
    except Error as e:
        print(f"CRITICAL ERROR initializing database: {e}")
        os._exit(1)
