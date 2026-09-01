import base64
import urllib.parse
import datetime
import json
import time
import os
import re
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod, is_faculty, is_student

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.normpath(os.path.join(CUR_DIR, "..", "..", "frontend", "uploads"))
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR, exist_ok=True)

def handle_get_documents(handler_instance, query_params, body):
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
            dept_f = query_params.get("department", [None])[0]
            if dept_f and dept_f != "All":
                cursor.execute("SELECT * FROM documents WHERE department = %s ORDER BY upload_date DESC", (dept_f,))
            else:
                cursor.execute("SELECT * FROM documents ORDER BY upload_date DESC")
        else:
            cursor.execute("SELECT * FROM documents WHERE department IN ('All', %s) ORDER BY upload_date DESC", (user_dept,))
            
        docs = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "documents": docs})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/documents', handle_get_documents)

def handle_post_documents(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    if is_student(user):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Students cannot upload documents"}, 403)

    role = user.get('role')
    user_dept = user.get('department')

    doc_id = (body.get("id") or f"DOC_{int(time.time() * 1000)}").strip()
    title = (body.get("title") or "Untitled Document").strip()
    category = body.get("category", "Notes").strip()
    dept = user_dept if (is_hod(user) or is_faculty(user)) else (body.get("department") or "All").strip()
    semester = body.get("semester", "All").strip()
    subject = body.get("subject", "All").strip()
    file_path = (body.get("filePath") or body.get("file_path") or "").strip()
    uploaded_by = user.get("name", "Staff")
    upload_date = time.strftime('%Y-%m-%d %H:%M:%S')

    if not title or not file_path:
        return handler_instance._send_json({"success": False, "message": "Document Title and File are required"}, 400)

    # Prevent directory traversal in file path
    clean_file_path = file_path.replace("\\", "/")
    if ".." in clean_file_path or clean_file_path.startswith("/../"):
        return handler_instance._send_json({"success": False, "message": "Invalid file path (directory traversal detected)"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """REPLACE INTO documents (id, title, category, department, semester, subject, file_path, uploaded_by, upload_date)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (doc_id, title, category, dept, semester, subject, clean_file_path, uploaded_by, upload_date)
        )
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Document published successfully!", "id": doc_id})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/documents', handle_post_documents)

def handle_delete_documents(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    if is_student(user):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Students cannot delete documents"}, 403)

    role = user.get('role')
    user_dept = user.get('department')
    item_id = query_params.get("id", [None])[0] or body.get("id")

    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Document ID is required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM documents WHERE id = %s", (item_id,))
        doc = cursor.fetchone()
        if not doc:
            return handler_instance._send_json({"success": False, "message": "Document not found"}, 404)

        if not is_admin(user) and doc.get("department") not in [user_dept, "All"]:
            return handler_instance._send_json({"success": False, "message": "Cannot delete document outside your department"}, 403)

        cursor.execute("DELETE FROM documents WHERE id = %s", (item_id,))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Document deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/documents', handle_delete_documents)
