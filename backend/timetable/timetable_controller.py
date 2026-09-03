import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod

def handle_get_timetable(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if is_admin(user):
            dept_filter = query_params.get("department", [None])[0]
            if dept_filter and dept_filter != "All":
                cursor.execute("SELECT * FROM timetable WHERE department = %s ORDER BY day, time", (dept_filter,))
            else:
                cursor.execute("SELECT * FROM timetable ORDER BY department, day, time")
        else:
            cursor.execute("SELECT * FROM timetable WHERE department = %s ORDER BY day, time", (user_dept,))
        recs = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "timetable": recs})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/timetable', handle_get_timetable)

def handle_post_timetable(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Permission denied: Only Admin and HOD can manage timetable"}, 403)

    role = user.get('role')
    user_dept = user.get('department')
    tt_id = body.get("id")
    dept = user_dept if is_hod(user) else (body.get("department") or "Computer Engineering").strip()
    sem = (body.get("semester") or "Semester 1").strip()
    div = (body.get("division") or "A").strip()
    day = (body.get("day") or "Monday").strip()
    tt_time = (body.get("time") or "10:00 AM - 11:00 AM").strip()
    subject = (body.get("subject") or "").strip()
    faculty = (body.get("faculty") or "").strip()
    room = (body.get("room") or "Classroom 1").strip()

    if not subject:
        return handler_instance._send_json({"success": False, "message": "Subject is required for timetable slot"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Division slot conflict
        if tt_id:
            cursor.execute("SELECT id, subject FROM timetable WHERE department=%s AND semester=%s AND division=%s AND day=%s AND time=%s AND id!=%s", (dept, sem, div, day, tt_time, tt_id))
        else:
            cursor.execute("SELECT id, subject FROM timetable WHERE department=%s AND semester=%s AND division=%s AND day=%s AND time=%s", (dept, sem, div, day, tt_time))
        conflict = cursor.fetchone()
        if conflict:
            return handler_instance._send_json({"success": False, "message": f"Timetable conflict: Slot '{tt_time}' on {day} is already scheduled for '{conflict['subject']}' in {dept} ({sem} - Div {div})."}, 400)

        # 2. Room conflict
        if room and room.lower() not in ["", "online", "tba"]:
            if tt_id:
                cursor.execute("SELECT id, department, subject FROM timetable WHERE room=%s AND day=%s AND time=%s AND id!=%s", (room, day, tt_time, tt_id))
            else:
                cursor.execute("SELECT id, department, subject FROM timetable WHERE room=%s AND day=%s AND time=%s", (room, day, tt_time))
            room_conflict = cursor.fetchone()
            if room_conflict:
                return handler_instance._send_json({"success": False, "message": f"Room conflict: Room '{room}' is already occupied by {room_conflict['department']} for '{room_conflict['subject']}' at {tt_time} on {day}."}, 400)

        # 3. Faculty conflict
        if faculty and faculty.lower() not in ["", "tba"]:
            if tt_id:
                cursor.execute("SELECT id, department, subject FROM timetable WHERE faculty=%s AND day=%s AND time=%s AND id!=%s", (faculty, day, tt_time, tt_id))
            else:
                cursor.execute("SELECT id, department, subject FROM timetable WHERE faculty=%s AND day=%s AND time=%s", (faculty, day, tt_time))
            faculty_conflict = cursor.fetchone()
            if faculty_conflict:
                return handler_instance._send_json({"success": False, "message": f"Faculty conflict: Faculty '{faculty}' is already assigned to {faculty_conflict['department']} ('{faculty_conflict['subject']}') at {tt_time} on {day}."}, 400)

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
        return handler_instance._send_json({"success": True, "message": "Timetable entry saved successfully!"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/timetable', handle_post_timetable)

def handle_delete_timetable(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)

    role = user.get('role')
    user_dept = user.get('department')
    item_id = query_params.get("id", [None])[0] or body.get("id")

    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Timetable slot ID required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM timetable WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row:
            return handler_instance._send_json({"success": False, "message": "Timetable entry not found"}, 404)

        if is_hod(user) and row.get("department") != user_dept:
            return handler_instance._send_json({"success": False, "message": "Cannot delete timetable slot outside your department"}, 403)

        cursor.execute("DELETE FROM timetable WHERE id = %s", (item_id,))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Timetable entry deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/timetable', handle_delete_timetable)
