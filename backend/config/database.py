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

                # Synchronize any existing mismatched statuses between users and role tables
                cursor.execute("UPDATE users u JOIN faculty f ON (u.faculty_id = f.id OR u.email = f.email) SET u.status = f.status WHERE f.status = 'Active' AND u.status = 'Pending'")
                cursor.execute("UPDATE faculty f JOIN users u ON (f.id = u.faculty_id OR f.email = u.email) SET f.status = u.status WHERE u.status = 'Pending' AND f.status = 'Active'")
                cursor.execute("UPDATE users u JOIN hods h ON (u.faculty_id = h.faculty_id OR u.department = h.department OR u.email = h.email) SET u.status = h.status WHERE h.status = 'Active' AND u.status = 'Pending'")
                cursor.execute("UPDATE hods h JOIN users u ON (h.faculty_id = u.faculty_id OR h.department = u.department OR h.email = u.email) SET h.status = u.status WHERE u.status = 'Pending' AND h.status = 'Active'")
            except Exception as e:
                print(f"Notice on column migration / status synchronization: {e}")

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

            # Synchronize / seed login accounts for any existing student records lacking user accounts
            try:
                from auth.utils import hash_password
                stu_pass = hash_password("student123")
                cursor.execute("""
                    INSERT IGNORE INTO users (username, password, role, name, email, department, student_id, mobile, status)
                    SELECT s.id, %s, 'Student', s.name, s.email, s.department, s.id, s.mobile, 'Active'
                    FROM students s
                    LEFT JOIN users u ON (u.student_id = s.id OR u.username = s.id)
                    WHERE u.id IS NULL
                """, (stu_pass,))

                # Synchronize / seed login accounts for any existing faculty records lacking user accounts
                fac_pass = hash_password("faculty123")
                cursor.execute("""
                    INSERT IGNORE INTO users (username, password, role, name, email, department, faculty_id, mobile, status)
                    SELECT f.id, %s, 'Faculty', f.name, f.email, f.department, f.id, f.mobile, 'Active'
                    FROM faculty f
                    LEFT JOIN users u ON (u.faculty_id = f.id OR u.username = f.id)
                    WHERE u.id IS NULL
                """, (fac_pass,))

                # Synchronize / seed login accounts for any existing HOD records lacking user accounts
                hod_pass = hash_password("hod123")
                cursor.execute("""
                    INSERT IGNORE INTO users (username, password, role, name, email, department, faculty_id, mobile, status)
                    SELECT COALESCE(NULLIF(h.faculty_id, ''), CONCAT('hod_', LOWER(REPLACE(h.department, ' ', '_')))), %s, 'HOD', h.name, h.email, h.department, h.faculty_id, h.contact, 'Active'
                    FROM hods h
                    LEFT JOIN users u ON (u.faculty_id = h.faculty_id OR (u.department = h.department AND u.role = 'HOD') OR (u.email = h.email AND u.email != ''))
                    WHERE u.id IS NULL
                """, (hod_pass,))
            except Exception as e:
                print(f"Notice on auto user synchronization: {e}")

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

