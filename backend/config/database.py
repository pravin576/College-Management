import os
import mysql.connector
from mysql.connector import Error

# Load environment variables if dotenv is available
try:
    from dotenv import load_dotenv
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_file = os.path.join(root_dir, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        env_example = os.path.join(root_dir, ".env.example")
        if os.path.exists(env_example):
            load_dotenv(env_example)
except ImportError:
    pass

def get_db_config():
    """Retrieve database connection parameters from environment variables with sensible defaults."""
    return {
        "host": os.environ.get("DB_HOST", "localhost").strip(),
        "port": int(os.environ.get("DB_PORT", 3306)),
        "user": os.environ.get("DB_USER", "root").strip(),
        "password": os.environ.get("DB_PASSWORD", "").strip(),
        "database": os.environ.get("DB_NAME", "college_erp").strip()
    }

def format_db_error(e, db_name="college_erp", host="localhost", port=3306, user="root"):
    """Format MySQL connection errors into clear, actionable, password-safe messages."""
    errno = getattr(e, "errno", None)
    msg = str(e)
    if errno in (2003, 2002) or "Can't connect to MySQL server" in msg:
        return f"MySQL server is not running or is not reachable at {host}:{port}. Please verify MySQL service is started."
    elif errno == 1045 or "Access denied" in msg:
        return f"MySQL authentication failed for user '{user}'. Please check DB_USER and DB_PASSWORD."
    elif errno == 1049 or "Unknown database" in msg:
        return f"Database '{db_name}' does not exist. Please create it or run database initialization."
    else:
        return f"MySQL Connection Error [{errno or 'N/A'}]: {msg}"

def get_db_connection():
    """Create and return a MySQL database connection using configured environment parameters."""
    cfg = get_db_config()
    try:
        conn = mysql.connector.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            auth_plugin='mysql_native_password',
            buffered=True
        )
        if conn.is_connected():
            return conn
    except Error as e:
        err_msg = format_db_error(e, db_name=cfg["database"], host=cfg["host"], port=cfg["port"], user=cfg["user"])
        print(f"[DATABASE ERROR] {err_msg}")
        return None
    except Exception as e:
        print(f"[DATABASE ERROR] Unexpected error connecting to MySQL: {e}")
        return None

def test_db_connection():
    """
    Perform a complete health check of the MySQL database connection and tables.
    Returns (success: bool, message: str, details: dict).
    """
    cfg = get_db_config()
    details = {
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "database": cfg["database"],
        "server_reachable": False,
        "auth_valid": False,
        "database_exists": False,
        "tables_accessible": False,
        "table_count": 0
    }
    
    try:
        conn = mysql.connector.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            auth_plugin='mysql_native_password'
        )
        if conn.is_connected():
            details["server_reachable"] = True
            details["auth_valid"] = True
            
            cursor = conn.cursor()
            cursor.execute(f"SHOW DATABASES LIKE '{cfg['database']}'")
            if cursor.fetchone():
                details["database_exists"] = True
                cursor.execute(f"USE {cfg['database']}")
                cursor.execute("SHOW TABLES")
                tables = [r[0] for r in cursor.fetchall()]
                details["tables_accessible"] = True
                details["table_count"] = len(tables)
                details["tables"] = tables
                cursor.close()
                conn.close()
                return True, "MySQL database connection and tables verified successfully.", details
            else:
                cursor.close()
                conn.close()
                return False, f"Database '{cfg['database']}' does not exist on MySQL server.", details
    except Error as e:
        err_msg = format_db_error(e, db_name=cfg["database"], host=cfg["host"], port=cfg["port"], user=cfg["user"])
        return False, err_msg, details
    except Exception as e:
        return False, f"Unexpected error testing database: {e}", details

def init_db():
    """
    Initialize MySQL database and required tables safely without data destruction.
    Preserves all existing tables and records. Never uses DROP or TRUNCATE.
    """
    cfg = get_db_config()
    db_name = cfg["database"]
    
    try:
        # Step 1: Connect to server without database to create database if not exists
        conn = mysql.connector.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            auth_plugin='mysql_native_password'
        )
        if not conn.is_connected():
            print("[DATABASE INIT] Could not establish connection to MySQL server.")
            return False

        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"USE {db_name}")

        # Step 2: Define deterministic schema order for foreign-key compliance
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
        
        schema_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'schema')
        if os.path.exists(schema_dir):
            for filename in ordered_schemas:
                filepath = os.path.join(schema_dir, filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as file:
                        sql = file.read()
                        try:
                            for statement in sql.split(';'):
                                statement = statement.strip()
                                if statement:
                                    cursor.execute(statement)
                        except Error as e:
                            print(f"[DATABASE NOTICE] Notice executing {filename}: {e}")
                            
        # Step 3: Safe, non-destructive schema migrations for existing installations
        try:
            cursor.execute("SHOW COLUMNS FROM users LIKE 'status'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN status VARCHAR(50) DEFAULT 'Active'")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'must_change_password'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INT DEFAULT 0")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'temp_password_created_at'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN temp_password_created_at DATETIME NULL")
            
            cursor.execute("SHOW COLUMNS FROM faculty LIKE 'status'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE faculty ADD COLUMN status VARCHAR(50) DEFAULT 'Active'")

            cursor.execute("SHOW COLUMNS FROM hods LIKE 'status'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE hods ADD COLUMN status VARCHAR(50) DEFAULT 'Active'")

            # Synchronize active statuses across user and role tables safely
            cursor.execute("UPDATE users u JOIN faculty f ON (u.faculty_id = f.id OR u.email = f.email) SET u.status = f.status WHERE f.status = 'Active' AND u.status = 'Pending'")
            cursor.execute("UPDATE faculty f JOIN users u ON (f.id = u.faculty_id OR f.email = u.email) SET f.status = u.status WHERE u.status = 'Pending' AND f.status = 'Active'")
            cursor.execute("UPDATE users u JOIN hods h ON (u.faculty_id = h.faculty_id OR u.department = h.department OR u.email = h.email) SET u.status = h.status WHERE h.status = 'Active' AND u.status = 'Pending'")
            cursor.execute("UPDATE hods h JOIN users u ON (h.faculty_id = u.faculty_id OR h.department = u.department OR h.email = u.email) SET h.status = u.status WHERE u.status = 'Pending' AND h.status = 'Active'")
        except Exception as e:
            print(f"[DATABASE NOTICE] Notice on safe column migrations: {e}")

        # Step 4: Seed default departments if table is empty
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
            print(f"[DATABASE NOTICE] Notice seeding default departments: {e}")

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Error as e:
        err_msg = format_db_error(e, db_name=cfg["database"], host=cfg["host"], port=cfg["port"], user=cfg["user"])
        print(f"[DATABASE INIT ERROR] {err_msg}")
        return False
    except Exception as e:
        print(f"[DATABASE INIT ERROR] Unexpected error initializing database: {e}")
        return False
