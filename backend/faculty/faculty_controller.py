import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod
from auth.utils import hash_password, generate_temp_password

def handle_get_faculty(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'Database connection error'}, 500)
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        base_query = """
            SELECT f.id, f.name, f.department, f.designation, f.email, f.mobile, f.experience,
                   MAX(u.id) AS user_id, MAX(u.username) AS username,
                   COALESCE(MAX(u.status), f.status, 'Active') AS status
            FROM faculty f
            LEFT JOIN users u ON (
                (f.id IS NOT NULL AND f.id != '' AND u.faculty_id = f.id)
                OR (f.email IS NOT NULL AND f.email != '' AND u.email = f.email AND u.role = 'Faculty')
            )
        """
        group_order = " GROUP BY f.id, f.name, f.department, f.designation, f.email, f.mobile, f.experience, f.status ORDER BY f.department, f.name ASC"
        
        if is_admin(user):
            dept_filter = query_params.get("department", [None])[0]
            if dept_filter and dept_filter != "All":
                cursor.execute(base_query + " WHERE f.department = %s" + group_order, (dept_filter,))
            else:
                cursor.execute(base_query + group_order)
        else:
            cursor.execute(base_query + " WHERE f.department = %s" + group_order, (user_dept,))
            
        fac = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "faculty": fac})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/faculty', handle_get_faculty)

def handle_post_faculty(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_hod(user):
        if is_admin(user) or (user and user.get('role') in ['Administrator', 'Admin', 'Principal']):
            return handler_instance._send_json({"success": False, "message": "Permission denied: Administrative/Principal role is monitoring-only. Faculty management is handled by the Head of Department (HOD)."}, 403)
        return handler_instance._send_json({"success": False, "message": "Permission denied: Only Head of Department (HOD) can manage faculty records"}, 403)

    user_dept = user.get('department')
    requested_dept = (body.get("department") or "").strip()
    if requested_dept and requested_dept != user_dept:
        return handler_instance._send_json({"success": False, "message": f"Forbidden: HOD can only manage faculty for their assigned department ({user_dept})."}, 403)
    dept = user_dept

    f_id = (body.get("id") or body.get("facultyId") or f"FAC_{int(time.time()) % 100000}").strip()
    mobile = (body.get("mobile", "") or body.get("phone", "")).strip()
    email = body.get("email", "").strip()
    name = body.get("name", "").strip()
    status_val = body.get("status", "Active")
    is_edit = body.get("is_edit", False)

    if not f_id or not name:
        return handler_instance._send_json({"success": False, "message": "Faculty ID and Name are required!"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'Database connection error'}, 500)
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("SELECT id, department FROM faculty WHERE id = %s", (f_id,))
        existing_fac = cursor.fetchone()

        if existing_fac and existing_fac.get("department") != user_dept:
            return handler_instance._send_json({"success": False, "message": f"Forbidden: Cannot edit faculty belonging to another department ({existing_fac.get('department')})."}, 403)

        if existing_fac or is_edit:
            cursor.execute(
                """UPDATE faculty 
                   SET name = %s, department = %s, designation = %s, email = %s, mobile = %s, experience = %s, status = %s
                   WHERE id = %s""",
                (
                    name,
                    dept,
                    body.get("designation", "Assistant Professor"),
                    email if email else f"{f_id.lower()}@college.edu",
                    mobile if mobile else "9876543210",
                    body.get("experience", "1 Year"),
                    status_val,
                    f_id
                )
            )
        else:
            cursor.execute(
                """INSERT INTO faculty (id, name, department, designation, email, mobile, experience, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    f_id,
                    name,
                    dept,
                    body.get("designation", "Assistant Professor"),
                    email if email else f"{f_id.lower()}@college.edu",
                    mobile if mobile else "9876543210",
                    body.get("experience", "1 Year"),
                    status_val
                )
            )
        cursor.execute("SELECT id FROM users WHERE faculty_id = %s OR username = %s OR (email = %s AND email != '')", (f_id, f_id, email))
        existing_user = cursor.fetchone()
        if existing_user:
            new_pass = (body.get("password") or "").strip()
            if new_pass:
                hashed = hash_password(new_pass)
                cursor.execute(
                    "UPDATE users SET name = %s, department = %s, mobile = %s, email = %s, status = %s, password = %s WHERE id = %s",
                    (name, dept, mobile if mobile else "9876543210", email if email else f"{f_id.lower()}@college.edu", status_val, hashed, existing_user["id"])
                )
            else:
                cursor.execute(
                    "UPDATE users SET name = %s, department = %s, mobile = %s, email = %s, status = %s WHERE id = %s",
                    (name, dept, mobile if mobile else "9876543210", email if email else f"{f_id.lower()}@college.edu", status_val, existing_user["id"])
                )
            success_msg = "Faculty record updated successfully!"
            cred_payload = None
        else:
            username = body.get("username") or f_id
            plain_pass = body.get("password") or generate_temp_password()
            hashed = hash_password(plain_pass)
            cursor.execute(
                "INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, created_at, status, must_change_password, temp_password_created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)",
                (username, hashed, "Faculty", name, email if email else f"{f_id.lower()}@college.edu", dept, f_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'), status_val, time.strftime('%Y-%m-%d %H:%M:%S'))
            )
            success_msg = f"Faculty created successfully.\n\nFaculty Username/ID: {f_id}\nTemporary Password: {plain_pass}\n\nThe faculty member can now log in directly."
            cred_payload = {
                "name": name,
                "facultyId": f_id,
                "role": "Faculty",
                "department": dept,
                "username": username,
                "temporaryPassword": plain_pass,
                "loginUrl": "/login.html"
            }

        conn.commit()
        return handler_instance._send_json({
            "success": True, 
            "message": success_msg, 
            "id": f_id, 
            "facultyId": f_id,
            "credentials": cred_payload
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/faculty', handle_post_faculty)

def handle_delete_faculty(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    if not is_hod(user):
        if is_admin(user) or (user and user.get('role') in ['Administrator', 'Admin', 'Principal']):
            return handler_instance._send_json({"success": False, "message": "Permission denied: Administrative/Principal role is monitoring-only. Faculty deletion is managed by the Head of Department (HOD)."}, 403)
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Head of Department (HOD) can delete faculty members"}, 403)

    user_dept = user.get('department')
    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Faculty ID required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, department FROM faculty WHERE id = %s", (item_id,))
        fac = cursor.fetchone()
        if not fac:
            return handler_instance._send_json({"success": False, "message": "Faculty record not found"}, 404)

        if fac.get("department") != user_dept:
            return handler_instance._send_json({"success": False, "message": f"Forbidden: Cannot delete faculty member belonging to another department ({fac.get('department')})"}, 403)

        cursor.execute("DELETE FROM faculty_students WHERE faculty_id = %s", (item_id,))
        cursor.execute("DELETE FROM users WHERE faculty_id = %s", (item_id,))
        cursor.execute("DELETE FROM faculty WHERE id = %s", (item_id,))

        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Faculty member deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Database deletion error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/faculty', handle_delete_faculty)
