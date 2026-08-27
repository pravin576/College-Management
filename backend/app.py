#!/usr/bin/env python3
"""
SimpleERP - College ERP Management System
Python 3 Backend REST API & Static File Server with SQLite Data Persistence
Zero demo data, Secure Hashed Password Authentication, and Role-Based Authorization
"""

import http.server
import socketserver
import json
import os
import urllib.parse
import urllib.request
import sqlite3
import uuid
import time
import re
import hashlib
import mimetypes
import random
import string
import base64
import io
import zipfile
import xml.etree.ElementTree as ET

PORT = 8000

# Resolve project paths dynamically so server works from any working directory
CUR_FILE_DIR = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(CUR_FILE_DIR, "frontend")):
    BASE_DIR = CUR_FILE_DIR
elif os.path.exists(os.path.join(CUR_FILE_DIR, "..", "frontend")):
    BASE_DIR = os.path.abspath(os.path.join(CUR_FILE_DIR, ".."))
elif os.path.exists(os.path.join(CUR_FILE_DIR, "College Management", "frontend")):
    BASE_DIR = os.path.abspath(os.path.join(CUR_FILE_DIR, "College Management"))
else:
    BASE_DIR = os.path.abspath(os.path.join(CUR_FILE_DIR, ".."))

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DB_FILE = os.path.join(DATABASE_DIR, "college_erp.db")
UPLOADS_DIR = os.path.join(FRONTEND_DIR, "uploads")

os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Global In-Memory Session Store: token -> user_dict
SESSIONS = {}

def parse_xlsx_bytes(file_bytes):
    """
    Parses an .xlsx file from binary bytes using zipfile & xml.etree.ElementTree.
    Returns a list of rows, where each row is a list of string values.
    """
    rows_data = []
    bio = io.BytesIO(file_bytes)
    with zipfile.ZipFile(bio) as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            with z.open('xl/sharedStrings.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                for si in root.iter():
                    if si.tag.endswith('si'):
                        texts = [t.text or '' for t in si.iter() if t.tag.endswith('t')]
                        shared_strings.append(''.join(texts))

        sheet_names = [n for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
        if not sheet_names:
            return []

        with z.open(sheet_names[0]) as f:
            tree = ET.parse(f)
            root = tree.getroot()
            
            for elem in root.iter():
                if elem.tag.endswith('row'):
                    row_vals = []
                    for c in elem:
                        if c.tag.endswith('c'):
                            t = c.get('t')
                            val = ''
                            for child in c:
                                if child.tag.endswith('v') or child.tag.endswith('t'):
                                    val = child.text or ''
                                    break
                            if t == 's' and val.isdigit():
                                idx = int(val)
                                if idx < len(shared_strings):
                                    val = shared_strings[idx]
                            row_vals.append(val.strip())
                    if any(row_vals):
                        rows_data.append(row_vals)
    return rows_data

def build_xlsx_bytes(headers, sample_rows):
    """
    Generates a valid .xlsx file in memory containing headers and sample_rows.
    """
    all_rows = [headers] + sample_rows
    strings = []
    string_map = {}

    for row in all_rows:
        for val in row:
            s_val = str(val)
            if s_val not in string_map:
                string_map[s_val] = len(strings)
                strings.append(s_val)

    sst_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{0}" uniqueCount="{0}">'.format(len(strings))
    for s in strings:
        escaped_s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        sst_xml += f'<si><t>{escaped_s}</t></si>'
    sst_xml += '</sst>'

    sheet_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for r_idx, row in enumerate(all_rows, start=1):
        sheet_xml += f'<row r="{r_idx}">'
        for c_idx, val in enumerate(row, start=1):
            col_letter = chr(64 + c_idx) if c_idx <= 26 else 'A' + chr(64 + c_idx - 26)
            s_idx = string_map[str(val)]
            sheet_xml += f'<c r="{col_letter}{r_idx}" t="s"><v>{s_idx}</v></c>'
        sheet_xml += '</row>'
    sheet_xml += '</sheetData></worksheet>'

    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>'
    dot_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    workbook_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>'
    workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="Data" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>'

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', dot_rels)
        z.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
        z.writestr('xl/workbook.xml', workbook)
        z.writestr('xl/sharedStrings.xml', sst_xml)
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    return buf.getvalue()

def create_student_template_xlsx():
    headers = [
        "Student ID", "Roll Number", "Student Name", "Email", "Mobile Number",
        "Gender", "DOB", "Department", "Year", "Semester", "Division",
        "Admission Year", "Address", "Status"
    ]
    sample_rows = [
        ["STU1001", "1", "Rahul Patil", "rahul.patil@college.edu", "9876543210", "Male", "2005-04-12", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Awasari, Pune", "Active"],
        ["STU1002", "2", "Priya Shinde", "priya.shinde@college.edu", "9876543211", "Female", "2005-08-20", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Awasari, Pune", "Active"]
    ]
    return build_xlsx_bytes(headers, sample_rows)

def create_attendance_template_xlsx():
    headers = [
        "Student ID", "Student Name", "Department", "Year", "Semester",
        "Division", "Subject", "Subject Code", "Date", "Attendance Status"
    ]
    sample_rows = [
        ["STU1001", "Rahul Patil", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Present"],
        ["STU1002", "Amit Shinde", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Absent"],
        ["STU1003", "Priya Patil", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Present"]
    ]
    return build_xlsx_bytes(headers, sample_rows)

def create_results_template_xlsx():
    headers = [
        "Student ID", "Student Name", "Department", "Semester", "Subject",
        "Internal Marks (30)", "End Sem Marks (70)"
    ]
    sample_rows = [
        ["STU1001", "Rahul Patil", "Computer Engineering", "Semester 3", "Software Engineering", "25", "58"],
        ["STU1002", "Priya Shinde", "Computer Engineering", "Semester 3", "Software Engineering", "22", "45"]
    ]
    return build_xlsx_bytes(headers, sample_rows)

def hash_password(password: str) -> str:
    salt = hashlib.sha256(str(time.time()).encode('utf-8')).hexdigest()[:16]
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}${key.hex()}"

def verify_password(stored_password: str, provided_password: str) -> bool:
    if not stored_password or not provided_password:
        return False
    if "$" not in stored_password:
        return stored_password == provided_password
    salt, key_hex = stored_password.split("$", 1)
    key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return key.hex() == key_hex

def check_duplicate_account(cursor, mobile=None, email=None, student_id=None, faculty_id=None, username=None):
    """
    Checks duplicate entries across users, students, faculty, and hods tables.
    Returns (is_duplicate: bool, error_message: str)
    """
    if username:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return True, f"Username '{username}' is already registered!"
            
    if email:
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            return True, f"Email '{email}' is already registered under another account!"
        cursor.execute("SELECT id FROM students WHERE email = ?", (email,))
        if cursor.fetchone():
            return True, f"Email '{email}' is already registered in student records!"
        cursor.execute("SELECT id FROM faculty WHERE email = ?", (email,))
        if cursor.fetchone():
            return True, f"Email '{email}' is already registered in faculty records!"
        cursor.execute("SELECT id FROM hods WHERE email = ?", (email,))
        if cursor.fetchone():
            return True, f"Email '{email}' is already registered in HOD records!"

    if mobile:
        cursor.execute("SELECT id FROM users WHERE mobile = ?", (mobile,))
        if cursor.fetchone():
            return True, f"Mobile number '{mobile}' is already registered under another account!"
        cursor.execute("SELECT id FROM students WHERE mobile = ?", (mobile,))
        if cursor.fetchone():
            return True, f"Mobile number '{mobile}' is already registered for a student!"
        cursor.execute("SELECT id FROM faculty WHERE mobile = ?", (mobile,))
        if cursor.fetchone():
            return True, f"Mobile number '{mobile}' is already registered for a faculty member!"
        cursor.execute("SELECT id FROM hods WHERE contact = ?", (mobile,))
        if cursor.fetchone():
            return True, f"Mobile number '{mobile}' is already registered for an HOD!"

    if student_id:
        cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        if cursor.fetchone():
            return True, f"Student ID '{student_id}' is already registered!"

    if faculty_id:
        cursor.execute("SELECT id FROM faculty WHERE id = ?", (faculty_id,))
        if cursor.fetchone():
            return True, f"Faculty ID '{faculty_id}' is already registered!"

    return False, ""

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    return conn

def init_db():
    """Initializes SQLite database schema cleanly without seeding fake demo records."""
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR, exist_ok=True)

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        department TEXT,
        student_id TEXT,
        faculty_id TEXT,
        mobile TEXT,
        created_at TEXT,
        must_change_password INTEGER DEFAULT 0,
        temp_password_created_at TEXT
    )''')
    
    # 2. Departments Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT
    )''')

    # 3. Students Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        roll_number TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mobile TEXT NOT NULL,
        gender TEXT NOT NULL,
        dob TEXT NOT NULL,
        department TEXT NOT NULL,
        year TEXT DEFAULT 'First Year',
        semester TEXT NOT NULL,
        division TEXT NOT NULL,
        admission_year TEXT NOT NULL,
        address TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        photo TEXT DEFAULT ''
    )''')

    # 4. Faculty Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS faculty (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        designation TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mobile TEXT NOT NULL,
        experience TEXT,
        status TEXT DEFAULT 'Active'
    )''')

    # 5. HODs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        qualification TEXT NOT NULL,
        experience TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        contact TEXT NOT NULL,
        faculty_id TEXT
    )''')

    # 6. Subjects Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        semester TEXT NOT NULL,
        credits INTEGER DEFAULT 4,
        faculty_id TEXT
    )''')

    # 7. Attendance Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        subject TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,
        faculty_id TEXT,
        department TEXT NOT NULL,
        year TEXT DEFAULT 'First Year',
        semester TEXT DEFAULT 'Semester 1',
        division TEXT DEFAULT 'A',
        subject_code TEXT DEFAULT '',
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    # 8. Results Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        subject TEXT NOT NULL,
        semester TEXT NOT NULL,
        internal_marks REAL NOT NULL,
        end_sem_marks REAL NOT NULL,
        total_marks REAL NOT NULL,
        percentage REAL NOT NULL,
        grade TEXT NOT NULL,
        status TEXT NOT NULL,
        document TEXT DEFAULT '',
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    # 9. Fees Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        department TEXT NOT NULL,
        total_fees REAL NOT NULL,
        paid_fees REAL NOT NULL,
        pending_fees REAL NOT NULL,
        payment_date TEXT,
        payment_status TEXT NOT NULL,
        receipt_number TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    # 10. Timetable Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS timetable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department TEXT NOT NULL,
        semester TEXT NOT NULL,
        division TEXT NOT NULL,
        day TEXT NOT NULL,
        time TEXT NOT NULL,
        subject TEXT NOT NULL,
        faculty TEXT NOT NULL,
        room TEXT NOT NULL
    )''')

    # 11. Notices Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notices (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        date TEXT NOT NULL,
        department TEXT NOT NULL,
        target_role TEXT DEFAULT 'All',
        priority TEXT NOT NULL,
        description TEXT NOT NULL,
        attachment TEXT,
        author TEXT
    )''')

    # 12. Documents Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        department TEXT NOT NULL,
        file_path TEXT NOT NULL,
        uploaded_by TEXT NOT NULL,
        upload_date TEXT NOT NULL,
        semester TEXT DEFAULT 'All',
        subject TEXT DEFAULT 'All'
    )''')

    # 13. Contact Messages Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contact_messages (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        recipientEmail TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT DEFAULT 'Unread'
    )''')

    # 14. Student ID Cards Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS id_cards (
        student_id TEXT PRIMARY KEY,
        issue_date TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    # 15. Faculty-Student Assignments Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS faculty_students (
        faculty_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        PRIMARY KEY (faculty_id, student_id),
        FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    # Safe column migrations for older database files
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN mobile TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN temp_password_created_at TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN year TEXT DEFAULT 'First Year'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN photo TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE fees ADD COLUMN receipt_number TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN semester TEXT DEFAULT 'All'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN subject TEXT DEFAULT 'All'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN year TEXT DEFAULT 'First Year'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN semester TEXT DEFAULT 'Semester 1'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN division TEXT DEFAULT 'A'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN subject_code TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE results ADD COLUMN document TEXT DEFAULT ''")
    except Exception:
        pass

    # 14. Faculty-Student Assignments Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS faculty_students (
        faculty_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        PRIMARY KEY (faculty_id, student_id),
        FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    # Seed default official government polytechnic departments
    default_depts = [
        ("CO", "Computer Engineering", "Department of Computer Engineering"),
        ("IF", "Information Technology", "Department of Information Technology"),
        ("ME", "Mechanical Engineering", "Department of Mechanical Engineering"),
        ("AE", "Automobile Engineering", "Department of Automobile Engineering"),
        ("CE", "Civil Engineering", "Department of Civil Engineering"),
        ("EE", "Electrical Engineering", "Department of Electrical Engineering"),
        ("EJ", "Electronics & Telecommunication", "Department of Electronics & Telecommunication Engineering"),
        ("SH", "Science & Humanities", "Department of Science & Humanities"),
        ("ADM", "Administration", "Administrative Department")
    ]
    for code, name, desc in default_depts:
        cursor.execute("INSERT OR IGNORE INTO departments (code, name, description) VALUES (?, ?, ?)", (code, name, desc))

    # Seed default fee records for students if fees table is empty
    cursor.execute("SELECT COUNT(*) FROM fees")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id, name, department FROM students")
        stus = cursor.fetchall()
        for s in stus:
            r_num = f"REC-2026-{1000 + (abs(hash(s[0])) % 8000)}"
            cursor.execute(
                "INSERT OR IGNORE INTO fees (student_id, student_name, department, total_fees, paid_fees, pending_fees, payment_date, payment_status, receipt_number) VALUES (?, ?, ?, 85000.0, 50000.0, 35000.0, ?, 'Partial', ?)",
                (s[0], s[1], s[2], time.strftime('%Y-%m-%d'), r_num)
            )

    # Seed initial System Administrator account if database is completely empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        admin_pass = hash_password("admin123")
        cursor.execute(
            "INSERT INTO users (username, password, role, name, email, department, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("admin", admin_pass, "Administrator", "System Administrator", "admin@college.edu", "Administration", time.strftime('%Y-%m-%d %H:%M:%S'))
        )
    
    conn.commit()
    conn.close()


class ERPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom Request Handler for REST API endpoints and static file serving."""

    def _send_json(self, data, status_code=200, headers=None):
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Session-Token")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Session-Token")
        self.end_headers()

    def get_session_token(self):
        auth_header = self.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        
        x_token = self.headers.get("X-Session-Token")
        if x_token:
            return x_token.strip()

        cookie_header = self.headers.get("Cookie")
        if cookie_header:
            cookies = urllib.parse.parse_qs(cookie_header.replace("; ", "&"))
            if "session_token" in cookies:
                return cookies["session_token"][0].strip()
        
        return None

    def get_current_user(self):
        token = self.get_session_token()
        if token and token in SESSIONS:
            return SESSIONS[token]
        return None

    def serve_static_file(self, rel_path):
        clean_path = rel_path.split("?")[0].lstrip("/")
        if not clean_path:
            clean_path = "index.html"
            
        # Static files are served from the frontend folder.
        full_path = os.path.normpath(os.path.join(FRONTEND_DIR, clean_path))
        if not full_path.startswith(os.path.normpath(FRONTEND_DIR) + os.sep) and full_path != os.path.normpath(FRONTEND_DIR):
            self.send_response(403)
            self.end_headers()
            return

        if not os.path.exists(full_path) or os.path.isdir(full_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>404 Not Found</h1><p>File not found.</p>")
            return

        ext = os.path.splitext(full_path)[1].lower()
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".htm": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".webp": "image/webp",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".csv": "text/csv; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
            ".zip": "application/zip"
        }

        content_type = content_types.get(ext, mimetypes.guess_type(full_path)[0] or "application/octet-stream")

        try:
            with open(full_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h1>500 Internal Error</h1><p>{e}</p>".encode("utf-8"))

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # Static file routing handling
        if path == "/" or path == "/index.html":
            return self.serve_static_file("index.html")

        if not path.startswith("/api/"):
            return self.serve_static_file(path)

        # Public API Endpoints
        if path == "/api/health":
            self._send_json({"status": "ok", "message": "College ERP Python Server Running"})
            return

        if path == "/api/auth/me":
            user = self.get_current_user()
            if user:
                self._send_json({"success": True, "user": user})
            else:
                self._send_json({"success": False, "message": "Not authenticated"}, 401)
            return

        if path == "/api/departments":
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM departments ORDER BY name ASC")
            depts = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "departments": depts})
            return

        if path in ["/api/public/notices", "/api/notices/public"]:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notices WHERE target_role IN ('All', 'Public', 'Student') ORDER BY rowid DESC LIMIT 10")
            notices = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "notices": notices})
            return

        if path in ["/api/public/courses", "/api/courses/public"]:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subjects ORDER BY name ASC")
            courses = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "courses": courses})
            return

        if path == "/api/students/excel-template":
            xlsx_bytes = create_student_template_xlsx()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", 'attachment; filename="student_import_template.xlsx"')
            self.send_header("Content-Length", str(len(xlsx_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(xlsx_bytes)
            return

        if path == "/api/attendance/excel-template":
            xlsx_bytes = create_attendance_template_xlsx()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", 'attachment; filename="attendance_import_template.xlsx"')
            self.send_header("Content-Length", str(len(xlsx_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(xlsx_bytes)
            return

        if path == "/api/results/excel-template":
            xlsx_bytes = create_results_template_xlsx()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", 'attachment; filename="exam_results_template.xlsx"')
            self.send_header("Content-Length", str(len(xlsx_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(xlsx_bytes)
            return

        # Protected API Endpoints - Authorization Check
        user = self.get_current_user()
        if not user:
            self._send_json({"success": False, "message": "Authentication required"}, 401)
            return

        role = user["role"]
        user_dept = user.get("department", "")
        student_id = user.get("student_id", "")
        faculty_id = user.get("faculty_id", "")

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Students Endpoint
        if path == "/api/students":
            dept_f = query_params.get("department", [None])[0]
            year_f = query_params.get("year", [None])[0]
            sem_f = query_params.get("semester", [None])[0]
            div_f = query_params.get("division", [None])[0]
            search_q = query_params.get("search", [None])[0]
            fac_f = query_params.get("faculty_id", [None])[0]
            assigned_only = query_params.get("assigned_only", [None])[0]

            if role == "Student":
                cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
            else:
                sql = "SELECT DISTINCT s.* FROM students s"
                joins = []
                where_clauses = []
                params = []

                # Role & faculty assignment scoping
                target_fac = fac_f if fac_f else (faculty_id if (role == "Faculty" and (assigned_only == "true" or not dept_f)) else None)
                if target_fac:
                    joins.append("JOIN faculty_students fs ON s.id = fs.student_id")
                    where_clauses.append("fs.faculty_id = ?")
                    params.append(target_fac)

                if role in ["HOD", "Faculty"] and not dept_f and not target_fac:
                    where_clauses.append("s.department = ?")
                    params.append(user_dept)
                elif dept_f and dept_f != "All":
                    where_clauses.append("s.department = ?")
                    params.append(dept_f)

                if year_f and year_f != "All":
                    where_clauses.append("s.year = ?")
                    params.append(year_f)

                if sem_f and sem_f != "All":
                    where_clauses.append("s.semester = ?")
                    params.append(sem_f)

                if div_f and div_f != "All":
                    where_clauses.append("s.division = ?")
                    params.append(div_f)

                if search_q:
                    where_clauses.append("(s.name LIKE ? OR s.id LIKE ? OR s.roll_number LIKE ? OR s.email LIKE ?)")
                    sq = f"%{search_q.strip()}%"
                    params.extend([sq, sq, sq, sq])

                full_sql = sql
                if joins:
                    full_sql += " " + " ".join(joins)
                if where_clauses:
                    full_sql += " WHERE " + " AND ".join(where_clauses)
                full_sql += " ORDER BY s.department, s.year, s.semester, s.division, s.roll_number"

                cursor.execute(full_sql, tuple(params))

            students = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "students": students})
            return

        # Faculty-Student Assignments GET Endpoint
        elif path == "/api/faculty-students":
            target_faculty_id = query_params.get("faculty_id", [faculty_id if role == "Faculty" else None])[0]
            year_f = query_params.get("year", [None])[0]
            sem_f = query_params.get("semester", [None])[0]
            div_f = query_params.get("division", [None])[0]
            dept_f = query_params.get("department", [None])[0]

            if not target_faculty_id:
                conn.close()
                self._send_json({"success": False, "message": "faculty_id is required"}, 400)
                return

            sql = """
                SELECT s.* FROM students s
                JOIN faculty_students fs ON s.id = fs.student_id
                WHERE fs.faculty_id = ?
            """
            p = [target_faculty_id]
            if dept_f and dept_f != "All":
                sql += " AND s.department = ?"; p.append(dept_f)
            if year_f and year_f != "All":
                sql += " AND s.year = ?"; p.append(year_f)
            if sem_f and sem_f != "All":
                sql += " AND s.semester = ?"; p.append(sem_f)
            if div_f and div_f != "All":
                sql += " AND s.division = ?"; p.append(div_f)
            sql += " ORDER BY s.department, s.year, s.semester, s.division, s.roll_number"

            cursor.execute(sql, tuple(p))
            students = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "students": students, "faculty_id": target_faculty_id})
            return

        # Comprehensive HOD Dashboard Dynamic Stats Endpoint
        elif path == "/api/hod/dashboard-stats":
            dept_override = query_params.get("department", [None])[0]
            if dept_override and dept_override != "All":
                target_dept = dept_override
            else:
                target_dept = user_dept if user_dept else "Computer Engineering"
            
            cursor.execute("SELECT COUNT(*) FROM students WHERE department = ?", (target_dept,))
            cnt_total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM students WHERE department = ? AND (year = 'First Year' OR year IS NULL OR year = '')", (target_dept,))
            cnt_first = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM students WHERE department = ? AND year = 'Second Year'", (target_dept,))
            cnt_second = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM students WHERE department = ? AND year = 'Third Year'", (target_dept,))
            cnt_third = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM faculty WHERE department = ?", (target_dept,))
            cnt_fac = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) FROM attendance WHERE department = ?", (target_dept,))
            att_row = cursor.fetchone()
            tot_att = att_row[0] or 0
            pres_att = att_row[1] or 0
            att_pct = round((pres_att / tot_att * 100), 1) if tot_att > 0 else 100.0

            cursor.execute("SELECT COUNT(*), SUM(CASE WHEN r.status = 'Pass' THEN 1 ELSE 0 END) FROM results r JOIN students s ON r.student_id = s.id WHERE s.department = ?", (target_dept,))
            res_row = cursor.fetchone()
            tot_res = res_row[0] or 0
            pass_res = res_row[1] or 0
            pass_pct = round((pass_res / tot_res * 100), 1) if tot_res > 0 else 100.0

            cursor.execute("SELECT SUM(pending_fees) FROM fees WHERE department = ?", (target_dept,))
            pending_fees = cursor.fetchone()[0] or 0.0

            cursor.execute("SELECT COUNT(*) FROM notices WHERE department IN ('All', ?)", (target_dept,))
            cnt_notices = cursor.fetchone()[0]

            conn.close()
            self._send_json({
                "success": True,
                "department": target_dept,
                "stats": {
                    "totalStudents": cnt_total,
                    "firstYearStudents": cnt_first,
                    "secondYearStudents": cnt_second,
                    "thirdYearStudents": cnt_third,
                    "totalFaculty": cnt_fac,
                    "attendancePercentage": att_pct,
                    "resultPassPercentage": pass_pct,
                    "pendingFees": pending_fees,
                    "departmentNotices": cnt_notices
                }
            })
            return

        # Student ID Card Payload Endpoint
        elif path == "/api/students/id-card":
            target_id = query_params.get("id", [student_id])[0]
            cursor.execute("SELECT * FROM students WHERE id = ?", (target_id,))
            s_row = cursor.fetchone()
            if not s_row:
                conn.close()
                self._send_json({"success": False, "message": "Student record not found"}, 404)
                return
            s = dict(s_row)
            card = {
                "collegeName": "Government Polytechnic, Awasari (Kh.)",
                "collegeSubtitle": "Autonomous Institute of Government of Maharashtra",
                "collegeLogo": "images/logo.jpg",
                "studentPhoto": s.get("photo") or "images/img1.jpg",
                "studentName": s["name"],
                "studentId": s["id"],
                "rollNumber": s["roll_number"],
                "department": s["department"],
                "year": s.get("year", "First Year"),
                "semester": s.get("semester", "Semester 1"),
                "division": s.get("division", "A"),
                "email": s["email"],
                "mobile": s["mobile"],
                "dob": s.get("dob", ""),
                "status": s.get("status", "Active")
            }
            conn.close()
            self._send_json({"success": True, "card": card})
            return

        # Printable Fee Receipt Payload Endpoint
        elif path == "/api/fees/receipt":
            target_id = query_params.get("id", [None])[0]
            if not target_id:
                target_id = student_id
            cursor.execute("SELECT * FROM fees WHERE id = ? OR student_id = ?", (target_id, target_id))
            f_row = cursor.fetchone()
            if not f_row:
                conn.close()
                self._send_json({"success": False, "message": "Fee record not found"}, 404)
                return
            f = dict(f_row)
            if not f.get("receipt_number"):
                r_num = f"REC-2026-{1000 + f['id']}"
                cursor.execute("UPDATE fees SET receipt_number = ? WHERE id = ?", (r_num, f["id"]))
                conn.commit()
                f["receipt_number"] = r_num

            receipt = {
                "receiptNumber": f["receipt_number"],
                "collegeName": "Government Polytechnic, Awasari (Kh.)",
                "studentName": f["student_name"],
                "studentId": f["student_id"],
                "department": f["department"],
                "totalFees": f["total_fees"],
                "paidFees": f["paid_fees"],
                "pendingFees": f["pending_fees"],
                "amountPaid": f["paid_fees"],
                "paymentDate": f.get("payment_date") or time.strftime('%Y-%m-%d'),
                "paymentStatus": f["payment_status"]
            }
            conn.close()
            self._send_json({"success": True, "receipt": receipt})
            return

        # Attendance Export CSV Endpoint
        elif path == "/api/attendance/export":
            dept_f = query_params.get("department", [None])[0]
            if role == "Student":
                cursor.execute("SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC", (student_id,))
            elif role in ["HOD", "Faculty"]:
                cursor.execute("SELECT * FROM attendance WHERE department = ? ORDER BY date DESC", (user_dept,))
            else:
                if dept_f and dept_f != "All":
                    cursor.execute("SELECT * FROM attendance WHERE department = ? ORDER BY date DESC", (dept_f,))
                else:
                    cursor.execute("SELECT * FROM attendance ORDER BY date DESC")
            recs = [dict(r) for r in cursor.fetchall()]
            conn.close()

            lines = ["ID,Student ID,Student Name,Subject,Date,Status,Department\n"]
            for r in recs:
                lines.append(f'"{r["id"]}","{r["student_id"]}","{r["student_name"]}","{r["subject"]}","{r["date"]}","{r["status"]}","{r["department"]}"\n')

            self.send_response(200)
            self.send_header("Content-type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="attendance_report.csv"')
            self.end_headers()
            self.wfile.write("".join(lines).encode("utf-8"))
            return

        # Reports Data Endpoint
        elif path == "/api/reports/data":
            report_type = query_params.get("type", ["student"])[0]
            dept_f = query_params.get("department", [None])[0]
            year_f = query_params.get("year", [None])[0]
            search_q = query_params.get("search", [None])[0]

            data = []
            summary = {}

            if report_type == "student":
                sql = "SELECT * FROM students WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = ?"; p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = ?"; p.append(dept_f)
                if year_f and year_f != "All":
                    sql += " AND year = ?"; p.append(year_f)
                if search_q:
                    sql += " AND (name LIKE ? OR id LIKE ? OR roll_number LIKE ?)"
                    p.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])
                sql += " ORDER BY department, year, name"
                cursor.execute(sql, tuple(p))
                data = [dict(r) for r in cursor.fetchall()]
                summary = {"totalCount": len(data)}

            elif report_type == "faculty":
                sql = "SELECT * FROM faculty WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = ?"; p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = ?"; p.append(dept_f)
                cursor.execute(sql, tuple(p))
                data = [dict(r) for r in cursor.fetchall()]
                summary = {"totalCount": len(data)}

            elif report_type == "attendance":
                sql = "SELECT * FROM attendance WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = ?"; p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = ?"; p.append(dept_f)
                cursor.execute(sql, tuple(p))
                data = [dict(r) for r in cursor.fetchall()]
                summary = {"totalCount": len(data), "presentCount": sum(1 for d in data if d.get("status") == "Present")}

            elif report_type == "results":
                sql = "SELECT r.*, s.department, s.year FROM results r JOIN students s ON r.student_id = s.id WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND s.department = ?"; p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND s.department = ?"; p.append(dept_f)
                cursor.execute(sql, tuple(p))
                data = [dict(r) for r in cursor.fetchall()]
                summary = {"totalCount": len(data), "passCount": sum(1 for d in data if d.get("status") == "Pass")}

            elif report_type == "fees":
                sql = "SELECT * FROM fees WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = ?"; p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = ?"; p.append(dept_f)
                cursor.execute(sql, tuple(p))
                data = [dict(r) for r in cursor.fetchall()]
                summary = {
                    "totalPaid": sum(d.get("paid_fees", 0) for d in data),
                    "totalPending": sum(d.get("pending_fees", 0) for d in data)
                }

            conn.close()
            self._send_json({"success": True, "type": report_type, "summary": summary, "data": data})
            return

        # Reports CSV Export Endpoint
        elif path == "/api/reports/export":
            report_type = query_params.get("type", ["student"])[0]
            dept_f = query_params.get("department", [None])[0]

            lines = []
            filename = f"{report_type}_report.csv"

            if report_type == "student":
                sql = "SELECT * FROM students WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = ?"; p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = ?"; p.append(dept_f)
                cursor.execute(sql, tuple(p))
                rows = [dict(r) for r in cursor.fetchall()]
                lines.append("Student ID,Roll Number,Name,Department,Year,Semester,Division,Email,Mobile,Status\n")
                for r in rows:
                    lines.append(f'"{r["id"]}","{r["roll_number"]}","{r["name"]}","{r["department"]}","{r.get("year","")}","{r["semester"]}","{r["division"]}","{r["email"]}","{r["mobile"]}","{r.get("status","")}"\n')

            elif report_type == "fees":
                sql = "SELECT * FROM fees WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = ?"; p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = ?"; p.append(dept_f)
                cursor.execute(sql, tuple(p))
                rows = [dict(r) for r in cursor.fetchall()]
                lines.append("Student ID,Student Name,Department,Total Fees,Paid Fees,Pending Fees,Status,Payment Date\n")
                for r in rows:
                    lines.append(f'"{r["student_id"]}","{r["student_name"]}","{r["department"]}","{r["total_fees"]}","{r["paid_fees"]}","{r["pending_fees"]}","{r["payment_status"]}","{r.get("payment_date","")}"\n')

            else:
                lines.append("Report Export Data\n")

            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write("".join(lines).encode("utf-8"))
            return

        # HOD Student Year Summary Count Endpoint
        elif path == "/api/hod/student-summary":
            target_dept = user_dept if role in ["HOD", "Faculty", "Student"] else query_params.get("department", ["Computer Science"])[0]
            
            cursor.execute("SELECT COUNT(*) FROM students WHERE department = ? AND (year = 'First Year' OR year IS NULL OR year = '')", (target_dept,))
            cnt_first = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM students WHERE department = ? AND year = 'Second Year'", (target_dept,))
            cnt_second = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM students WHERE department = ? AND year = 'Third Year'", (target_dept,))
            cnt_third = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM students WHERE department = ?", (target_dept,))
            cnt_total = cursor.fetchone()[0]
            
            conn.close()
            self._send_json({
                "success": True,
                "department": target_dept,
                "summary": {
                    "firstYear": cnt_first,
                    "secondYear": cnt_second,
                    "thirdYear": cnt_third,
                    "total": cnt_total
                }
            })
            return

        # 2. Faculty Endpoint
        elif path == "/api/faculty":
            if role in ["Student", "HOD", "Faculty"]:
                cursor.execute("SELECT * FROM faculty WHERE department = ?", (user_dept,))
            else: # Admin
                dept_filter = query_params.get("department", [None])[0]
                if dept_filter and dept_filter != "All":
                    cursor.execute("SELECT * FROM faculty WHERE department = ?", (dept_filter,))
                else:
                    cursor.execute("SELECT * FROM faculty")
            fac = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "faculty": fac})
            return

        # 3. HODs Endpoint
        elif path == "/api/hods":
            if role in ["HOD", "Faculty", "Student"]:
                cursor.execute("SELECT * FROM hods WHERE department = ?", (user_dept,))
            else: # Admin
                dept_filter = query_params.get("department", [None])[0]
                if dept_filter and dept_filter != "All":
                    cursor.execute("SELECT * FROM hods WHERE department = ?", (dept_filter,))
                else:
                    cursor.execute("SELECT * FROM hods")
            hods = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "hods": hods})
            return

        # 4. Attendance Endpoint
        elif path == "/api/attendance":
            dept_f = query_params.get("department", [None])[0]
            year_f = query_params.get("year", [None])[0]
            sem_f = query_params.get("semester", [None])[0]
            div_f = query_params.get("division", [None])[0]
            subj_f = query_params.get("subject", [None])[0]
            date_f = query_params.get("date", [None])[0]
            status_f = query_params.get("status", [None])[0]
            search_q = query_params.get("search", [None])[0]

            sql = "SELECT a.* FROM attendance a"
            where_clauses = []
            params = []

            if role == "Student":
                where_clauses.append("a.student_id = ?")
                params.append(student_id)
            else:
                if role in ["HOD", "Faculty"] and not dept_f:
                    where_clauses.append("a.department = ?")
                    params.append(user_dept)
                elif dept_f and dept_f != "All":
                    where_clauses.append("a.department = ?")
                    params.append(dept_f)

                if year_f and year_f != "All":
                    where_clauses.append("a.year = ?")
                    params.append(year_f)

                if sem_f and sem_f != "All":
                    where_clauses.append("a.semester = ?")
                    params.append(sem_f)

                if div_f and div_f != "All":
                    where_clauses.append("a.division = ?")
                    params.append(div_f)

                if subj_f and subj_f != "All":
                    where_clauses.append("(a.subject LIKE ? OR a.subject_code LIKE ?)")
                    params.extend([f"%{subj_f}%", f"%{subj_f}%"])

                if date_f:
                    where_clauses.append("a.date = ?")
                    params.append(date_f)

                if status_f and status_f != "All":
                    where_clauses.append("a.status = ?")
                    params.append(status_f)

                if search_q:
                    where_clauses.append("(a.student_name LIKE ? OR a.student_id LIKE ? OR a.subject LIKE ?)")
                    sq = f"%{search_q.strip()}%"
                    params.extend([sq, sq, sq])

            full_sql = sql
            if where_clauses:
                full_sql += " WHERE " + " AND ".join(where_clauses)
            full_sql += " ORDER BY a.date DESC, a.student_id ASC"

            cursor.execute(full_sql, tuple(params))
            recs = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "attendance": recs})
            return

        # 5. Results Endpoint
        elif path == "/api/results":
            if role == "Student":
                cursor.execute("SELECT * FROM results WHERE student_id = ?", (student_id,))
            elif role in ["HOD", "Faculty"]:
                cursor.execute("SELECT r.* FROM results r JOIN students s ON r.student_id = s.id WHERE s.department = ?", (user_dept,))
            else: # Admin
                dept_filter = query_params.get("department", [None])[0]
                if dept_filter and dept_filter != "All":
                    cursor.execute("SELECT r.* FROM results r JOIN students s ON r.student_id = s.id WHERE s.department = ?", (dept_filter,))
                else:
                    cursor.execute("SELECT * FROM results")
            recs = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "results": recs})
            return

        elif path == "/api/results/export":
            dept_f = query_params.get("department", [None])[0]
            sem_f = query_params.get("semester", [None])[0]
            
            sql = "SELECT r.*, s.department FROM results r LEFT JOIN students s ON r.student_id = s.id WHERE 1=1"
            params = []
            if role in ["HOD", "Faculty"]:
                sql += " AND (s.department = ? OR s.department IS NULL)"
                params.append(user_dept)
            elif dept_f and dept_f != "All":
                sql += " AND s.department = ?"
                params.append(dept_f)

            if sem_f and sem_f != "All":
                sql += " AND r.semester = ?"
                params.append(sem_f)

            cursor.execute(sql, tuple(params))
            recs = cursor.fetchall()
            conn.close()

            lines = ["Student ID,Student Name,Department,Semester,Subject,Internal Marks,End Sem Marks,Total Marks,Percentage,Grade,Status,Document File\n"]
            for r in recs:
                rd = dict(r)
                lines.append(f'"{rd.get("student_id")}","{rd.get("student_name")}","{rd.get("department","")}","{rd.get("semester")}","{rd.get("subject")}","{rd.get("internal_marks")}","{rd.get("end_sem_marks")}","{rd.get("total_marks")}","{rd.get("percentage")}%","{rd.get("grade")}","{rd.get("status")}","{rd.get("document","")}"\n')

            filename = f"exam_results_{int(time.time())}.csv"
            self.send_response(200)
            self.send_header("Content-type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write("".join(lines).encode("utf-8"))
            return

        # 6. Fees Endpoint
        elif path == "/api/fees":
            if role == "Student":
                cursor.execute("SELECT * FROM fees WHERE student_id = ?", (student_id,))
            elif role in ["HOD", "Faculty"]:
                cursor.execute("SELECT * FROM fees WHERE department = ?", (user_dept,))
            else: # Admin
                dept_filter = query_params.get("department", [None])[0]
                if dept_filter and dept_filter != "All":
                    cursor.execute("SELECT * FROM fees WHERE department = ?", (dept_filter,))
                else:
                    cursor.execute("SELECT * FROM fees")
            recs = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "fees": recs})
            return

        # 7. Timetable Endpoint
        elif path == "/api/timetable":
            if role in ["Student", "Faculty", "HOD"]:
                cursor.execute("SELECT * FROM timetable WHERE department = ?", (user_dept,))
            else: # Admin
                dept_filter = query_params.get("department", [None])[0]
                if dept_filter and dept_filter != "All":
                    cursor.execute("SELECT * FROM timetable WHERE department = ?", (dept_filter,))
                else:
                    cursor.execute("SELECT * FROM timetable")
            recs = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "timetable": recs})
            return

        # 8. Notices Endpoint
        elif path == "/api/notices":
            if role == "Student":
                cursor.execute("SELECT * FROM notices WHERE department IN ('All', ?) AND target_role IN ('All', 'Student') ORDER BY rowid DESC", (user_dept,))
            elif role == "Faculty":
                cursor.execute("SELECT * FROM notices WHERE department IN ('All', ?) AND target_role IN ('All', 'Faculty') ORDER BY rowid DESC", (user_dept,))
            elif role == "HOD":
                cursor.execute("SELECT * FROM notices WHERE department IN ('All', ?) ORDER BY rowid DESC", (user_dept,))
            else: # Admin
                cursor.execute("SELECT * FROM notices ORDER BY rowid DESC")
            notices = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "notices": notices})
            return

        # 9. Subjects Endpoint
        elif path == "/api/subjects":
            if role in ["Student", "Faculty", "HOD"]:
                cursor.execute("SELECT * FROM subjects WHERE department = ?", (user_dept,))
            else: # Admin
                dept_filter = query_params.get("department", [None])[0]
                if dept_filter and dept_filter != "All":
                    cursor.execute("SELECT * FROM subjects WHERE department = ?", (dept_filter,))
                else:
                    cursor.execute("SELECT * FROM subjects")
            subjects = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "subjects": subjects})
            return

        # 10. Documents Endpoint
        elif path == "/api/documents":
            if role in ["Student", "Faculty", "HOD"]:
                cursor.execute("SELECT * FROM documents WHERE department IN ('All', ?) ORDER BY upload_date DESC", (user_dept,))
            else:
                cursor.execute("SELECT * FROM documents ORDER BY upload_date DESC")
            docs = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "documents": docs})
            return

        # 11. Contact Messages Inbox
        elif path == "/api/contact":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Access denied"}, 403)
                return
            cursor.execute("SELECT * FROM contact_messages ORDER BY rowid DESC")
            msgs = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json({"success": True, "contacts": msgs})
            return

        # 12. Executive Summary Dashboard Stats
        elif path == "/api/dashboard/stats":
            stats = {}
            if role in ["Administrator", "Admin"]:
                cursor.execute("SELECT COUNT(*) FROM students")
                stats["totalStudents"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM faculty")
                stats["totalFaculty"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM hods")
                stats["totalHODs"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM departments")
                stats["totalDepartments"] = cursor.fetchone()[0]
                cursor.execute("SELECT SUM(paid_fees), SUM(pending_fees) FROM fees")
                row = cursor.fetchone()
                stats["totalPaidFees"] = row[0] or 0
                stats["totalPendingFees"] = row[1] or 0
                cursor.execute("SELECT COUNT(*) FROM notices")
                stats["totalNotices"] = cursor.fetchone()[0]
            elif role == "HOD":
                cursor.execute("SELECT COUNT(*) FROM students WHERE department = ?", (user_dept,))
                stats["totalStudents"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM faculty WHERE department = ?", (user_dept,))
                stats["totalFaculty"] = cursor.fetchone()[0]
                cursor.execute("SELECT SUM(paid_fees), SUM(pending_fees) FROM fees WHERE department = ?", (user_dept,))
                row = cursor.fetchone()
                stats["totalPaidFees"] = row[0] or 0
                stats["totalPendingFees"] = row[1] or 0
                cursor.execute("SELECT COUNT(*) FROM notices WHERE department IN ('All', ?)", (user_dept,))
                stats["totalNotices"] = cursor.fetchone()[0]
            elif role == "Faculty":
                cursor.execute("SELECT COUNT(*) FROM students WHERE department = ?", (user_dept,))
                stats["totalStudents"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM subjects WHERE department = ?", (user_dept,))
                stats["totalSubjects"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM notices WHERE department IN ('All', ?) AND target_role IN ('All', 'Faculty')", (user_dept,))
                stats["totalNotices"] = cursor.fetchone()[0]
            elif role == "Student":
                cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ?", (student_id,))
                tot_att = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND status = 'Present'", (student_id,))
                pres_att = cursor.fetchone()[0]
                stats["attendancePercentage"] = round((pres_att / tot_att * 100), 1) if tot_att > 0 else 100.0
                cursor.execute("SELECT paid_fees, pending_fees, total_fees FROM fees WHERE student_id = ?", (student_id,))
                fee_row = cursor.fetchone()
                stats["paidFees"] = fee_row[0] if fee_row else 0
                stats["pendingFees"] = fee_row[1] if fee_row else 0
                stats["totalFees"] = fee_row[2] if fee_row else 0
                cursor.execute("SELECT AVG(percentage) FROM results WHERE student_id = ?", (student_id,))
                avg_p = cursor.fetchone()[0]
                stats["avgPercentage"] = round(avg_p, 1) if avg_p else 0.0

            conn.close()
            self._send_json({"success": True, "stats": stats})
            return

        conn.close()
        self._send_json({"error": "API endpoint not found"}, 404)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Binary / Multipart Upload Handling
        if path == "/api/upload":
            user = self.get_current_user()
            if not user:
                self._send_json({"success": False, "message": "Authentication required"}, 401)
                return
            
            content_type = self.headers.get("Content-Type", "")
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            if "boundary=" in content_type:
                # Extract boundary value safely handling quotes and parameters
                boundary_val = content_type.split("boundary=")[1].split(";")[0].strip().strip('"').strip("'")
                boundary = boundary_val.encode('utf-8')
                delimiter = b"--" + boundary
                parts = body.split(delimiter)
                for part in parts:
                    if b"filename=" in part:
                        if part.startswith(b"\r\n"):
                            part = part[2:]
                        if b"\r\n\r\n" in part:
                            headers_part, file_data = part.split(b"\r\n\r\n", 1)
                            # Remove trailing \r\n (or \r\n--) before the boundary delimiter
                            if file_data.endswith(b"\r\n"):
                                file_data = file_data[:-2]
                            elif file_data.endswith(b"\r\n--"):
                                file_data = file_data[:-4]
                            
                            headers_str = headers_part.decode('utf-8', errors='ignore')
                            fn_match = re.search(r'filename=["\']?([^"\'\r\n;]+)["\']?', headers_str)
                            raw_fn = fn_match.group(1).strip() if fn_match else f"upload_{int(time.time())}.dat"
                            safe_basename = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(raw_fn))
                            safe_fn = f"{int(time.time())}_{safe_basename}"
                            out_path = os.path.join(UPLOADS_DIR, safe_fn)
                            with open(out_path, "wb") as f:
                                f.write(file_data)
                            rel_path = f"/uploads/{safe_fn}"
                            self._send_json({"success": True, "filePath": rel_path, "fileName": safe_fn})
                            return

            filename = self.headers.get("X-File-Name", f"file_{int(time.time())}.dat")
            safe_basename = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(filename))
            safe_fn = f"{int(time.time())}_{safe_basename}"
            out_path = os.path.join(UPLOADS_DIR, safe_fn)
            with open(out_path, "wb") as f:
                f.write(body)
            self._send_json({"success": True, "filePath": f"/uploads/{safe_fn}", "fileName": safe_fn})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode("utf-8")) if post_data else {}

        # 1. Login Endpoint
        if path == "/api/login":
            username = payload.get("username", "").strip()
            password = payload.get("password", "").strip()
            role = payload.get("role", "").strip()

            if not username or not password:
                self._send_json({"success": False, "message": "Username/Email and Password are required!"}, 400)
                return

            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username))
            user = cursor.fetchone()
            
            if user and verify_password(user["password"], password):
                user_dict = dict(user)
                
                # Check role compatibility if explicit role was selected
                if role and role != "All" and user_dict.get("role") != role:
                    conn.close()
                    self._send_json({"success": False, "message": f"Role mismatch for this account! Account role is '{user_dict.get('role')}'."}, 401)
                    return

                del user_dict["password"]
                token = uuid.uuid4().hex
                SESSIONS[token] = user_dict

                cookie_hdr = f"session_token={token}; Path=/; HttpOnly; SameSite=Lax"
                self._send_json({
                    "success": True,
                    "message": "Login successful",
                    "token": token,
                    "user": user_dict
                }, headers={"Set-Cookie": cookie_hdr})
            else:
                self._send_json({"success": False, "message": "Invalid username or password credentials"}, 401)
            conn.close()
            return

        # 2. Logout Endpoint
        elif path == "/api/logout":
            token = self.get_session_token()
            if token and token in SESSIONS:
                del SESSIONS[token]
            cookie_hdr = "session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
            self._send_json({"success": True, "message": "Logged out successfully"}, headers={"Set-Cookie": cookie_hdr})
            return

        # 4. Registration Endpoint (Supports Student, Faculty, HOD, Administrator)
        elif path == "/api/register":
            role = payload.get("role", "Student").strip()
            if role == "Admin":
                role = "Administrator"
            name = payload.get("name", "").strip()
            email = payload.get("email", "").strip()
            mobile = payload.get("mobile", "").strip() or payload.get("phone", "").strip() or payload.get("contact", "").strip()
            department = payload.get("department", "Computer Science").strip()
            username = payload.get("username", "").strip()
            password = payload.get("password", "").strip()
            confirm_password = payload.get("confirmPassword", "").strip()

            if not name or not email or not username or not password:
                self._send_json({"success": False, "message": "All required fields (Name, Email, Username, Password) must be provided!"}, 400)
                return
            if password != confirm_password:
                self._send_json({"success": False, "message": "Password and Confirm Password do not match!"}, 400)
                return

            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            student_id = payload.get("studentId", "").strip() if role == "Student" else None
            faculty_id = payload.get("facultyId", "").strip() if role in ["Faculty", "HOD"] else None

            # Perform Duplicate Account Protection Check
            is_dup, dup_msg = check_duplicate_account(
                cursor,
                mobile=mobile if mobile else None,
                email=email,
                student_id=student_id if student_id else None,
                faculty_id=faculty_id if faculty_id else None,
                username=username
            )
            if is_dup:
                conn.close()
                self._send_json({"success": False, "message": dup_msg}, 400)
                return

            hashed_pass = hash_password(password)

            if role == "Student":
                if not student_id:
                    student_id = f"STU_{int(time.time() * 1000) % 100000}"
                roll_number = payload.get("rollNumber", "").strip() or f"R{int(time.time()) % 10000}"
                gender = payload.get("gender", "Male").strip()
                dob = payload.get("dob", "2000-01-01").strip()
                year = payload.get("year", "First Year").strip()
                semester = payload.get("semester", "Semester 1").strip()
                division = payload.get("division", "A").strip()
                admission_year = payload.get("admissionYear", "2026").strip()
                address = payload.get("address", "").strip()

                cursor.execute(
                    """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')""",
                    (student_id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address)
                )

            elif role == "Faculty":
                if not faculty_id:
                    faculty_id = f"FAC{int(time.time() * 1000) % 100000}"
                designation = payload.get("designation", "Assistant Professor").strip()
                experience = payload.get("experience", "1 Year").strip()

                cursor.execute(
                    """INSERT INTO faculty (id, name, department, designation, email, mobile, experience, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')""",
                    (faculty_id, name, department, designation, email, mobile, experience)
                )

            elif role == "HOD":
                if not faculty_id:
                    faculty_id = f"HOD{int(time.time() * 1000) % 100000}"
                qualification = payload.get("qualification", "Ph.D.").strip()
                experience = payload.get("experience", "10 Years").strip()
                contact = mobile

                cursor.execute(
                    """INSERT OR REPLACE INTO hods (department, name, qualification, experience, email, contact, faculty_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (department, name, qualification, experience, email, contact, faculty_id)
                )

            elif role in ["Administrator", "Admin"]:
                role = "Administrator"
                department = "Administration"

            # Create User Account in users table
            cursor.execute(
                """INSERT INTO users (username, password, role, name, email, department, student_id, faculty_id, mobile, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (username, hashed_pass, role, name, email, department, student_id, faculty_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()

            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            new_user = dict(cursor.fetchone())
            conn.close()
            del new_user["password"]

            token = uuid.uuid4().hex
            SESSIONS[token] = new_user

            cookie_hdr = f"session_token={token}; Path=/; HttpOnly; SameSite=Lax"

            self._send_json({
                "success": True,
                "username": username,
                "message": f"{role} registration completed successfully!",
                "token": token,
                "user": new_user
            }, headers={"Set-Cookie": cookie_hdr})
            return

        # 4. Public Contact Inquiry Endpoint
        elif path == "/api/contact":
            name = payload.get("name", "").strip()
            email = payload.get("email", "").strip()
            subject = payload.get("subject", "").strip()
            message = payload.get("message", "").strip()
            recipient_email = payload.get("recipientEmail", "admin@college.edu").strip()

            if not name or not email or not subject or not message:
                self._send_json({"success": False, "message": "All contact form fields are required!"}, 400)
                return

            inquiry_id = f"INQ_{int(time.time() * 1000)}"
            date_str = time.strftime('%Y-%m-%d %H:%M:%S')

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO contact_messages (id, name, email, subject, message, recipientEmail, date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (inquiry_id, name, email, subject, message, recipient_email, date_str, "Unread")
            )
            conn.commit()
            conn.close()

            self._send_json({
                "success": True,
                "message": "Contact inquiry submitted successfully!",
                "contact": { "id": inquiry_id, "name": name, "email": email, "subject": subject, "message": message, "date": date_str }
            })
            return

        # 5. Forgot Password Endpoint (Role-based recovery for Student, Faculty, HOD, Administrator)
        elif path == "/api/forgot-password":
            action = payload.get("action", "verify").strip()
            role = payload.get("role", "").strip()
            if role == "Admin":
                role = "Administrator"

            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if action == "verify":
                identifier = payload.get("identifier", "").strip()
                if not identifier:
                    conn.close()
                    self._send_json({"success": False, "message": "Username, Email, Phone, or ID is required for verification!"}, 400)
                    return

                query = "SELECT * FROM users WHERE (username = ? OR email = ? OR mobile = ? OR student_id = ? OR faculty_id = ?)"
                params = [identifier, identifier, identifier, identifier, identifier]

                if role and role != "All":
                    query += " AND role = ?"
                    params.append(role)

                cursor.execute(query, params)
                user = cursor.fetchone()

                if not user:
                    conn.close()
                    self._send_json({"success": False, "message": f"No account found matching '{identifier}' for role '{role if role else 'Any'}'. Please check your details and selected role."}, 404)
                    return

                user_dict = dict(user)
                email = user_dict.get("email") or ""
                mobile = user_dict.get("mobile") or ""

                masked_email = ""
                if "@" in email:
                    parts = email.split("@", 1)
                    masked_email = (parts[0][:2] + "****" if len(parts[0]) > 2 else parts[0] + "****") + "@" + parts[1]
                elif email:
                    masked_email = "****"

                masked_mobile = ""
                if len(mobile) >= 4:
                    masked_mobile = "******" + mobile[-4:]
                elif mobile:
                    masked_mobile = "****"

                conn.close()
                self._send_json({
                    "success": True,
                    "message": "Account verified successfully!",
                    "user": {
                        "username": user_dict.get("username"),
                        "name": user_dict.get("name"),
                        "role": user_dict.get("role"),
                        "department": user_dict.get("department", ""),
                        "maskedEmail": masked_email,
                        "maskedMobile": masked_mobile
                    }
                })
                return

            elif action == "reset":
                username = payload.get("username", "").strip()
                verification_input = payload.get("verificationInput", "").strip()
                new_password = payload.get("newPassword", "").strip()
                confirm_password = payload.get("confirmPassword", "").strip()

                if not username or not new_password:
                    conn.close()
                    self._send_json({"success": False, "message": "Username and New Password are required!"}, 400)
                    return

                if new_password != confirm_password:
                    conn.close()
                    self._send_json({"success": False, "message": "New Password and Confirm Password do not match!"}, 400)
                    return

                if len(new_password) < 6:
                    conn.close()
                    self._send_json({"success": False, "message": "Password must be at least 6 characters long!"}, 400)
                    return

                cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                user = cursor.fetchone()
                if not user:
                    conn.close()
                    self._send_json({"success": False, "message": "User account not found!"}, 404)
                    return

                user_dict = dict(user)

                if role and role != "All" and user_dict.get("role") != role:
                    conn.close()
                    self._send_json({"success": False, "message": f"Account role mismatch. Account role is '{user_dict.get('role')}'."}, 400)
                    return

                user_email = (user_dict.get("email") or "").strip().lower()
                user_mobile = (user_dict.get("mobile") or "").strip()
                user_uname = (user_dict.get("username") or "").strip().lower()
                ver_clean = verification_input.strip().lower()

                if verification_input:
                    if ver_clean != user_email and ver_clean != user_mobile and ver_clean != user_uname:
                        conn.close()
                        self._send_json({"success": False, "message": "Security verification failed! Provided email/phone does not match the registered account details."}, 400)
                        return

                hashed_pass = hash_password(new_password)
                cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_pass, user_dict["id"]))
                conn.commit()
                conn.close()

                self._send_json({
                    "success": True,
                    "message": f"Password for account '{username}' has been successfully reset! You can now log in with your new password."
                })
                return

            conn.close()
            self._send_json({"success": False, "message": "Invalid forgot password action!"}, 400)
            return

        # Authenticated Endpoints Check
        user = self.get_current_user()
        if not user:
            self._send_json({"success": False, "message": "Authentication required"}, 401)
            return

        role = user["role"]
        user_dept = user.get("department", "")

        conn = get_db_connection()
        cursor = conn.cursor()

        # 5. Departments CRUD
        if path == "/api/departments":
            if role not in ["Administrator", "Admin"]:
                conn.close()
                self._send_json({"success": False, "message": "Only System Administrator can create or edit departments"}, 403)
                return
            code = payload.get("code", "").strip()
            name = payload.get("name", "").strip()
            desc = payload.get("description", "").strip()
            dept_id = payload.get("id")

            if dept_id:
                cursor.execute("UPDATE departments SET code = ?, name = ?, description = ? WHERE id = ?", (code, name, desc, dept_id))
            else:
                cursor.execute("INSERT OR REPLACE INTO departments (code, name, description) VALUES (?, ?, ?)", (code, name, desc))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Department saved successfully!"})
            return

        # 6. Students CRUD
        elif path == "/api/students":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return

            s_id = payload.get("id") or payload.get("studentId")
            roll_number = payload.get("rollNumber") or payload.get("roll_number")
            dept = payload.get("department") or (user_dept if role == "HOD" else "Computer Engineering")
            mobile = payload.get("mobile", "").strip() or payload.get("phone", "").strip()
            email = payload.get("email", "").strip()
            name = payload.get("name", "").strip()
            is_edit = payload.get("is_edit", False)

            if not s_id or not roll_number or not name:
                conn.close()
                self._send_json({"success": False, "message": "Student ID, Roll Number, and Name are required!"}, 400)
                return

            # Check duplicates if new student creation
            if not is_edit:
                cursor.execute("SELECT id FROM students WHERE id = ?", (s_id,))
                if cursor.fetchone():
                    conn.close()
                    self._send_json({"success": False, "message": f"Duplicate Error: Student ID '{s_id}' already exists!"}, 400)
                    return

                cursor.execute("SELECT id FROM students WHERE roll_number = ? AND department = ?", (roll_number, dept))
                if cursor.fetchone():
                    conn.close()
                    self._send_json({"success": False, "message": f"Duplicate Error: Roll Number '{roll_number}' already exists in department '{dept}'!"}, 400)
                    return

            cursor.execute(
                """INSERT OR REPLACE INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status, photo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    s_id,
                    roll_number,
                    name,
                    email if email else f"{s_id.lower()}@college.edu",
                    mobile if mobile else "9876543210",
                    payload.get("gender", "Male"),
                    payload.get("dob", "2000-01-01"),
                    dept,
                    payload.get("year", "First Year"),
                    payload.get("semester", "Semester 1"),
                    payload.get("division", "A"),
                    payload.get("admissionYear", "2026"),
                    payload.get("address", ""),
                    payload.get("status", "Active"),
                    payload.get("photo", "")
                )
            )

            cursor.execute("SELECT id FROM users WHERE student_id = ? OR email = ?", (s_id, email))
            if not cursor.fetchone():
                username = payload.get("username") or (email.split("@")[0] if email else f"student_{s_id}")
                plain_pass = payload.get("password", "student123")
                hashed = hash_password(plain_pass)
                cursor.execute(
                    "INSERT INTO users (username, password, role, name, email, department, student_id, mobile, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, hashed, "Student", name, email if email else f"{s_id.lower()}@college.edu", dept, s_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
                )

            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Student record saved successfully!", "id": s_id})
            return

        # Bulk Student Add Endpoint
        elif path == "/api/students/bulk":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return

            default_dept = payload.get("department") or (user_dept if role == "HOD" else "Computer Engineering")
            default_year = payload.get("year", "First Year")
            default_sem = payload.get("semester", "Semester 1")
            default_div = payload.get("division", "A")
            students_list = payload.get("students", [])

            if not isinstance(students_list, list) or len(students_list) == 0:
                conn.close()
                self._send_json({"success": False, "message": "No valid student list provided for bulk insertion!"}, 400)
                return

            inserted_cnt = 0
            skipped_cnt = 0

            for s in students_list:
                s_id = s.get("id") or s.get("studentId")
                r_num = s.get("roll_number") or s.get("rollNumber")
                name = s.get("name")
                if not s_id or not r_num or not name:
                    continue

                dept = s.get("department") or default_dept
                year = s.get("year") or default_year
                sem = s.get("semester") or default_sem
                div = s.get("division") or default_div
                email = s.get("email") or f"{s_id.lower()}@college.edu"
                mobile = s.get("mobile") or "9876543210"

                # Check duplicate Student ID or Roll Number in dept
                cursor.execute("SELECT id FROM students WHERE id = ? OR (roll_number = ? AND department = ?)", (s_id, r_num, dept))
                if cursor.fetchone():
                    skipped_cnt += 1
                    continue

                cursor.execute(
                    """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')""",
                    (
                        s_id, r_num, name, email, mobile,
                        s.get("gender", "Male"), s.get("dob", "2005-01-01"),
                        dept, year, sem, div, s.get("admissionYear", "2026"), s.get("address", "Awasari")
                    )
                )
                
                # Insert default user record
                username = s.get("username") or email.split("@")[0]
                hashed = hash_password("student123")
                cursor.execute(
                    "INSERT OR IGNORE INTO users (username, password, role, name, email, department, student_id, mobile, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, hashed, "Student", name, email, dept, s_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
                )

                inserted_cnt += 1

            conn.commit()
            conn.close()
            self._send_json({
                "success": True,
                "message": f"Bulk insertion complete! Added {inserted_cnt} new students. Skipped {skipped_cnt} existing duplicates.",
                "inserted": inserted_cnt,
                "skipped": skipped_cnt
            })
            return

        # Assign Students to Faculty Endpoint
        elif path == "/api/faculty-students/assign":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return

            fac_id = payload.get("faculty_id") or payload.get("facultyId")
            stu_ids = payload.get("student_ids") or payload.get("studentIds") or []

            if not fac_id or not isinstance(stu_ids, list) or len(stu_ids) == 0:
                conn.close()
                self._send_json({"success": False, "message": "Faculty ID and student ID list are required!"}, 400)
                return

            assigned_cnt = 0
            for sid in stu_ids:
                cursor.execute("INSERT OR IGNORE INTO faculty_students (faculty_id, student_id) VALUES (?, ?)", (fac_id, sid))
                assigned_cnt += 1

            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": f"Successfully assigned {assigned_cnt} students to faculty member '{fac_id}'."})
            return

        # Remove Student Assignment Endpoint
        elif path == "/api/faculty-students/remove":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return

            fac_id = payload.get("faculty_id") or payload.get("facultyId")
            stu_id = payload.get("student_id") or payload.get("studentId")
            stu_ids = payload.get("student_ids") or payload.get("studentIds") or ([stu_id] if stu_id else [])

            if not fac_id or not stu_ids:
                conn.close()
                self._send_json({"success": False, "message": "Faculty ID and student ID are required!"}, 400)
                return

            for sid in stu_ids:
                cursor.execute("DELETE FROM faculty_students WHERE faculty_id = ? AND student_id = ?", (fac_id, sid))

            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Student assignment removed successfully!"})
            return

        # Import Students from Excel (.xlsx) Endpoint
        elif path == "/api/students/import-excel":
            if role == "Student":
                conn.close()
                self._send_json({"success": False, "message": "Students are not permitted to import data"}, 403)
                return

            file_b64 = payload.get("file_base64") or payload.get("file")
            if not file_b64:
                conn.close()
                self._send_json({"success": False, "message": "No Excel file data provided"}, 400)
                return

            if "," in file_b64:
                file_b64 = file_b64.split(",", 1)[1]

            try:
                raw_bytes = base64.b64decode(file_b64)
                rows = parse_xlsx_bytes(raw_bytes)
            except Exception as ex:
                conn.close()
                self._send_json({"success": False, "message": f"Failed to parse Excel file: {ex}"}, 400)
                return

            if not rows or len(rows) <= 1:
                conn.close()
                self._send_json({"success": False, "message": "Excel file contains no data rows"}, 400)
                return

            header = [str(h).lower().replace(' ', '').replace('_', '') for h in rows[0]]
            data_rows = rows[1:]

            def get_col_idx(candidates, default_idx):
                for candidate in candidates:
                    for i, h in enumerate(header):
                        if candidate in h:
                            return i
                return default_idx if default_idx < len(header) else -1

            idx_id = get_col_idx(["studentid", "id"], 0)
            idx_roll = get_col_idx(["rollnumber", "rollno", "roll"], 1)
            idx_name = get_col_idx(["studentname", "fullname", "name"], 2)
            idx_email = get_col_idx(["email"], 3)
            idx_mobile = get_col_idx(["mobilenumber", "mobile", "phone", "contact"], 4)
            idx_gender = get_col_idx(["gender"], 5)
            idx_dob = get_col_idx(["dob", "dateofbirth", "birth"], 6)
            idx_dept = get_col_idx(["department", "dept"], 7)
            idx_year = get_col_idx(["year"], 8)
            idx_sem = get_col_idx(["semester", "sem"], 9)
            idx_div = get_col_idx(["division", "div"], 10)
            idx_adm_year = get_col_idx(["admissionyear", "admission"], 11)
            idx_address = get_col_idx(["address"], 12)
            idx_status = get_col_idx(["status"], 13)

            seen_ids = set()
            seen_rolls = set()
            added_cnt = 0
            dup_cnt = 0
            fail_cnt = 0
            errors = []

            for r_num, r in enumerate(data_rows, start=2):
                def get_val(idx, default=""):
                    return r[idx].strip() if idx >= 0 and idx < len(r) else default

                stu_id = get_val(idx_id)
                roll_no = get_val(idx_roll)
                name = get_val(idx_name)
                email = get_val(idx_email)
                mobile = get_val(idx_mobile)
                gender = get_val(idx_gender, "Male")
                dob = get_val(idx_dob, "2005-01-01")
                dept = get_val(idx_dept, user_dept if role in ["HOD", "Faculty"] else "Computer Engineering")
                year = get_val(idx_year, "First Year")
                sem = get_val(idx_sem, "Semester 1")
                div = get_val(idx_div, "A")
                adm_year = get_val(idx_adm_year, "2026")
                address = get_val(idx_address, "Awasari")
                status_val = get_val(idx_status, "Active")

                # Validate Role Scoping
                if role in ["HOD", "Faculty"] and dept != user_dept:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": f"Unauthorized department '{dept}'. Restricted to '{user_dept}'."})
                    continue

                if not stu_id or not roll_no or not name:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": "Missing required field (Student ID, Roll Number, or Student Name)"})
                    continue

                # Internal Excel Duplicates
                if stu_id in seen_ids:
                    dup_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Duplicate Student ID '{stu_id}' inside Excel file"})
                    continue

                if (roll_no, dept) in seen_rolls:
                    dup_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Duplicate Roll Number '{roll_no}' in department '{dept}' inside Excel file"})
                    continue

                # DB Duplicates
                cursor.execute("SELECT id FROM students WHERE id = ?", (stu_id,))
                if cursor.fetchone():
                    dup_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Student ID '{stu_id}' already exists in database"})
                    continue

                cursor.execute("SELECT id FROM students WHERE roll_number = ? AND department = ?", (roll_no, dept))
                if cursor.fetchone():
                    dup_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Roll Number '{roll_no}' already exists in department '{dept}' in database"})
                    continue

                seen_ids.add(stu_id)
                seen_rolls.add((roll_no, dept))

                if not email:
                    email = f"{stu_id.lower()}@college.edu"
                if not mobile:
                    mobile = "9876543210"

                cursor.execute(
                    """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (stu_id, roll_no, name, email, mobile, gender, dob, dept, year, sem, div, adm_year, address, status_val)
                )

                username = email.split("@")[0]
                hashed = hash_password("student123")
                cursor.execute(
                    "INSERT OR IGNORE INTO users (username, password, role, name, email, department, student_id, mobile, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, hashed, "Student", name, email, dept, stu_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
                )

                added_cnt += 1

            conn.commit()
            conn.close()
            self._send_json({
                "success": True,
                "totalRecords": len(data_rows),
                "addedCount": added_cnt,
                "duplicateCount": dup_cnt,
                "failedCount": fail_cnt,
                "errors": errors
            })
            return

        # Import Attendance from Excel (.xlsx) Endpoint
        elif path == "/api/attendance/import-excel":
            if role == "Student":
                conn.close()
                self._send_json({"success": False, "message": "Students are not permitted to import attendance"}, 403)
                return

            file_b64 = payload.get("file_base64") or payload.get("file")
            if not file_b64:
                conn.close()
                self._send_json({"success": False, "message": "No Excel file data provided"}, 400)
                return

            if "," in file_b64:
                file_b64 = file_b64.split(",", 1)[1]

            try:
                raw_bytes = base64.b64decode(file_b64)
                rows = parse_xlsx_bytes(raw_bytes)
            except Exception as ex:
                conn.close()
                self._send_json({"success": False, "message": f"Failed to parse Excel file: {ex}"}, 400)
                return

            if not rows or len(rows) <= 1:
                conn.close()
                self._send_json({"success": False, "message": "Excel file contains no data rows"}, 400)
                return

            header = [str(h).lower().replace(' ', '').replace('_', '') for h in rows[0]]
            data_rows = rows[1:]

            def get_col_idx(candidates, default_idx):
                for candidate in candidates:
                    for i, h in enumerate(header):
                        if candidate in h:
                            return i
                return default_idx if default_idx < len(header) else -1

            idx_id = get_col_idx(["studentid", "id"], 0)
            idx_name = get_col_idx(["studentname", "fullname", "name"], 1)
            idx_dept = get_col_idx(["department", "dept"], 2)
            idx_year = get_col_idx(["year"], 3)
            idx_sem = get_col_idx(["semester", "sem"], 4)
            idx_div = get_col_idx(["division", "div"], 5)
            idx_subject = get_col_idx(["subjectname", "subject"], 6)
            idx_code = get_col_idx(["subjectcode", "code"], 7)
            idx_date = get_col_idx(["date"], 8)
            idx_status = get_col_idx(["attendancestatus", "status"], 9)

            seen_att = set()
            added_cnt = 0
            dup_cnt = 0
            fail_cnt = 0
            errors = []

            for r_num, r in enumerate(data_rows, start=2):
                def get_val(idx, default=""):
                    return r[idx].strip() if idx >= 0 and idx < len(r) else default

                stu_id = get_val(idx_id)
                name = get_val(idx_name)
                dept = get_val(idx_dept)
                year = get_val(idx_year, "First Year")
                sem = get_val(idx_sem, "Semester 1")
                div = get_val(idx_div, "A")
                subject = get_val(idx_subject)
                subj_code = get_val(idx_code)
                att_date = get_val(idx_date)
                att_status_raw = get_val(idx_status, "Present")

                if not stu_id or not subject or not att_date:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": "Missing required field (Student ID, Subject, or Date)"})
                    continue

                att_status = att_status_raw.capitalize()
                if att_status not in ["Present", "Absent", "Late"]:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": name or "N/A", "reason": f"Invalid Attendance Status '{att_status_raw}'. Must be Present or Absent."})
                    continue

                # Verify Student ID exists in DB
                cursor.execute("SELECT id, name, department, year, semester, division FROM students WHERE id = ?", (stu_id,))
                stu_row = cursor.fetchone()
                if not stu_row:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": name or "N/A", "reason": f"Student ID '{stu_id}' does not exist in student database"})
                    continue

                stu_db = dict(stu_row)
                target_dept = dept if dept else stu_db["department"]
                target_name = name if name else stu_db["name"]

                # Validate Role Scoping
                if role in ["HOD", "Faculty"] and target_dept != user_dept:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Unauthorized department '{target_dept}'. Restricted to '{user_dept}'."})
                    continue

                # Check internal Excel duplicate
                att_key = (stu_id, subject, att_date)
                if att_key in seen_att:
                    dup_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Duplicate attendance for '{stu_id}', subject '{subject}' on '{att_date}' inside Excel"})
                    continue

                # Check DB duplicate
                cursor.execute("SELECT id FROM attendance WHERE student_id = ? AND subject = ? AND date = ?", (stu_id, subject, att_date))
                if cursor.fetchone():
                    dup_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Attendance record already exists for '{stu_id}', subject '{subject}' on '{att_date}' in database"})
                    continue

                seen_att.add(att_key)

                cursor.execute(
                    """INSERT INTO attendance (student_id, student_name, subject, date, status, faculty_id, department, year, semester, division, subject_code)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (stu_id, target_name, subject, att_date, att_status, user.get("faculty_id", ""), target_dept, year, sem, div, subj_code)
                )
                added_cnt += 1

            conn.commit()
            conn.close()
            self._send_json({
                "success": True,
                "totalRecords": len(data_rows),
                "addedCount": added_cnt,
                "duplicateCount": dup_cnt,
                "failedCount": fail_cnt,
                "errors": errors
            })
            return

        # Export Error Log CSV/Excel Endpoint
        elif path == "/api/excel/export-errors":
            errors = payload.get("errors", [])
            lines = ["Excel Row Number,Student ID,Student Name,Failure Reason\n"]
            for err in errors:
                lines.append(f'"{err.get("row")}","{err.get("student_id")}","{err.get("name")}","{err.get("reason")}"\n')
            
            conn.close()
            self.send_response(200)
            self.send_header("Content-type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="excel_import_error_report.csv"')
            self.end_headers()
            self.wfile.write("".join(lines).encode("utf-8"))
            return

        # Import Exam Results from Excel (.xlsx) Endpoint
        elif path == "/api/results/import-excel":
            if role == "Student":
                conn.close()
                self._send_json({"success": False, "message": "Students are not permitted to import exam results"}, 403)
                return

            file_b64 = payload.get("file_base64") or payload.get("file")
            if not file_b64:
                conn.close()
                self._send_json({"success": False, "message": "No Excel file data provided"}, 400)
                return

            if "," in file_b64:
                file_b64 = file_b64.split(",", 1)[1]

            try:
                raw_bytes = base64.b64decode(file_b64)
                rows = parse_xlsx_bytes(raw_bytes)
            except Exception as ex:
                conn.close()
                self._send_json({"success": False, "message": f"Failed to parse Excel file: {ex}"}, 400)
                return

            if not rows or len(rows) <= 1:
                conn.close()
                self._send_json({"success": False, "message": "Excel file contains no data rows"}, 400)
                return

            header = [str(h).lower().replace(' ', '').replace('_', '') for h in rows[0]]
            data_rows = rows[1:]

            def get_col_idx(candidates, default_idx):
                for candidate in candidates:
                    for i, h in enumerate(header):
                        if candidate in h:
                            return i
                return default_idx if default_idx < len(header) else -1

            idx_id = get_col_idx(["studentid", "id"], 0)
            idx_name = get_col_idx(["studentname", "fullname", "name"], 1)
            idx_dept = get_col_idx(["department", "dept"], 2)
            idx_sem = get_col_idx(["semester", "sem"], 3)
            idx_subject = get_col_idx(["subjectname", "subject"], 4)
            idx_internal = get_col_idx(["internalmarks", "internal"], 5)
            idx_endsem = get_col_idx(["endsemmarks", "endsem", "external"], 6)

            seen_results = set()
            added_cnt = 0
            dup_cnt = 0
            fail_cnt = 0
            errors = []

            for r_num, r in enumerate(data_rows, start=2):
                def get_val(idx, default=""):
                    return r[idx].strip() if idx >= 0 and idx < len(r) else default

                stu_id = get_val(idx_id)
                name = get_val(idx_name)
                dept = get_val(idx_dept)
                sem = get_val(idx_sem, "Semester 1")
                subject = get_val(idx_subject)
                internal_str = get_val(idx_internal, "0")
                end_sem_str = get_val(idx_endsem, "0")

                if not stu_id or not subject:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": "Missing required field (Student ID or Subject)"})
                    continue

                try:
                    internal = float(internal_str)
                    end_sem = float(end_sem_str)
                except ValueError:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": name or "N/A", "reason": f"Invalid marks values: internal='{internal_str}', end_sem='{end_sem_str}'"})
                    continue

                cursor.execute("SELECT id, name, department FROM students WHERE id = ?", (stu_id,))
                stu_row = cursor.fetchone()
                target_name = name if name else (stu_row["name"] if stu_row else "Student")
                target_dept = dept if dept else (stu_row["department"] if stu_row else user_dept)

                if role in ["HOD", "Faculty"] and target_dept != user_dept:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Unauthorized department '{target_dept}'. Restricted to '{user_dept}'."})
                    continue

                res_key = (stu_id, subject, sem)
                if res_key in seen_results:
                    dup_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Duplicate result for '{stu_id}', subject '{subject}' on '{sem}' inside Excel"})
                    continue

                seen_results.add(res_key)

                total = internal + end_sem
                percentage = round((total / 100.0) * 100.0, 1)
                grade = "A+" if percentage >= 85 else "A" if percentage >= 75 else "B" if percentage >= 60 else "C" if percentage >= 50 else "F"
                res_status = "Pass" if percentage >= 40 and end_sem >= 28 else "Fail"

                cursor.execute("SELECT id FROM results WHERE student_id = ? AND subject = ? AND semester = ?", (stu_id, subject, sem))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        """UPDATE results SET student_name=?, internal_marks=?, end_sem_marks=?, total_marks=?, percentage=?, grade=?, status=?
                           WHERE id=?""",
                        (target_name, internal, end_sem, total, percentage, grade, res_status, existing["id"])
                    )
                    dup_cnt += 1
                else:
                    cursor.execute(
                        """INSERT INTO results (student_id, student_name, subject, semester, internal_marks, end_sem_marks, total_marks, percentage, grade, status, document)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')""",
                        (stu_id, target_name, subject, sem, internal, end_sem, total, percentage, grade, res_status)
                    )
                    added_cnt += 1

            conn.commit()
            conn.close()
            self._send_json({
                "success": True,
                "totalRecords": len(data_rows),
                "addedCount": added_cnt,
                "duplicateCount": dup_cnt,
                "failedCount": fail_cnt,
                "errors": errors
            })
            return

        # Upload Marksheet Document / Photo Endpoint (.pdf, .doc, .docx, .png, .jpg, .jpeg)
        elif path == "/api/results/upload-document":
            if role == "Student":
                conn.close()
                self._send_json({"success": False, "message": "Students cannot upload documents"}, 403)
                return

            res_id = payload.get("result_id") or payload.get("id")
            file_b64 = payload.get("file_base64") or payload.get("file")
            file_name = payload.get("file_name", "marksheet.png")

            if not res_id or not file_b64:
                conn.close()
                self._send_json({"success": False, "message": "Result ID and file data are required"}, 400)
                return

            if "," in file_b64:
                file_b64 = file_b64.split(",", 1)[1]

            try:
                raw_bytes = base64.b64decode(file_b64)
                ext = os.path.splitext(file_name)[1].lower() or ".png"
                safe_filename = f"marksheet_{res_id}_{int(time.time())}{ext}"
                target_filepath = os.path.join(UPLOADS_DIR, safe_filename)
                with open(target_filepath, "wb") as f:
                    f.write(raw_bytes)
                
                doc_url = f"/uploads/{safe_filename}"
                cursor.execute("UPDATE results SET document = ? WHERE id = ?", (doc_url, res_id))
                conn.commit()
                conn.close()
                self._send_json({"success": True, "message": "Marksheet document/photo uploaded successfully!", "document": doc_url})
                return
            except Exception as ex:
                conn.close()
                self._send_json({"success": False, "message": f"Failed to save uploaded file: {ex}"}, 500)
                return

        # 7. Faculty CRUD
        elif path == "/api/faculty":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            f_id = payload.get("id") or payload.get("facultyId") or f"FAC{int(time.time()) % 100000}"
            dept = user_dept if role == "HOD" else payload.get("department", "Computer Science")
            mobile = payload.get("mobile", "").strip() or payload.get("phone", "").strip()
            email = payload.get("email", "").strip()
            name = payload.get("name", "").strip()

            cursor.execute(
                """INSERT OR REPLACE INTO faculty (id, name, department, designation, email, mobile, experience, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f_id,
                    name,
                    dept,
                    payload.get("designation", "Assistant Professor"),
                    email,
                    mobile,
                    payload.get("experience", "1 Year"),
                    payload.get("status", "Active")
                )
            )
            cursor.execute("SELECT id FROM users WHERE faculty_id = ? OR email = ?", (f_id, email))
            if not cursor.fetchone():
                username = payload.get("username") or (email.split("@")[0] if email else f"faculty_{f_id}")
                plain_pass = payload.get("password", "faculty123")
                hashed = hash_password(plain_pass)
                cursor.execute(
                    "INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, hashed, "Faculty", name, email, dept, f_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
                )

            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Faculty record saved successfully!", "id": f_id})
            return

        # 8. HODs CRUD
        elif path == "/api/hods":
            if role not in ["Administrator", "Admin"]:
                conn.close()
                self._send_json({"success": False, "message": "Only System Administrator can manage HODs"}, 403)
                return
            dept = payload.get("department")
            f_id = payload.get("faculty_id") or f"HOD{int(time.time()) % 100000}"
            email = payload.get("email", "").strip()
            contact = payload.get("contact", "").strip() or payload.get("mobile", "").strip()
            name = payload.get("name", "").strip()

            cursor.execute(
                """INSERT OR REPLACE INTO hods (department, name, qualification, experience, email, contact, faculty_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (dept, name, payload.get("qualification"), payload.get("experience"), email, contact, f_id)
            )
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if not cursor.fetchone():
                username = payload.get("username") or (email.split("@")[0] if email else f"hod_{dept.lower().replace(' ', '_')}")
                plain_pass = payload.get("password", "hod123")
                hashed = hash_password(plain_pass)
                cursor.execute(
                    "INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, hashed, "HOD", name, email, dept, f_id, contact, time.strftime('%Y-%m-%d %H:%M:%S'))
                )

            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "HOD record saved successfully!"})
            return

        # 9. Attendance CRUD
        elif path == "/api/attendance":
            if role not in ["Administrator", "Admin", "HOD", "Faculty"]:
                conn.close()
                self._send_json({"success": False, "message": "Students cannot modify attendance records"}, 403)
                return
            att_id = payload.get("id")
            s_id = payload.get("studentId") or payload.get("student_id")
            s_name = payload.get("studentName") or payload.get("student_name", "Student")
            dept = user_dept if role in ["HOD", "Faculty"] else payload.get("department", "Computer Science")
            subject = payload.get("subject", "General")
            att_date = payload.get("date", time.strftime('%Y-%m-%d'))
            status = payload.get("status", "Present")
            f_id = user.get("faculty_id") or user.get("username")

            if att_id:
                cursor.execute(
                    "UPDATE attendance SET student_id=?, student_name=?, subject=?, date=?, status=?, department=? WHERE id=?",
                    (s_id, s_name, subject, att_date, status, dept, att_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO attendance (student_id, student_name, subject, date, status, faculty_id, department) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (s_id, s_name, subject, att_date, status, f_id, dept)
                )
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Attendance record saved successfully!"})
            return

        # 10. Results CRUD
        elif path == "/api/results":
            if role not in ["Administrator", "Admin", "HOD", "Faculty"]:
                conn.close()
                self._send_json({"success": False, "message": "Students cannot enter exam results"}, 403)
                return
            res_id = payload.get("id")
            s_id = payload.get("studentId") or payload.get("student_id")
            s_name = payload.get("studentName") or payload.get("student_name", "Student")
            subject = payload.get("subject")
            semester = payload.get("semester", "Semester 1")
            internal = float(payload.get("internalMarks", 0))
            end_sem = float(payload.get("endSemMarks", 0))
            total = internal + end_sem
            percentage = round((total / 100.0) * 100, 1)
            grade = "A+" if percentage >= 90 else "A" if percentage >= 80 else "B" if percentage >= 70 else "C" if percentage >= 60 else "D" if percentage >= 40 else "F"
            res_status = "Pass" if percentage >= 40 else "Fail"

            if res_id:
                cursor.execute(
                    """UPDATE results SET student_id=?, student_name=?, subject=?, semester=?, internal_marks=?, end_sem_marks=?, total_marks=?, percentage=?, grade=?, status=?
                       WHERE id=?""",
                    (s_id, s_name, subject, semester, internal, end_sem, total, percentage, grade, res_status, res_id)
                )
            else:
                cursor.execute(
                    """INSERT INTO results (student_id, student_name, subject, semester, internal_marks, end_sem_marks, total_marks, percentage, grade, status, document)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')""",
                    (s_id, s_name, subject, semester, internal, end_sem, total, percentage, grade, res_status)
                )
                res_id = cursor.lastrowid
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Result record saved successfully!", "id": res_id})
            return

        # 11. Fees CRUD / Pay Fee
        elif path == "/api/fees":
            fee_id = payload.get("id")
            
            if role == "Student":
                s_id = user.get("student_id")
                pay_amount = float(payload.get("payAmount", 0))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM fees WHERE student_id = ?", (s_id,))
                fee_row = cursor.fetchone()
                if fee_row:
                    fee_dict = dict(fee_row)
                    curr_paid = float(fee_dict["paid_fees"])
                    total_f = float(fee_dict["total_fees"])
                    new_paid = min(total_f, curr_paid + pay_amount)
                    new_pending = max(0.0, total_f - new_paid)
                    pay_status = "Paid" if new_pending <= 0 else "Partial"
                    cursor.execute(
                        "UPDATE fees SET paid_fees=?, pending_fees=?, payment_date=?, payment_status=? WHERE student_id=?",
                        (new_paid, new_pending, time.strftime('%Y-%m-%d'), pay_status, s_id)
                    )
                    conn.commit()
                    conn.close()
                    self._send_json({"success": True, "message": f"Payment of ₹{pay_amount} processed successfully!"})
                    return
                else:
                    conn.close()
                    self._send_json({"success": False, "message": "No fee record assigned for student"}, 404)
                    return

            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return

            s_id = payload.get("studentId") or payload.get("student_id")
            s_name = payload.get("studentName", "Student")
            dept = user_dept if role == "HOD" else payload.get("department", "Computer Science")
            total_fees = float(payload.get("totalFees", 0))
            paid_fees = float(payload.get("paidFees", 0))
            pending_fees = max(0.0, total_fees - paid_fees)
            pay_status = "Paid" if pending_fees <= 0 else "Partial" if paid_fees > 0 else "Pending"
            p_date = payload.get("paymentDate", time.strftime('%Y-%m-%d'))

            if fee_id:
                cursor.execute(
                    "UPDATE fees SET student_id=?, student_name=?, department=?, total_fees=?, paid_fees=?, pending_fees=?, payment_date=?, payment_status=? WHERE id=?",
                    (s_id, s_name, dept, total_fees, paid_fees, pending_fees, p_date, pay_status, fee_id)
                )
            else:
                cursor.execute("SELECT id FROM fees WHERE student_id = ?", (s_id,))
                if cursor.fetchone():
                    cursor.execute(
                        "UPDATE fees SET total_fees=?, paid_fees=?, pending_fees=?, payment_date=?, payment_status=? WHERE student_id=?",
                        (total_fees, paid_fees, pending_fees, p_date, pay_status, s_id)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO fees (student_id, student_name, department, total_fees, paid_fees, pending_fees, payment_date, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (s_id, s_name, dept, total_fees, paid_fees, pending_fees, p_date, pay_status)
                    )
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Fee record saved successfully!"})
            return

        # 12. Timetable CRUD
        elif path == "/api/timetable":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            tt_id = payload.get("id")
            dept = user_dept if role == "HOD" else payload.get("department", "Computer Science")
            sem = payload.get("semester", "Semester 1")
            div = payload.get("division", "A")
            day = payload.get("day", "Monday")
            tt_time = payload.get("time", "10:00 AM - 11:00 AM")
            subject = payload.get("subject", "")
            faculty = payload.get("faculty", "")
            room = payload.get("room", "Lab 1")

            if tt_id:
                cursor.execute(
                    "UPDATE timetable SET department=?, semester=?, division=?, day=?, time=?, subject=?, faculty=?, room=? WHERE id=?",
                    (dept, sem, div, day, tt_time, subject, faculty, room, tt_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO timetable (department, semester, division, day, time, subject, faculty, room) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (dept, sem, div, day, tt_time, subject, faculty, room)
                )
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Timetable entry saved successfully!"})
            return

        # 13. Notices CRUD
        elif path == "/api/notices":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Only Admin and HOD can publish notices"}, 403)
                return

            n_id = payload.get("id") or f"NOT{int(time.time()) % 10000}"
            title = payload.get("title")
            n_date = payload.get("date", time.strftime('%Y-%m-%d'))
            dept = user_dept if role == "HOD" else payload.get("department", "All")
            target_role = payload.get("targetRole", "All")
            priority = payload.get("priority", "Medium")
            desc = payload.get("description", "")
            attachment = payload.get("attachment", "")
            author = user.get("name", "Administration")

            cursor.execute(
                """INSERT OR REPLACE INTO notices (id, title, date, department, target_role, priority, description, attachment, author)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (n_id, title, n_date, dept, target_role, priority, desc, attachment, author)
            )
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Notice published successfully!", "id": n_id})
            return

        # 14. Profile Update
        elif path == "/api/profile":
            name = payload.get("name")
            email = payload.get("email")
            new_pass = payload.get("password")

            if new_pass:
                hashed_pass = hash_password(new_pass)
                cursor.execute("UPDATE users SET name = ?, email = ?, password = ? WHERE id = ?", (name, email, hashed_pass, user["id"]))
            else:
                cursor.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (name, email, user["id"]))
            
            user["name"] = name
            user["email"] = email

            if user.get("student_id"):
                cursor.execute("UPDATE students SET name = ?, email = ? WHERE id = ?", (name, email, user["student_id"]))
            if user.get("faculty_id"):
                cursor.execute("UPDATE faculty SET name = ?, email = ? WHERE id = ?", (name, email, user["faculty_id"]))

            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Profile updated successfully!", "user": user})
            return

        # 15. Documents CRUD
        elif path == "/api/documents":
            if role not in ["Administrator", "Admin", "HOD", "Faculty"]:
                conn.close()
                self._send_json({"success": False, "message": "Only Admin, HOD, and Faculty can upload documents"}, 403)
                return

            doc_id = payload.get("id") or f"DOC_{int(time.time() * 1000)}"
            title = payload.get("title", "Untitled Document")
            category = payload.get("category", "Notes")
            dept = user_dept if role in ["HOD", "Faculty"] else payload.get("department", "All")
            semester = payload.get("semester", "All")
            subject = payload.get("subject", "All")
            file_path = payload.get("filePath") or payload.get("file_path", "")
            uploaded_by = user.get("name", "Staff")
            upload_date = time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                """INSERT OR REPLACE INTO documents (id, title, category, department, semester, subject, file_path, uploaded_by, upload_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, title, category, dept, semester, subject, file_path, uploaded_by, upload_date)
            )
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Document published successfully!", "id": doc_id})
            return

        conn.close()
        self._send_json({"error": "API endpoint not found"}, 404)

    def do_DELETE(self):
        user = self.get_current_user()
        if not user:
            self._send_json({"success": False, "message": "Authentication required"}, 401)
            return

        role = user["role"]
        user_dept = user.get("department", "")

        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)
        item_id = query_params.get("id", [None])[0]

        if not item_id:
            self._send_json({"success": False, "message": "Record ID is required for deletion"}, 400)
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        if path == "/api/students":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            if role == "HOD":
                cursor.execute("SELECT department FROM students WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if not row or row[0] != user_dept:
                    conn.close()
                    self._send_json({"success": False, "message": "Cannot delete student from another department"}, 403)
                    return
            cursor.execute("DELETE FROM students WHERE id = ?", (item_id,))
            cursor.execute("DELETE FROM users WHERE student_id = ?", (item_id,))
            cursor.execute("DELETE FROM attendance WHERE student_id = ?", (item_id,))
            cursor.execute("DELETE FROM results WHERE student_id = ?", (item_id,))
            cursor.execute("DELETE FROM fees WHERE student_id = ?", (item_id,))

        elif path == "/api/faculty":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            if role == "HOD":
                cursor.execute("SELECT department FROM faculty WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if not row or row[0] != user_dept:
                    conn.close()
                    self._send_json({"success": False, "message": "Cannot delete faculty from another department"}, 403)
                    return
            cursor.execute("DELETE FROM faculty WHERE id = ?", (item_id,))
            cursor.execute("DELETE FROM users WHERE faculty_id = ?", (item_id,))

        elif path == "/api/hods":
            if role not in ["Administrator", "Admin"]:
                conn.close()
                self._send_json({"success": False, "message": "Only System Administrator can delete HODs"}, 403)
                return
            cursor.execute("DELETE FROM hods WHERE id = ? OR department = ?", (item_id, item_id))

        elif path == "/api/departments":
            if role not in ["Administrator", "Admin"]:
                conn.close()
                self._send_json({"success": False, "message": "Only System Administrator can delete departments"}, 403)
                return
            cursor.execute("DELETE FROM departments WHERE id = ?", (item_id,))

        elif path == "/api/attendance":
            if role not in ["Administrator", "Admin", "HOD", "Faculty"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            if role in ["HOD", "Faculty"]:
                cursor.execute("SELECT department FROM attendance WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if not row or row[0] != user_dept:
                    conn.close()
                    self._send_json({"success": False, "message": "Cannot delete attendance outside your department"}, 403)
                    return
            cursor.execute("DELETE FROM attendance WHERE id = ?", (item_id,))

        elif path == "/api/results":
            if role not in ["Administrator", "Admin", "HOD", "Faculty"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            if role in ["HOD", "Faculty"]:
                cursor.execute("SELECT s.department FROM results r JOIN students s ON r.student_id = s.id WHERE r.id = ?", (item_id,))
                row = cursor.fetchone()
                if not row or row[0] != user_dept:
                    conn.close()
                    self._send_json({"success": False, "message": "Cannot delete exam result outside your department"}, 403)
                    return
            cursor.execute("DELETE FROM results WHERE id = ?", (item_id,))

        elif path == "/api/fees":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            if role == "HOD":
                cursor.execute("SELECT department FROM fees WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if not row or row[0] != user_dept:
                    conn.close()
                    self._send_json({"success": False, "message": "Cannot delete fee record outside your department"}, 403)
                    return
            cursor.execute("DELETE FROM fees WHERE id = ?", (item_id,))

        elif path == "/api/timetable":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            if role == "HOD":
                cursor.execute("SELECT department FROM timetable WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if not row or row[0] != user_dept:
                    conn.close()
                    self._send_json({"success": False, "message": "Cannot delete timetable slot outside your department"}, 403)
                    return
            cursor.execute("DELETE FROM timetable WHERE id = ?", (item_id,))

        elif path == "/api/notices":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            if role == "HOD":
                cursor.execute("SELECT department FROM notices WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if not row or row[0] not in [user_dept, "All"]:
                    conn.close()
                    self._send_json({"success": False, "message": "Cannot delete notice outside your department"}, 403)
                    return
            cursor.execute("DELETE FROM notices WHERE id = ?", (item_id,))

        elif path == "/api/contact":
            if role not in ["Administrator", "Admin", "HOD"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            cursor.execute("DELETE FROM contact_messages WHERE id = ?", (item_id,))

        elif path == "/api/documents":
            if role not in ["Administrator", "Admin", "HOD", "Faculty"]:
                conn.close()
                self._send_json({"success": False, "message": "Permission denied"}, 403)
                return
            cursor.execute("DELETE FROM documents WHERE id = ?", (item_id,))

        conn.commit()
        conn.close()
        self._send_json({"success": True, "message": "Record deleted successfully!"})
        return

    def do_PUT(self):
        return self.do_POST()

def main(port=PORT):
    init_db()
    print("==================================================")
    print("College ERP System - Secure Python Backend Server")
    print(f"Running at: http://localhost:{port}")
    print(f"Serving frontend from: {FRONTEND_DIR}")
    print(f"Database located at: {DB_FILE}")
    print("==================================================")
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", port), ERPRequestHandler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down ERP Python server...")
    except Exception as e:
        print(f"Port binding error on {port}: {e}")

if __name__ == "__main__":
    main()
