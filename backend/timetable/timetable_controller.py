import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user

def handle_get_timetable(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role in ["Student", "Faculty", "HOD"]:
        cursor.execute("SELECT * FROM timetable WHERE department = %s", (user_dept,))
    else: # Admin
        dept_filter = query_params.get("department", [None])[0]
        if dept_filter and dept_filter != "All":
            cursor.execute("SELECT * FROM timetable WHERE department = %s", (dept_filter,))
        else:
            cursor.execute("SELECT * FROM timetable")
    recs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "timetable": recs})
    return

#      Notices Endpoint

register_route('GET', '/api/timetable', handle_get_timetable)

def handle_post_timetable(handler_instance, query_params, body):
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
    tt_id = body.get("id")
    dept = user_dept if role == "HOD" else body.get("department", "Computer Science")
    sem = body.get("semester", "Semester 1")
    div = body.get("division", "A")
    day = body.get("day", "Monday")
    tt_time = body.get("time", "10:00 AM - 11:00 AM")
    subject = body.get("subject", "")
    faculty = body.get("faculty", "")
    room = body.get("room", "Lab 1")

    if tt_id:
        cursor.execute(
            "UPDATE timetable SET department=%s, semester=%s, division=%s, day=%s, time=%s, subject=%s, faculty=%s, room=%s WHERE id=%s",
            (dept, sem, div, day, tt_time, subject, faculty, room, tt_id)
        )
    else:
        cursor.execute(
            "INSERT INTO timetable (department, semester, division, day, time, subject, faculty, room) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (dept, sem, div, day, tt_time, subject, faculty, room)
        )
    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "Timetable entry saved successfully!"})
    return

#     . Notices CRUD

register_route('POST', '/api/timetable', handle_post_timetable)

def handle_delete_timetable(handler_instance, query_params, body):
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
        cursor.execute("SELECT department FROM timetable WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row or row[0] != user_dept:
            conn.close()
            handler_instance._send_json({"success": False, "message": "Cannot delete timetable slot outside your department"}, 403)
            return
    cursor.execute("DELETE FROM timetable WHERE id = %s", (item_id,))


register_route('DELETE', '/api/timetable', handle_delete_timetable)

