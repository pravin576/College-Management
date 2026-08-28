import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user

def handle_get_contact(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Access denied"}, 403)
        return
    cursor.execute("SELECT * FROM contact_messages ORDER BY date DESC, id DESC")
    msgs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "contacts": msgs})
    return

#     . Executive Summary Dashboard Stats

register_route('GET', '/api/contact', handle_get_contact)

def handle_post_contact(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    subject = body.get("subject", "").strip()
    message = body.get("message", "").strip()
    recipient_email = body.get("recipientEmail", "admin@college.edu").strip()

    if not name or not email or not subject or not message:
        handler_instance._send_json({"success": False, "message": "All contact form fields are required!"}, 400)
        return

    inquiry_id = f"INQ_{int(time.time() * 1000)}"
    date_str = time.strftime('%Y-%m-%d %H:%M:%S')

    pass # conn = get_db_connection()
    pass
    cursor.execute(
        "INSERT INTO contact_messages (id, name, email, subject, message, recipientEmail, date, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (inquiry_id, name, email, subject, message, recipient_email, date_str, "Unread")
    )
    conn.commit()
    conn.close()

    handler_instance._send_json({
        "success": True,
        "message": "Contact inquiry submitted successfully!",
        "contact": { "id": inquiry_id, "name": name, "email": email, "subject": subject, "message": message, "date": date_str }
    })
    return

#      Forgot Password Endpoint (Role-based recovery for Student, Faculty, HOD, Administrator)

register_route('POST', '/api/contact', handle_post_contact)

def handle_delete_contact(handler_instance, query_params, body):
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
    cursor.execute("DELETE FROM contact_messages WHERE id = %s", (item_id,))


register_route('DELETE', '/api/contact', handle_delete_contact)

