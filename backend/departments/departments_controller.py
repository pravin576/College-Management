import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin

def handle_get_departments(handler_instance, query_params, body):
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM departments ORDER BY name ASC")
        depts = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "departments": depts})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/departments', handle_get_departments)

def handle_post_departments(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Administrator can manage departments"}, 403)

    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip()
    desc = (body.get("description") or "").strip()
    dept_id = body.get("id")

    if not code or not name:
        return handler_instance._send_json({"success": False, "message": "Department Code and Name are required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if dept_id:
            cursor.execute("UPDATE departments SET code = %s, name = %s, description = %s WHERE id = %s", (code, name, desc, dept_id))
        else:
            cursor.execute("REPLACE INTO departments (code, name, description) VALUES (%s, %s, %s)", (code, name, desc))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Department saved successfully!"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/departments', handle_post_departments)

def handle_delete_departments(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Administrator can delete departments"}, 403)

    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Department ID is required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM departments WHERE id = %s OR code = %s OR name = %s", (item_id, item_id, item_id))
        dept_row = cursor.fetchone()
        if not dept_row:
            return handler_instance._send_json({"success": True, "message": "Department not found or already deleted"})

        dept_name = dept_row["name"]

        # Check students
        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s", (dept_name,))
        stu_cnt = cursor.fetchone()["count"]
        if stu_cnt > 0:
            return handler_instance._send_json({"success": False, "message": f"Cannot delete department '{dept_name}' because {stu_cnt} student record(s) belong to it. Please reassign or delete these students first."}, 400)

        # Check faculty
        cursor.execute("SELECT COUNT(*) as count FROM faculty WHERE department = %s", (dept_name,))
        fac_cnt = cursor.fetchone()["count"]
        if fac_cnt > 0:
            return handler_instance._send_json({"success": False, "message": f"Cannot delete department '{dept_name}' because {fac_cnt} faculty member(s) belong to it. Please reassign or delete these faculty members first."}, 400)

        # Check HOD
        cursor.execute("SELECT COUNT(*) as count FROM hods WHERE department = %s", (dept_name,))
        hod_cnt = cursor.fetchone()["count"]
        if hod_cnt > 0:
            return handler_instance._send_json({"success": False, "message": f"Cannot delete department '{dept_name}' because an assigned HOD exists. Please remove the HOD assignment first."}, 400)

        # Check Timetable
        cursor.execute("SELECT COUNT(*) as count FROM timetable WHERE department = %s", (dept_name,))
        tt_cnt = cursor.fetchone()["count"]
        if tt_cnt > 0:
            return handler_instance._send_json({"success": False, "message": f"Cannot delete department '{dept_name}' because {tt_cnt} timetable slot(s) exist for it."}, 400)

        # Check Subjects
        cursor.execute("SELECT COUNT(*) as count FROM subjects WHERE department = %s", (dept_name,))
        sub_cnt = cursor.fetchone()["count"]
        if sub_cnt > 0:
            return handler_instance._send_json({"success": False, "message": f"Cannot delete department '{dept_name}' because {sub_cnt} subject(s) are associated with it."}, 400)

        cursor.execute("DELETE FROM departments WHERE id = %s", (dept_row["id"],))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": f"Department '{dept_name}' deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/departments', handle_delete_departments)
