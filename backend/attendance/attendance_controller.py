import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user
from core.excel_utils import create_attendance_template_xlsx, parse_xlsx_bytes


def handle_get_attendance_excel_template(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    xlsx_bytes = create_attendance_template_xlsx()
    handler_instance.send_response(200)
    handler_instance.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    handler_instance.send_header("Content-Disposition", 'attachment; filename="attendance_import_template.xlsx"')
    handler_instance.send_header("Content-Length", str(len(xlsx_bytes)))
    handler_instance.send_header("Access-Control-Allow-Origin", "*")
    handler_instance.end_headers()
    handler_instance.wfile.write(xlsx_bytes)
    return


register_route('GET', '/api/attendance/excel-template', handle_get_attendance_excel_template)

def handle_get_attendance_export(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    dept_f = query_params.get("department", [None])[0]
    if role == "Student":
        cursor.execute("SELECT * FROM attendance WHERE student_id = %s ORDER BY date DESC", (student_id,))
    elif role in ["HOD", "Faculty"]:
        cursor.execute("SELECT * FROM attendance WHERE department = %s ORDER BY date DESC", (user_dept,))
    else:
        if dept_f and dept_f != "All":
            cursor.execute("SELECT * FROM attendance WHERE department = %s ORDER BY date DESC", (dept_f,))
        else:
            cursor.execute("SELECT * FROM attendance ORDER BY date DESC")
    recs = [dict(r) for r in cursor.fetchall()]
    conn.close()

    lines = ["ID,Student ID,Student Name,Subject,Date,Status,Department\n"]
    for r in recs:
        lines.append(f'"{r["id"]}","{r["student_id"]}","{r["student_name"]}","{r["subject"]}","{r["date"]}","{r["status"]}","{r["department"]}"\n')

    handler_instance.send_response(200)
    handler_instance.send_header("Content-type", "text/csv; charset=utf-8")
    handler_instance.send_header("Content-Disposition", 'attachment; filename="attendance_report.csv"')
    handler_instance.end_headers()
    handler_instance.wfile.write("".join(lines).encode("utf-8"))
    return

#     ports Data Endpoint

register_route('GET', '/api/attendance/export', handle_get_attendance_export)

def handle_get_attendance(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    dept_f = query_params.get("department", [None])[0]
    year_f = query_params.get("year", [None])[0]
    sem_f = query_params.get("semester", [None])[0]
    div_f = query_params.get("division", [None])[0]
    subj_f = query_params.get("subject", [None])[0]
    date_f = query_params.get("date", [None])[0]
    status_f = query_params.get("status", [None])[0]
    search_q = query_params.get("search", [None])[0]

    sql = "SELECT a.* FROM attendance a"
    where_clauses = []
    params = []

    if role == "Student":
        where_clauses.append("a.student_id = %s")
        params.append(student_id)
    else:
        if role in ["HOD", "Faculty"] and not dept_f:
            where_clauses.append("a.department = %s")
            params.append(user_dept)
        elif dept_f and dept_f != "All":
            where_clauses.append("a.department = %s")
            params.append(dept_f)

        if year_f and year_f != "All":
            where_clauses.append("a.year = %s")
            params.append(year_f)

        if sem_f and sem_f != "All":
            where_clauses.append("a.semester = %s")
            params.append(sem_f)

        if div_f and div_f != "All":
            where_clauses.append("a.division = %s")
            params.append(div_f)

        if subj_f and subj_f != "All":
            where_clauses.append("(a.subject LIKE %s OR a.subject_code LIKE %s)")
            params.extend([f"%{subj_f}%", f"%{subj_f}%"])

        if date_f:
            where_clauses.append("a.date = %s")
            params.append(date_f)

        if status_f and status_f != "All":
            where_clauses.append("a.status = %s")
            params.append(status_f)

        if search_q:
            where_clauses.append("(a.student_name LIKE %s OR a.student_id LIKE %s OR a.subject LIKE %s)")
            sq = f"%{search_q.strip()}%"
            params.extend([sq, sq, sq])

    full_sql = sql
    if where_clauses:
        full_sql += " WHERE " + " AND ".join(where_clauses)
    full_sql += " ORDER BY a.date DESC, a.student_id ASC"

    cursor.execute(full_sql, tuple(params))
    recs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "attendance": recs})
    return

#      Results Endpoint

register_route('GET', '/api/attendance', handle_get_attendance)

def handle_post_attendance_import_excel(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    if role == "Student":
        conn.close()
        handler_instance._send_json({"success": False, "message": "Students are not permitted to import attendance"}, 403)
        return

    file_b64 = body.get("file_base64") or body.get("file")
    if not file_b64:
        conn.close()
        handler_instance._send_json({"success": False, "message": "No Excel file data provided"}, 400)
        return

    if "," in file_b64:
        file_b64 = file_b64.split(",", 1)[1]

    try:
        raw_bytes = base64.b64decode(file_b64)
        rows = parse_xlsx_bytes(raw_bytes)
    except Exception as ex:
        conn.close()
        handler_instance._send_json({"success": False, "message": f"Failed to parse Excel file: {ex}"}, 400)
        return

    if not rows or len(rows) <= 1:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Excel file contains no data rows"}, 400)
        return

    header = [str(h).lower().replace(' ', '').replace('_', '') for h in rows[0]]
    data_rows = rows[1:]

    def get_col_idx(candidates, default_idx):
        for candidate in candidates:
            for i, h in enumerate(header):
                if candidate in h:
                    return i
        return default_idx if default_idx < len(header) else -1

    idx_id = get_col_idx(["studentid", "id"], 0)
    idx_name = get_col_idx(["studentname", "fullname", "name"], 1)
    idx_dept = get_col_idx(["department", "dept"], 2)
    idx_year = get_col_idx(["year"], 3)
    idx_sem = get_col_idx(["semester", "sem"], 4)
    idx_div = get_col_idx(["division", "div"], 5)
    idx_subject = get_col_idx(["subjectname", "subject"], 6)
    idx_code = get_col_idx(["subjectcode", "code"], 7)
    idx_date = get_col_idx(["date"], 8)
    idx_status = get_col_idx(["attendancestatus", "status"], 9)

    seen_att = set()
    added_cnt = 0
    dup_cnt = 0
    fail_cnt = 0
    errors = []

    for r_num, r in enumerate(data_rows, start=2):
        def get_val(idx, default=""):
            return r[idx].strip() if idx >= 0 and idx < len(r) else default

        stu_id = get_val(idx_id)
        name = get_val(idx_name)
        dept = get_val(idx_dept)
        year = get_val(idx_year, "First Year")
        sem = get_val(idx_sem, "Semester 1")
        div = get_val(idx_div, "A")
        subject = get_val(idx_subject)
        subj_code = get_val(idx_code)
        att_date = get_val(idx_date)
        att_status_raw = get_val(idx_status, "Present")

        if not stu_id or not subject or not att_date:
            fail_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": "Missing required field (Student ID, Subject, or Date)"})
            continue

        att_status = att_status_raw.capitalize()
        if att_status not in ["Present", "Absent", "Late"]:
            fail_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": name or "N/A", "reason": f"Invalid Attendance Status '{att_status_raw}'. Must be Present or Absent."})
            continue

        # Verify Student ID exists in DB
        cursor.execute("SELECT id, name, department, year, semester, division FROM students WHERE id = %s", (stu_id,))
        stu_row = cursor.fetchone()
        if not stu_row:
            fail_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": name or "N/A", "reason": f"Student ID '{stu_id}' does not exist in student database"})
            continue

        stu_db = dict(stu_row)
        target_dept = dept if dept else stu_db["department"]
        target_name = name if name else stu_db["name"]

        # Validate Role Scoping
        if role in ["HOD", "Faculty"] and target_dept != user_dept:
            fail_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Unauthorized department '{target_dept}'. Restricted to '{user_dept}'."})
            continue

        # Check internal Excel duplicate
        att_key = (stu_id, subject, att_date)
        if att_key in seen_att:
            dup_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Duplicate attendance for '{stu_id}', subject '{subject}' on '{att_date}' inside Excel"})
            continue

        # Check DB duplicate
        cursor.execute("SELECT id FROM attendance WHERE student_id = %s AND subject = %s AND date = %s", (stu_id, subject, att_date))
        if cursor.fetchone():
            dup_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Attendance record already exists for '{stu_id}', subject '{subject}' on '{att_date}' in database"})
            continue

        seen_att.add(att_key)

        cursor.execute(
            """INSERT INTO attendance (student_id, student_name, subject, date, status, faculty_id, department, year, semester, division, subject_code)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (stu_id, target_name, subject, att_date, att_status, user.get("faculty_id", ""), target_dept, year, sem, div, subj_code)
        )
        added_cnt += 1

    conn.commit()
    conn.close()
    handler_instance._send_json({
        "success": True,
        "totalRecords": len(data_rows),
        "addedCount": added_cnt,
        "duplicateCount": dup_cnt,
        "failedCount": fail_cnt,
        "errors": errors
    })
    return

#     port Error Log CSV/Excel Endpoint

register_route('POST', '/api/attendance/import-excel', handle_post_attendance_import_excel)

def handle_post_attendance(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Students cannot modify attendance records"}, 403)
        return
    att_id = body.get("id")
    s_id = body.get("studentId") or body.get("student_id")
    s_name = body.get("studentName") or body.get("student_name", "Student")
    dept = user_dept if role in ["HOD", "Faculty"] else body.get("department", "Computer Science")
    subject = body.get("subject", "General")
    att_date = body.get("date", time.strftime('%Y-%m-%d'))
    status = body.get("status", "Present")
    f_id = user.get("faculty_id") or user.get("username")

    if att_id:
        cursor.execute(
            "UPDATE attendance SET student_id=%s, student_name=%s, subject=%s, date=%s, status=%s, department=%s WHERE id=%s",
            (s_id, s_name, subject, att_date, status, dept, att_id)
        )
    else:
        cursor.execute(
            "INSERT INTO attendance (student_id, student_name, subject, date, status, faculty_id, department) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (s_id, s_name, subject, att_date, status, f_id, dept)
        )
    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "Attendance record saved successfully!"})
    return

#     . Results CRUD

register_route('POST', '/api/attendance', handle_post_attendance)

def handle_delete_attendance(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return
    if role in ["HOD", "Faculty"]:
        cursor.execute("SELECT department FROM attendance WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row or row[0] != user_dept:
            conn.close()
            handler_instance._send_json({"success": False, "message": "Cannot delete attendance outside your department"}, 403)
            return
    cursor.execute("DELETE FROM attendance WHERE id = %s", (item_id,))


register_route('DELETE', '/api/attendance', handle_delete_attendance)

