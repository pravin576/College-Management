import sqlite3
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.app import hash_password, get_db_connection

def clean_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear test/demo data tables
    cursor.execute("DELETE FROM students")
    cursor.execute("DELETE FROM faculty")
    cursor.execute("DELETE FROM hods")
    cursor.execute("DELETE FROM attendance")
    cursor.execute("DELETE FROM results")
    cursor.execute("DELETE FROM fees")
    cursor.execute("DELETE FROM notices")
    cursor.execute("DELETE FROM documents")
    cursor.execute("DELETE FROM contact_messages")
    cursor.execute("DELETE FROM faculty_students")
    cursor.execute("DELETE FROM id_cards")
    cursor.execute("DELETE FROM timetable")
    cursor.execute("DELETE FROM users")

    # Insert single standard System Administrator account
    admin_pass = hash_password("adminpassword")
    cursor.execute(
        """INSERT INTO users (username, password, role, name, email, department, created_at)
           VALUES ('admin', ?, 'Administrator', 'System Administrator', 'admin@college.edu', 'Administration', '2026-08-18 00:00:00')""",
        (admin_pass,)
    )

    # Ensure standard departments exist
    depts = [
        ("CO", "Computer Engineering", "Department of Computer Engineering"),
        ("IT", "Information Technology", "Department of Information Technology"),
        ("ME", "Mechanical Engineering", "Department of Mechanical Engineering"),
        ("CE", "Civil Engineering", "Department of Civil Engineering"),
        ("EE", "Electrical Engineering", "Department of Electrical Engineering"),
        ("EJ", "Electronics & Telecommunication", "Department of Electronics & Telecommunication")
    ]
    for code, name, desc in depts:
        cursor.execute("INSERT OR IGNORE INTO departments (code, name, description) VALUES (?, ?, ?)", (code, name, desc))

    conn.commit()
    conn.close()
    print("Database demo data wiped clean successfully! Admin user restored to 'admin' / 'adminpassword'.")

if __name__ == "__main__":
    clean_database()
