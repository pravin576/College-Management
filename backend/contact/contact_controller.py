import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod

def handle_get_contact(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Access denied to contact inquiries"}, 403)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM contact_messages ORDER BY date DESC, id DESC")
        msgs = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "contacts": msgs})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/contact', handle_get_contact)

def handle_post_contact(handler_instance, query_params, body):
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    subject = (body.get("subject") or "").strip()
    message = (body.get("message") or "").strip()
    recipient_email = (body.get("recipientEmail") or "admin@college.edu").strip()

    if not name or not email or not subject or not message:
        return handler_instance._send_json({"success": False, "message": "All contact form fields (Name, Email, Subject, Message) are required!"}, 400)

    inquiry_id = f"INQ_{int(time.time() * 1000)}"
    date_str = time.strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "INSERT INTO contact_messages (id, name, email, subject, message, recipientEmail, date, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (inquiry_id, name, email, subject, message, recipient_email, date_str, "Unread")
        )
        conn.commit()
        return handler_instance._send_json({
            "success": True,
            "message": "Contact inquiry submitted successfully!",
            "contact": { "id": inquiry_id, "name": name, "email": email, "subject": subject, "message": message, "date": date_str }
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/contact', handle_post_contact)

def handle_delete_contact(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Administrator can delete contact messages"}, 403)

    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Contact message ID required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("DELETE FROM contact_messages WHERE id = %s", (item_id,))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Contact message deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/contact', handle_delete_contact)
