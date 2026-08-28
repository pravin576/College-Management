import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user

def handle_get_notices(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role == "Student":
        cursor.execute("SELECT * FROM notices WHERE department IN ('All', %s) AND target_role IN ('All', 'Student') ORDER BY date DESC, id DESC", (user_dept,))
    elif role == "Faculty":
        cursor.execute("SELECT * FROM notices WHERE department IN ('All', %s) AND target_role IN ('All', 'Faculty') ORDER BY date DESC, id DESC", (user_dept,))
    elif role == "HOD":
        cursor.execute("SELECT * FROM notices WHERE department IN ('All', %s) ORDER BY date DESC, id DESC", (user_dept,))
    else: # Admin
        cursor.execute("SELECT * FROM notices ORDER BY date DESC, id DESC")
    notices = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "notices": notices})
    return

#      Subjects Endpoint

register_route('GET', '/api/notices', handle_get_notices)
register_route('GET', '/api/public/notices', handle_get_notices)

def handle_post_notices(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Only Admin and HOD can publish notices"}, 403)
        return

    n_id = body.get("id") or f"NOT{int(time.time()) % 10000}"
    title = body.get("title")
    n_date = body.get("date", time.strftime('%Y-%m-%d'))
    dept = user_dept if role == "HOD" else body.get("department", "All")
    target_role = body.get("targetRole", "All")
    priority = body.get("priority", "Medium")
    desc = body.get("description", "")
    attachment = body.get("attachment", "")
    author = user.get("name", "Administration")

    cursor.execute(
        """REPLACE INTO notices (id, title, date, department, target_role, priority, description, attachment, author)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (n_id, title, n_date, dept, target_role, priority, desc, attachment, author)
    )
    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "Notice published successfully!", "id": n_id})
    return

#     . Profile Update

register_route('POST', '/api/notices', handle_post_notices)

def handle_delete_notices(handler_instance, query_params, body):
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


    item_id = query_params.get("id", [None])[0]
    if not item_id:
        conn.close()
        return handler_instance._send_json({"success": False, "message": "ID required"}, 400)

    if role not in ["Administrator", "Admin", "HOD"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return
    if role == "HOD":
        cursor.execute("SELECT department FROM notices WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row or row.get("department") not in [user_dept, "All"]:
            conn.close()
            handler_instance._send_json({"success": False, "message": "Cannot delete notice outside your department"}, 403)
            return
    cursor.execute("DELETE FROM notices WHERE id = %s", (item_id,))


register_route('DELETE', '/api/notices', handle_delete_notices)

