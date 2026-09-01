import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod, is_faculty, is_student

def handle_get_notices(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user.get('role') if user else None
    user_dept = user.get('department') if user else None

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if role == "Student":
            cursor.execute("SELECT * FROM notices WHERE department IN ('All', %s) AND target_role IN ('All', 'Student') ORDER BY date DESC, id DESC", (user_dept,))
        elif role == "Faculty":
            cursor.execute("SELECT * FROM notices WHERE department IN ('All', %s) AND target_role IN ('All', 'Faculty') ORDER BY date DESC, id DESC", (user_dept,))
        elif role == "HOD":
            cursor.execute("SELECT * FROM notices WHERE department IN ('All', %s) ORDER BY date DESC, id DESC", (user_dept,))
        else: # Admin or Public unauthenticated
            cursor.execute("SELECT * FROM notices ORDER BY date DESC, id DESC")
        notices = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "notices": notices})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/notices', handle_get_notices)
register_route('GET', '/api/public/notices', handle_get_notices)

def handle_post_notices(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Admin and HOD can publish notices"}, 403)

    role = user.get('role')
    user_dept = user.get('department')

    n_id = (body.get("id") or f"NOT_{int(time.time() * 1000) % 100000}").strip()
    title = (body.get("title") or "").strip()
    n_date = body.get("date") or time.strftime('%Y-%m-%d')
    dept = user_dept if is_hod(user) else (body.get("department") or "All").strip()
    target_role = body.get("targetRole", "All").strip()
    priority = body.get("priority", "Medium").strip()
    desc = (body.get("description") or "").strip()
    attachment = (body.get("attachment") or "").strip()
    author = user.get("name", "Administration")

    if not title or not desc:
        return handler_instance._send_json({"success": False, "message": "Notice Title and Description are required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """REPLACE INTO notices (id, title, date, department, target_role, priority, description, attachment, author)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (n_id, title, n_date, dept, target_role, priority, desc, attachment, author)
        )
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Notice published successfully!", "id": n_id})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/notices', handle_post_notices)

def handle_delete_notices(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)

    role = user.get('role')
    user_dept = user.get('department')
    item_id = query_params.get("id", [None])[0] or body.get("id")

    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Notice ID required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM notices WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row:
            return handler_instance._send_json({"success": False, "message": "Notice not found"}, 404)

        if is_hod(user) and row.get("department") not in [user_dept, "All"]:
            return handler_instance._send_json({"success": False, "message": "Cannot delete notice outside your department"}, 403)

        cursor.execute("DELETE FROM notices WHERE id = %s", (item_id,))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Notice deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/notices', handle_delete_notices)
