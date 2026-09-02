import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin
from auth.utils import hash_password

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
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if is_admin(user):
            dept_filter = query_params.get("department", [None])[0]
            if dept_filter and dept_filter != "All":
                cursor.execute("""
                    SELECT h.id, h.department, h.name, h.qualification, h.experience, h.email, h.contact, h.faculty_id,
                           u.id AS user_id, u.username,
                           COALESCE(u.status, h.status, 'Pending') AS status
                    FROM hods h
                    LEFT JOIN users u ON (h.faculty_id = u.faculty_id OR h.department = u.department OR (h.email = u.email AND h.email != ''))
                    WHERE h.department = %s
                """, (dept_filter,))
            else:
                cursor.execute("""
                    SELECT h.id, h.department, h.name, h.qualification, h.experience, h.email, h.contact, h.faculty_id,
                           u.id AS user_id, u.username,
                           COALESCE(u.status, h.status, 'Pending') AS status
                    FROM hods h
                    LEFT JOIN users u ON (h.faculty_id = u.faculty_id OR h.department = u.department OR (h.email = u.email AND h.email != ''))
                """)
        else:
            cursor.execute("""
                SELECT h.id, h.department, h.name, h.qualification, h.experience, h.email, h.contact, h.faculty_id,
                       u.id AS user_id, u.username,
                       COALESCE(u.status, h.status, 'Pending') AS status
                FROM hods h
                LEFT JOIN users u ON (h.faculty_id = u.faculty_id OR h.department = u.department OR (h.email = u.email AND h.email != ''))
                WHERE h.department = %s
            """, (user_dept,))
            
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
    f_id = (body.get("faculty_id") or f"HOD_{int(time.time()) % 100000}").strip()
    email = body.get("email", "").strip()
    contact = (body.get("contact", "") or body.get("mobile", "")).strip()
    name = body.get("name", "").strip()

    if not dept or not name:
        return handler_instance._send_json({"success": False, "message": "Department and Name are required!"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    status_val = body.get("status", "Active")

    try:
        cursor.execute(
            """REPLACE INTO hods (department, name, qualification, experience, email, contact, faculty_id, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (dept, name, body.get("qualification", "Ph.D."), body.get("experience", "10 Years"), email, contact, f_id, status_val)
        )
        cursor.execute("SELECT id FROM users WHERE email = %s OR faculty_id = %s OR (department = %s AND role = 'HOD')", (email, f_id, dept))
        existing_user = cursor.fetchone()
        if existing_user:
            cursor.execute(
                "UPDATE users SET name = %s, email = %s, department = %s, faculty_id = %s, mobile = %s, status = %s WHERE id = %s",
                (name, email, dept, f_id, contact, status_val, existing_user["id"])
            )
        else:
            username = body.get("username") or (email.split("@")[0] if email else f"hod_{dept.lower().replace(' ', '_')}")
            plain_pass = body.get("password", "hod123")
            hashed = hash_password(plain_pass)
            cursor.execute(
                "INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, created_at, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (username, hashed, "HOD", name, email, dept, f_id, contact, time.strftime('%Y-%m-%d %H:%M:%S'), status_val)
            )

        conn.commit()
        return handler_instance._send_json({"success": True, "message": "HOD record saved successfully!"})
    except Exception as e:
        conn.rollback()
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

    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        return handler_instance._send_json({"success": False, "message": "HOD ID or Department required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM hods WHERE id = %s OR department = %s", (item_id, item_id))
        hod_record = cursor.fetchone()
        if not hod_record:
            return handler_instance._send_json({"success": False, "message": "HOD record not found"}, 404)

        if hod_record.get("email"):
            cursor.execute("DELETE FROM users WHERE email = %s AND role = 'HOD'", (hod_record["email"],))
        if hod_record.get("faculty_id"):
            cursor.execute("DELETE FROM users WHERE faculty_id = %s AND role = 'HOD'", (hod_record["faculty_id"],))

        cursor.execute("DELETE FROM hods WHERE id = %s OR department = %s", (item_id, item_id))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "HOD record deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Database deletion error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/hods', handle_delete_hods)
