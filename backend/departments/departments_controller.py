import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user

def handle_get_departments(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    pass # conn = get_db_connection()
    # conn.row_factory = 
    pass
    cursor.execute("SELECT * FROM departments ORDER BY name ASC")
    depts = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "departments": depts})
    return



register_route('GET', '/api/departments', handle_get_departments)

def handle_post_departments(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role not in ["Administrator", "Admin"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Only System Administrator can create or edit departments"}, 403)
        return
    code = body.get("code", "").strip()
    name = body.get("name", "").strip()
    desc = body.get("description", "").strip()
    dept_id = body.get("id")

    if dept_id:
        cursor.execute("UPDATE departments SET code = %s, name = %s, description = %s WHERE id = %s", (code, name, desc, dept_id))
    else:
        cursor.execute("REPLACE INTO departments (code, name, description) VALUES (%s, %s, %s)", (code, name, desc))
    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "Department saved successfully!"})
    return

#      Students CRUD

register_route('POST', '/api/departments', handle_post_departments)

def handle_delete_departments(handler_instance, query_params, body):
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


    if role not in ["Administrator", "Admin"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Only System Administrator can delete departments"}, 403)
        return
    cursor.execute("DELETE FROM departments WHERE id = %s", (item_id,))


register_route('DELETE', '/api/departments', handle_delete_departments)

