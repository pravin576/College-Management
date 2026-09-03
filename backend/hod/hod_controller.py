import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin
from auth.utils import hash_password, generate_temp_password

def handle_get_hod_dashboard_stats(handler_instance, query_params, body):
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
            dept_override = query_params.get("department", [None])[0]
            target_dept = dept_override if (dept_override and dept_override != "All") else (user_dept or "Computer Engineering")
        else:
            # Enforce department isolation: Never trust frontend department for non-admin
            target_dept = user_dept or "Computer Engineering"

        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s", (target_dept,))
        cnt_total = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND (year = 'First Year' OR year IS NULL OR year = '')", (target_dept,))
        cnt_first = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND year = 'Second Year'", (target_dept,))
        cnt_second = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND year = 'Third Year'", (target_dept,))
        cnt_third = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM faculty WHERE department = %s", (target_dept,))
        cnt_fac = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as total_att, SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as pres_att FROM attendance WHERE department = %s", (target_dept,))
        att_row = cursor.fetchone()
        tot_att = (att_row['total_att'] if att_row else 0) or 0
        pres_att = (att_row['pres_att'] if att_row else 0) or 0
        att_pct = round((float(pres_att) / float(tot_att) * 100), 1) if tot_att > 0 else 100.0

        cursor.execute("SELECT COUNT(*) as total_res, SUM(CASE WHEN r.status = 'Pass' THEN 1 ELSE 0 END) as pass_res FROM results r JOIN students s ON r.student_id = s.id WHERE s.department = %s", (target_dept,))
        res_row = cursor.fetchone()
        tot_res = (res_row['total_res'] if res_row else 0) or 0
        pass_res = (res_row['pass_res'] if res_row else 0) or 0
        pass_pct = round((float(pass_res) / float(tot_res) * 100), 1) if tot_res > 0 else 100.0

        cursor.execute("SELECT SUM(pending_fees) as pending FROM fees WHERE department = %s", (target_dept,))
        fee_row = cursor.fetchone()
        pending_fees = float(fee_row['pending'] or 0) if fee_row else 0.0

        cursor.execute("SELECT COUNT(*) as count FROM notices WHERE department IN ('All', %s)", (target_dept,))
        cnt_notices = cursor.fetchone()['count']

        return handler_instance._send_json({
            "success": True,
            "department": target_dept,
            "stats": {
                "totalStudents": cnt_total,
                "firstYearStudents": cnt_first,
                "secondYearStudents": cnt_second,
                "thirdYearStudents": cnt_third,
                "totalFaculty": cnt_fac,
                "attendancePercentage": att_pct,
                "resultPassPercentage": pass_pct,
                "pendingFees": pending_fees,
                "departmentNotices": cnt_notices
            }
        })
    except Exception as e:
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/hod/dashboard-stats', handle_get_hod_dashboard_stats)

def handle_get_hods(handler_instance, query_params, body):
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
            SELECT h.id, h.department, h.name, h.qualification, h.experience, h.email, h.contact, h.faculty_id,
                   MAX(u.id) AS user_id, MAX(u.username) AS username,
                   COALESCE(MAX(u.status), h.status, 'Active') AS status
            FROM hods h
            LEFT JOIN users u ON (
                (h.faculty_id IS NOT NULL AND h.faculty_id != '' AND u.faculty_id = h.faculty_id)
                OR (h.email IS NOT NULL AND h.email != '' AND u.email = h.email AND u.role = 'HOD')
            )
        """
        group_order = " GROUP BY h.id, h.department, h.name, h.qualification, h.experience, h.email, h.contact, h.faculty_id, h.status ORDER BY h.department ASC"
        
        if is_admin(user):
            dept_filter = query_params.get("department", [None])[0]
            if dept_filter and dept_filter != "All":
                cursor.execute(base_query + " WHERE h.department = %s" + group_order, (dept_filter,))
            else:
                cursor.execute(base_query + group_order)
        else:
            cursor.execute(base_query + " WHERE h.department = %s" + group_order, (user_dept,))
            
        hods = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "hods": hods})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/hods', handle_get_hods)

def handle_post_hods(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Administrator can manage HODs"}, 403)

    dept = (body.get("department") or "").strip()
    f_id = (body.get("faculty_id") or body.get("facultyId") or f"HOD_{dept[:2].upper()}_{int(time.time()) % 10000}").strip()
    email = body.get("email", "").strip()
    contact = (body.get("contact", "") or body.get("mobile", "") or body.get("phone", "")).strip()
    name = body.get("name", "").strip()
    username = (body.get("username") or f_id).strip()
    status_val = body.get("status", "Active")
    qual = body.get("qualification", "Ph.D.").strip()
    exp = body.get("experience", "10 Years").strip()

    if not dept or not name:
        return handler_instance._send_json({"success": False, "message": "Department and Name are required!"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'Database connection error'}, 500)
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        # Check if an HOD record already exists for this department
        cursor.execute("SELECT id, name, faculty_id, email FROM hods WHERE department = %s", (dept,))
        existing_dept_hod = cursor.fetchone()

        official_email = email if email else f"hod_{dept[:2].lower()}@college.edu"
        official_contact = contact if contact else "9876543210"

        is_edit = body.get("is_edit", False)
        explicit_fid = (body.get("faculty_id") or body.get("facultyId") or "").strip()

        if existing_dept_hod and not is_edit and explicit_fid and explicit_fid != existing_dept_hod.get("faculty_id"):
            return handler_instance._send_json({
                "success": False,
                "message": f"An HOD ({existing_dept_hod['name']}) is already assigned to the {dept} department. Please edit or remove the existing HOD first."
            }, 400)

        if existing_dept_hod:
            f_id = existing_dept_hod.get("faculty_id") or f_id
            cursor.execute(
                """UPDATE hods 
                   SET name = %s, qualification = %s, experience = %s, email = %s, contact = %s, status = %s
                   WHERE department = %s""",
                (name, qual, exp, official_email, official_contact, status_val, dept)
            )

            # Update or create linked user account
            cursor.execute("SELECT id, username FROM users WHERE (department = %s AND role = 'HOD') OR faculty_id = %s OR (email = %s AND email != '')", (dept, f_id, official_email))
            existing_user = cursor.fetchone()
            if existing_user:
                new_pass = (body.get("password") or "").strip()
                if new_pass:
                    hashed = hash_password(new_pass)
                    cursor.execute(
                        "UPDATE users SET name = %s, email = %s, department = %s, faculty_id = %s, mobile = %s, status = %s, password = %s WHERE id = %s",
                        (name, official_email, dept, f_id, official_contact, status_val, hashed, existing_user["id"])
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET name = %s, email = %s, department = %s, faculty_id = %s, mobile = %s, status = %s WHERE id = %s",
                        (name, official_email, dept, f_id, official_contact, status_val, existing_user["id"])
                    )
                success_msg = f"HOD leadership updated successfully for {dept}!"
                cred_payload = None
            else:
                plain_pass = body.get("password") or generate_temp_password()
                hashed = hash_password(plain_pass)
                cursor.execute(
                    "INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, created_at, status, must_change_password, temp_password_created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)",
                    (username, hashed, "HOD", name, official_email, dept, f_id, official_contact, time.strftime('%Y-%m-%d %H:%M:%S'), status_val, time.strftime('%Y-%m-%d %H:%M:%S'))
                )
                success_msg = f"HOD assigned successfully for {dept}.\n\nHOD Username: {username}\nTemporary Password: {plain_pass}\n\nThe HOD can now log in directly using these credentials."
                cred_payload = {
                    "name": name,
                    "role": "HOD",
                    "department": dept,
                    "username": username,
                    "facultyId": f_id,
                    "temporaryPassword": plain_pass,
                    "loginUrl": "/login.html"
                }
        else:
            # Insert new HOD record
            cursor.execute(
                """INSERT INTO hods (department, name, qualification, experience, email, contact, faculty_id, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (dept, name, qual, exp, official_email, official_contact, f_id, status_val)
            )

            # Update or create linked user account
            cursor.execute("SELECT id, username FROM users WHERE (department = %s AND role = 'HOD') OR faculty_id = %s OR (email = %s AND email != '')", (dept, f_id, official_email))
            existing_user = cursor.fetchone()
            if existing_user:
                new_pass = (body.get("password") or "").strip()
                if new_pass:
                    hashed = hash_password(new_pass)
                    cursor.execute(
                        "UPDATE users SET name = %s, email = %s, department = %s, faculty_id = %s, mobile = %s, status = %s, password = %s WHERE id = %s",
                        (name, official_email, dept, f_id, official_contact, status_val, hashed, existing_user["id"])
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET name = %s, email = %s, department = %s, faculty_id = %s, mobile = %s, status = %s WHERE id = %s",
                        (name, official_email, dept, f_id, official_contact, status_val, existing_user["id"])
                    )
                success_msg = f"HOD assigned successfully for {dept}!"
                cred_payload = None
            else:
                plain_pass = body.get("password") or generate_temp_password()
                hashed = hash_password(plain_pass)
                cursor.execute(
                    "INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, created_at, status, must_change_password, temp_password_created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)",
                    (username, hashed, "HOD", name, official_email, dept, f_id, official_contact, time.strftime('%Y-%m-%d %H:%M:%S'), status_val, time.strftime('%Y-%m-%d %H:%M:%S'))
                )
                success_msg = f"HOD assigned successfully for {dept}.\n\nHOD Username: {username}\nTemporary Password: {plain_pass}\n\nThe HOD can now log in directly using these credentials."
                cred_payload = {
                    "name": name,
                    "role": "HOD",
                    "department": dept,
                    "username": username,
                    "facultyId": f_id,
                    "temporaryPassword": plain_pass,
                    "loginUrl": "/login.html"
                }

        conn.commit()
        return handler_instance._send_json({
            "success": True, 
            "message": success_msg, 
            "id": f_id, 
            "username": username, 
            "department": dept,
            "credentials": cred_payload
        })
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/hods', handle_post_hods)

def handle_delete_hods(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    if not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Administrator can delete HOD records"}, 403)

    item_id = query_params.get("id", [None])[0] or (body.get("id") if isinstance(body, dict) else None) or query_params.get("department", [None])[0] or (body.get("department") if isinstance(body, dict) else None)
    if not item_id:
        return handler_instance._send_json({"success": False, "message": "HOD ID or Department required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if str(item_id).isdigit():
            cursor.execute("SELECT * FROM hods WHERE id = %s OR department = %s OR faculty_id = %s", (int(item_id), item_id, item_id))
        else:
            cursor.execute("SELECT * FROM hods WHERE department = %s OR faculty_id = %s", (item_id, item_id))
            
        hod_records = cursor.fetchall()
        if not hod_records:
            return handler_instance._send_json({"success": True, "message": "HOD record not found or already deleted"})

        for hod_record in hod_records:
            if hod_record.get("email"):
                cursor.execute("DELETE FROM users WHERE email = %s AND role = 'HOD'", (hod_record["email"],))
            if hod_record.get("faculty_id"):
                cursor.execute("DELETE FROM users WHERE (faculty_id = %s OR username = %s) AND role = 'HOD'", (hod_record["faculty_id"], hod_record["faculty_id"]))
            if hod_record.get("department"):
                cursor.execute("DELETE FROM users WHERE department = %s AND role = 'HOD'", (hod_record["department"],))

        if str(item_id).isdigit():
            cursor.execute("DELETE FROM hods WHERE id = %s OR department = %s OR faculty_id = %s", (int(item_id), item_id, item_id))
        else:
            cursor.execute("DELETE FROM hods WHERE department = %s OR faculty_id = %s", (item_id, item_id))

        conn.commit()
        return handler_instance._send_json({"success": True, "message": "HOD record and login account deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Database deletion error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/hods', handle_delete_hods)
