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
        cursor.execute("DELETE FROM departments WHERE id = %s", (item_id,))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Department deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/departments', handle_delete_departments)
