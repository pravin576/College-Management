import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod

def handle_get_subjects(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user.get('role') if user else None
    user_dept = user.get('department') if user else None

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if is_admin(user):
            dept_filter = query_params.get("department", [None])[0]
            if dept_filter and dept_filter != "All":
                cursor.execute("SELECT * FROM subjects WHERE department = %s ORDER BY semester, name ASC", (dept_filter,))
            else:
                cursor.execute("SELECT * FROM subjects ORDER BY department, semester, name ASC")
        elif role in ["Student", "Faculty", "HOD"]:
            cursor.execute("SELECT * FROM subjects WHERE department = %s ORDER BY semester, name ASC", (user_dept,))
        else:
            cursor.execute("SELECT * FROM subjects ORDER BY department, semester, name ASC")
            
        subjects = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "subjects": subjects})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/subjects', handle_get_subjects)

def handle_post_subjects(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Admin and HOD can manage subjects"}, 403)

    user_dept = user.get('department')
    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip()
    dept = user_dept if is_hod(user) else (body.get("department") or "Computer Engineering").strip()
    semester = (body.get("semester") or "Semester 1").strip()
    credits_val = int(body.get("credits", 4))
    faculty_id = (body.get("faculty_id") or "").strip()
    sub_id = body.get("id")

    if not code or not name:
        return handler_instance._send_json({"success": False, "message": "Subject Code and Name are required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if sub_id:
            cursor.execute("SELECT id FROM subjects WHERE code = %s AND id != %s", (code, sub_id))
        else:
            cursor.execute("SELECT id FROM subjects WHERE code = %s", (code,))
        if cursor.fetchone():
            return handler_instance._send_json({"success": False, "message": f"Subject with code '{code}' already exists. Please use a unique subject code."}, 400)

        if sub_id:
            cursor.execute(
                "UPDATE subjects SET code=%s, name=%s, department=%s, semester=%s, credits=%s, faculty_id=%s WHERE id=%s",
                (code, name, dept, semester, credits_val, faculty_id, sub_id)
            )
        else:
            cursor.execute(
                "INSERT INTO subjects (code, name, department, semester, credits, faculty_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (code, name, dept, semester, credits_val, faculty_id)
            )
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Subject saved successfully!"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/subjects', handle_post_subjects)

def handle_delete_subjects(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Forbidden"}, 403)

    user_dept = user.get('department')
    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Subject ID required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM subjects WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row:
            return handler_instance._send_json({"success": False, "message": "Subject not found"}, 404)

        if is_hod(user) and row.get("department") != user_dept:
            return handler_instance._send_json({"success": False, "message": "Cannot delete subject outside your department"}, 403)

        cursor.execute("DELETE FROM subjects WHERE id = %s", (item_id,))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Subject deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/subjects', handle_delete_subjects)

def handle_post_excel_export_errors(handler_instance, query_params, body):
    errors = body.get("errors", [])
    lines = ["Excel Row Number,Student ID,Student Name,Failure Reason\n"]
    for err in errors:
        lines.append(f'"{err.get("row")}","{err.get("student_id")}","{err.get("name")}","{err.get("reason")}"\n')

    handler_instance.send_response(200)
    handler_instance.send_header("Content-type", "text/csv; charset=utf-8")
    handler_instance.send_header("Content-Disposition", 'attachment; filename="excel_import_error_report.csv"')
    handler_instance.end_headers()
    handler_instance.wfile.write("".join(lines).encode("utf-8"))

register_route('POST', '/api/excel/export-errors', handle_post_excel_export_errors)
