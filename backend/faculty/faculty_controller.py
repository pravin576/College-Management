import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user
from auth.utils import hash_password

def handle_get_faculty(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role in ["Student", "HOD", "Faculty"]:
        cursor.execute("SELECT * FROM faculty WHERE department = %s", (user_dept,))
    else: # Admin
        dept_filter = query_params.get("department", [None])[0]
        if dept_filter and dept_filter != "All":
            cursor.execute("SELECT * FROM faculty WHERE department = %s", (dept_filter,))
        else:
            cursor.execute("SELECT * FROM faculty")
    fac = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "faculty": fac})
    return

#      HODs Endpoint

register_route('GET', '/api/faculty', handle_get_faculty)

def handle_post_faculty(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role not in ["Administrator", "Admin", "HOD"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return
    f_id = body.get("id") or body.get("facultyId") or f"FAC{int(time.time()) % 100000}"
    dept = user_dept if role == "HOD" else body.get("department", "Computer Science")
    mobile = body.get("mobile", "").strip() or body.get("phone", "").strip()
    email = body.get("email", "").strip()
    name = body.get("name", "").strip()

    cursor.execute(
        """REPLACE INTO faculty (id, name, department, designation, email, mobile, experience, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            f_id,
            name,
            dept,
            body.get("designation", "Assistant Professor"),
            email,
            mobile,
            body.get("experience", "1 Year"),
            body.get("status", "Active")
        )
    )
    cursor.execute("SELECT id FROM users WHERE faculty_id = %s OR email = %s", (f_id, email))
    if not cursor.fetchone():
        username = body.get("username") or (email.split("@")[0] if email else f"faculty_{f_id}")
        plain_pass = body.get("password", "faculty123")
        hashed = hash_password(plain_pass)
        cursor.execute(
            "INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (username, hashed, "Faculty", name, email, dept, f_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
        )

    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "Faculty record saved successfully!", "id": f_id})
    return

#      HODs CRUD

register_route('POST', '/api/faculty', handle_post_faculty)

def handle_delete_faculty(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)
    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        if conn: conn.close()
        handler_instance._send_json({"success": False, "message": "ID required"}, 400)
        return


    if role not in ["Administrator", "Admin", "HOD"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return
    if role == "HOD":
        cursor.execute("SELECT department FROM faculty WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row or row[0] != user_dept:
            conn.close()
            handler_instance._send_json({"success": False, "message": "Cannot delete faculty from another department"}, 403)
            return
    cursor.execute("DELETE FROM faculty WHERE id = %s", (item_id,))
    cursor.execute("DELETE FROM users WHERE faculty_id = %s", (item_id,))


register_route('DELETE', '/api/faculty', handle_delete_faculty)

