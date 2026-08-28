import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user
from auth.utils import hash_password

def handle_get_hod_dashboard_stats(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    dept_override = query_params.get("department", [None])[0]
    if dept_override and dept_override != "All":
        target_dept = dept_override
    else:
        target_dept = user_dept if user_dept else "Computer Engineering"

    cursor.execute("SELECT COUNT(*) FROM students WHERE department = %s", (target_dept,))
    cnt_total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM students WHERE department = %s AND (year = 'First Year' OR year IS NULL OR year = '')", (target_dept,))
    cnt_first = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM students WHERE department = %s AND year = 'Second Year'", (target_dept,))
    cnt_second = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM students WHERE department = %s AND year = 'Third Year'", (target_dept,))
    cnt_third = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM faculty WHERE department = %s", (target_dept,))
    cnt_fac = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) FROM attendance WHERE department = %s", (target_dept,))
    att_row = cursor.fetchone()
    tot_att = att_row[0] or 0
    pres_att = att_row[1] or 0
    att_pct = round((pres_att / tot_att * 100), 1) if tot_att > 0 else 100.0

    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN r.status = 'Pass' THEN 1 ELSE 0 END) FROM results r JOIN students s ON r.student_id = s.id WHERE s.department = %s", (target_dept,))
    res_row = cursor.fetchone()
    tot_res = res_row[0] or 0
    pass_res = res_row[1] or 0
    pass_pct = round((pass_res / tot_res * 100), 1) if tot_res > 0 else 100.0

    cursor.execute("SELECT SUM(pending_fees) FROM fees WHERE department = %s", (target_dept,))
    pending_fees = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT COUNT(*) FROM notices WHERE department IN ('All', %s)", (target_dept,))
    cnt_notices = cursor.fetchone()[0]

    conn.close()
    handler_instance._send_json({
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
    return

#     udent ID Card Payload Endpoint

register_route('GET', '/api/hod/dashboard-stats', handle_get_hod_dashboard_stats)

def handle_get_hods(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role in ["HOD", "Faculty", "Student"]:
        cursor.execute("SELECT * FROM hods WHERE department = %s", (user_dept,))
    else: # Admin
        dept_filter = query_params.get("department", [None])[0]
        if dept_filter and dept_filter != "All":
            cursor.execute("SELECT * FROM hods WHERE department = %s", (dept_filter,))
        else:
            cursor.execute("SELECT * FROM hods")
    hods = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "hods": hods})
    return

#      Attendance Endpoint

register_route('GET', '/api/hods', handle_get_hods)

def handle_post_hods(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role not in ["Administrator", "Admin"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Only System Administrator can manage HODs"}, 403)
        return
    dept = body.get("department")
    f_id = body.get("faculty_id") or f"HOD{int(time.time()) % 100000}"
    email = body.get("email", "").strip()
    contact = body.get("contact", "").strip() or body.get("mobile", "").strip()
    name = body.get("name", "").strip()

    cursor.execute(
        """REPLACE INTO hods (department, name, qualification, experience, email, contact, faculty_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (dept, name, body.get("qualification"), body.get("experience"), email, contact, f_id)
    )
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if not cursor.fetchone():
        username = body.get("username") or (email.split("@")[0] if email else f"hod_{dept.lower().replace(' ', '_')}")
        plain_pass = body.get("password", "hod123")
        hashed = hash_password(plain_pass)
        cursor.execute(
            "INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (username, hashed, "HOD", name, email, dept, f_id, contact, time.strftime('%Y-%m-%d %H:%M:%S'))
        )

    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "HOD record saved successfully!"})
    return

#      Attendance CRUD

register_route('POST', '/api/hods', handle_post_hods)

def handle_delete_hods(handler_instance, query_params, body):
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


    if role not in ["Administrator", "Admin"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Only System Administrator can delete HODs"}, 403)
        return
    cursor.execute("DELETE FROM hods WHERE id = %s OR department = %s", (item_id, item_id))


register_route('DELETE', '/api/hods', handle_delete_hods)

