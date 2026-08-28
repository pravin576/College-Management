import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user

def handle_get_subjects(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role in ["Student", "Faculty", "HOD"]:
        cursor.execute("SELECT * FROM subjects WHERE department = %s", (user_dept,))
    else: # Admin
        dept_filter = query_params.get("department", [None])[0]
        if dept_filter and dept_filter != "All":
            cursor.execute("SELECT * FROM subjects WHERE department = %s", (dept_filter,))
        else:
            cursor.execute("SELECT * FROM subjects")
    subjects = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "subjects": subjects})
    return

#     . Documents Endpoint

register_route('GET', '/api/subjects', handle_get_subjects)

def handle_post_excel_export_errors(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    errors = body.get("errors", [])
    lines = ["Excel Row Number,Student ID,Student Name,Failure Reason\n"]
    for err in errors:
        lines.append(f'"{err.get("row")}","{err.get("student_id")}","{err.get("name")}","{err.get("reason")}"\n')

    conn.close()
    handler_instance.send_response(200)
    handler_instance.send_header("Content-type", "text/csv; charset=utf-8")
    handler_instance.send_header("Content-Disposition", 'attachment; filename="excel_import_error_report.csv"')
    handler_instance.end_headers()
    handler_instance.wfile.write("".join(lines).encode("utf-8"))
    return

#     port Exam Results from Excel (.xlsx) Endpoint

register_route('POST', '/api/excel/export-errors', handle_post_excel_export_errors)

