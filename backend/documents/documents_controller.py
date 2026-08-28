import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user

def handle_get_documents(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role in ["Student", "Faculty", "HOD"]:
        cursor.execute("SELECT * FROM documents WHERE department IN ('All', %s) ORDER BY upload_date DESC", (user_dept,))
    else:
        cursor.execute("SELECT * FROM documents ORDER BY upload_date DESC")
    docs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "documents": docs})
    return

#     . Contact Messages Inbox

register_route('GET', '/api/documents', handle_get_documents)

def handle_delete_documents(handler_instance, query_params, body):
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


    if role not in ["Administrator", "Admin", "HOD", "Faculty"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Only Admin, HOD, and Faculty can upload documents"}, 403)
        return

    doc_id = body.get("id") or f"DOC_{int(time.time() * 1000)}"
    title = body.get("title", "Untitled Document")
    category = body.get("category", "Notes")
    dept = user_dept if role in ["HOD", "Faculty"] else body.get("department", "All")
    semester = body.get("semester", "All")
    subject = body.get("subject", "All")
    file_path = body.get("filePath") or body.get("file_path", "")
    uploaded_by = user.get("name", "Staff")
    upload_date = time.strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
        """REPLACE INTO documents (id, title, category, department, semester, subject, file_path, uploaded_by, upload_date)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (doc_id, title, category, dept, semester, subject, file_path, uploaded_by, upload_date)
    )
    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "Document published successfully!", "id": doc_id})
    return

#     .close()
#     ._send_json({"error": "API endpoint not found"}, 404)

#      = self.get_current_user()
#     ot user:
    handler_instance._send_json({"success": False, "message": "Authentication required"}, 401)
    return

#      = user["role"]
    _dept = user.get("department", "")

    ed_url = urllib.parse.urlparse(self.path)
#      = parsed_url.path
    y_params = urllib.parse.parse_qs(parsed_url.query)
    _id = query_params.get("id", [None])[0]

#     ot item_id:
    handler_instance._send_json({"success": False, "message": "Record ID is required for deletion"}, 400)
    return

#      = get_db_connection()
#     or = # conn.cursor()


register_route('DELETE', '/api/documents', handle_delete_documents)

def handle_put_documents(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role not in ["Administrator", "Admin", "HOD", "Faculty"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return
    cursor.execute("DELETE FROM documents WHERE id = %s", (item_id,))

#     .commit()
#     .close()
#     ._send_json({"success": True, "message": "Record deleted successfully!"})
    rn

#     rn self.do_POST()


register_route('PUT', '/api/documents', handle_put_documents)

