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
                "contact_messages.sql",
                "faculty_students.sql"
            ]
            
            schema_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'database', 'schema')
            if os.path.exists(schema_dir):
                for filename in ordered_schemas:
                    filepath = os.path.join(schema_dir, filename)
                    if os.path.exists(filepath):
                        with open(filepath, 'r') as file:
                            sql = file.read()
                            try:
                                for statement in sql.split(';'):
                                    statement = statement.strip()
                                    if statement:
                                        cursor.execute(statement)
                            except Error as e:
                                print(f"Notice executing {filename}: {e}")
                                
            # Safe schema migrations for existing databases
            try:
                cursor.execute("SHOW COLUMNS FROM users LIKE 'status'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE users ADD COLUMN status VARCHAR(50) DEFAULT 'Active'")
                
                cursor.execute("SHOW COLUMNS FROM faculty LIKE 'status'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE faculty ADD COLUMN status VARCHAR(50) DEFAULT 'Active'")
            except Exception as e:
                print(f"Notice on column migration: {e}")

            # Seed default departments if table is empty
            try:
                cursor.execute("SELECT COUNT(*) FROM departments")
                dept_cnt = cursor.fetchone()[0]
                if dept_cnt == 0:
                    depts = [
                        ("CO", "Computer Engineering", "Department of Computer Engineering"),
                        ("ME", "Mechanical Engineering", "Department of Mechanical Engineering"),
                        ("CE", "Civil Engineering", "Department of Civil Engineering"),
                        ("EE", "Electrical Engineering", "Department of Electrical Engineering"),
                        ("EJ", "Electronics & Telecommunication", "Department of Electronics & Telecommunication"),
                        ("AE", "Automobile Engineering", "Department of Automobile Engineering"),
                        ("IF", "Information Technology", "Department of Information Technology")
                    ]
                    for d_code, d_name, d_desc in depts:
                        cursor.execute("INSERT INTO departments (code, name, description) VALUES (%s, %s, %s)", (d_code, d_name, d_desc))
            except Exception as e:
                print(f"Notice seeding departments: {e}")

            # Seed default admin user if not exists
            try:
                cursor.execute("SELECT id FROM users WHERE username = 'admin'")
                if not cursor.fetchone():
                    from auth.utils import hash_password
                    cursor.execute(
                        "INSERT INTO users (username, password, role, name, email, department, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        ("admin", hash_password("admin123"), "Administrator", "System Administrator", "admin@college.edu", "Administration", "Active")
                    )
            except Exception as e:
                print(f"Notice seeding admin: {e}")

            conn.commit()
            cursor.close()
            conn.close()
    except Error as e:
        print(f"CRITICAL ERROR initializing database: {e}")
        # Do not crash the entire app if database init encounters transient warning

