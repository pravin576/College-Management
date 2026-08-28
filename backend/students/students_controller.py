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
from core.excel_utils import create_student_template_xlsx, parse_xlsx_bytes


def handle_get_students_excel_template(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    xlsx_bytes = create_student_template_xlsx()
    handler_instance.send_response(200)
    handler_instance.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    handler_instance.send_header("Content-Disposition", 'attachment; filename="student_import_template.xlsx"')
    handler_instance.send_header("Content-Length", str(len(xlsx_bytes)))
    handler_instance.send_header("Access-Control-Allow-Origin", "*")
    handler_instance.end_headers()
    handler_instance.wfile.write(xlsx_bytes)
    return


register_route('GET', '/api/students/excel-template', handle_get_students_excel_template)

def handle_get_students(handler_instance, query_params, body):
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
    search_q = query_params.get("search", [None])[0]
    fac_f = query_params.get("faculty_id", [None])[0]
    assigned_only = query_params.get("assigned_only", [None])[0]

    if role == "Student":
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    else:
        sql = "SELECT DISTINCT s.* FROM students s"
        joins = []
        where_clauses = []
        params = []

        # Role & faculty assignment scoping
        target_fac = fac_f if fac_f else (faculty_id if (role == "Faculty" and (assigned_only == "true" or not dept_f)) else None)
        if target_fac:
            joins.append("JOIN faculty_students fs ON s.id = fs.student_id")
            where_clauses.append("fs.faculty_id = %s")
            params.append(target_fac)

        if role in ["HOD", "Faculty"] and not dept_f and not target_fac:
            where_clauses.append("s.department = %s")
            params.append(user_dept)
        elif dept_f and dept_f != "All":
            where_clauses.append("s.department = %s")
            params.append(dept_f)

        if year_f and year_f != "All":
            where_clauses.append("s.year = %s")
            params.append(year_f)

        if sem_f and sem_f != "All":
            where_clauses.append("s.semester = %s")
            params.append(sem_f)

        if div_f and div_f != "All":
            where_clauses.append("s.division = %s")
            params.append(div_f)

        if search_q:
            where_clauses.append("(s.name LIKE %s OR s.id LIKE %s OR s.roll_number LIKE %s OR s.email LIKE %s)")
            sq = f"%{search_q.strip()}%"
            params.extend([sq, sq, sq, sq])

        full_sql = sql
        if joins:
            full_sql += " " + " ".join(joins)
        if where_clauses:
            full_sql += " WHERE " + " AND ".join(where_clauses)
        full_sql += " ORDER BY s.department, s.year, s.semester, s.division, s.roll_number"

        cursor.execute(full_sql, tuple(params))

    students = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "students": students})
    return

#     culty-Student Assignments GET Endpoint

register_route('GET', '/api/students', handle_get_students)

def handle_get_faculty_students(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    target_faculty_id = query_params.get("faculty_id", [faculty_id if role == "Faculty" else None])[0]
    year_f = query_params.get("year", [None])[0]
    sem_f = query_params.get("semester", [None])[0]
    div_f = query_params.get("division", [None])[0]
    dept_f = query_params.get("department", [None])[0]

    if not target_faculty_id:
        conn.close()
        handler_instance._send_json({"success": False, "message": "faculty_id is required"}, 400)
        return

    sql = """
        SELECT s.* FROM students s
        JOIN faculty_students fs ON s.id = fs.student_id
        WHERE fs.faculty_id = %s
    """
    p = [target_faculty_id]
    if dept_f and dept_f != "All":
        sql += " AND s.department = %s"; p.append(dept_f)
    if year_f and year_f != "All":
        sql += " AND s.year = %s"; p.append(year_f)
    if sem_f and sem_f != "All":
        sql += " AND s.semester = %s"; p.append(sem_f)
    if div_f and div_f != "All":
        sql += " AND s.division = %s"; p.append(div_f)
    sql += " ORDER BY s.department, s.year, s.semester, s.division, s.roll_number"

    cursor.execute(sql, tuple(p))
    students = [dict(r) for r in cursor.fetchall()]
    conn.close()
    handler_instance._send_json({"success": True, "students": students, "faculty_id": target_faculty_id})
    return

#     mprehensive HOD Dashboard Dynamic Stats Endpoint

register_route('GET', '/api/faculty-students', handle_get_faculty_students)

def handle_get_students_id_card(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    target_id = query_params.get("id", [student_id])[0]
    cursor.execute("SELECT * FROM students WHERE id = %s", (target_id,))
    s_row = cursor.fetchone()
    if not s_row:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Student record not found"}, 404)
        return
    s = dict(s_row)
    card = {
        "collegeName": "Government Polytechnic, Awasari (Kh.)",
        "collegeSubtitle": "Autonomous Institute of Government of Maharashtra",
        "collegeLogo": "images/logo.jpg",
        "studentPhoto": s.get("photo") or "images/img1.jpg",
        "studentName": s["name"],
        "studentId": s["id"],
        "rollNumber": s["roll_number"],
        "department": s["department"],
        "year": s.get("year", "First Year"),
        "semester": s.get("semester", "Semester 1"),
        "division": s.get("division", "A"),
        "email": s["email"],
        "mobile": s["mobile"],
        "dob": s.get("dob", ""),
        "status": s.get("status", "Active")
    }
    conn.close()
    handler_instance._send_json({"success": True, "card": card})
    return

#     intable Fee Receipt Payload Endpoint

register_route('GET', '/api/students/id-card', handle_get_students_id_card)

def handle_get_hod_student_summary(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    target_dept = user_dept if role in ["HOD", "Faculty", "Student"] else query_params.get("department", ["Computer Science"])[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE department = %s AND (year = 'First Year' OR year IS NULL OR year = '')", (target_dept,))
    cnt_first = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE department = %s AND year = 'Second Year'", (target_dept,))
    cnt_second = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE department = %s AND year = 'Third Year'", (target_dept,))
    cnt_third = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE department = %s", (target_dept,))
    cnt_total = cursor.fetchone()[0]

    conn.close()
    handler_instance._send_json({
        "success": True,
        "department": target_dept,
        "summary": {
            "firstYear": cnt_first,
            "secondYear": cnt_second,
            "thirdYear": cnt_third,
            "total": cnt_total
        }
    })
    return

#      Faculty Endpoint

register_route('GET', '/api/hod/student-summary', handle_get_hod_student_summary)

def handle_post_students(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return

    s_id = body.get("id") or body.get("studentId")
    roll_number = body.get("rollNumber") or body.get("roll_number")
    dept = body.get("department") or (user_dept if role == "HOD" else "Computer Engineering")
    mobile = body.get("mobile", "").strip() or body.get("phone", "").strip()
    email = body.get("email", "").strip()
    name = body.get("name", "").strip()
    is_edit = body.get("is_edit", False)

    if not s_id or not roll_number or not name:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Student ID, Roll Number, and Name are required!"}, 400)
        return

    # Check duplicates if new student creation
    if not is_edit:
        cursor.execute("SELECT id FROM students WHERE id = %s", (s_id,))
        if cursor.fetchone():
            conn.close()
            handler_instance._send_json({"success": False, "message": f"Duplicate Error: Student ID '{s_id}' already exists!"}, 400)
            return

        cursor.execute("SELECT id FROM students WHERE roll_number = %s AND department = %s", (roll_number, dept))
        if cursor.fetchone():
            conn.close()
            handler_instance._send_json({"success": False, "message": f"Duplicate Error: Roll Number '{roll_number}' already exists in department '{dept}'!"}, 400)
            return

    cursor.execute(
        """REPLACE INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status, photo)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            s_id,
            roll_number,
            name,
            email if email else f"{s_id.lower()}@college.edu",
            mobile if mobile else "9876543210",
            body.get("gender", "Male"),
            body.get("dob", "2000-01-01"),
            dept,
            body.get("year", "First Year"),
            body.get("semester", "Semester 1"),
            body.get("division", "A"),
            body.get("admissionYear", "2026"),
            body.get("address", ""),
            body.get("status", "Active"),
            body.get("photo", "")
        )
    )

    cursor.execute("SELECT id FROM users WHERE student_id = %s OR email = %s", (s_id, email))
    if not cursor.fetchone():
        username = body.get("username") or (email.split("@")[0] if email else f"student_{s_id}")
        plain_pass = body.get("password", "student123")
        hashed = hash_password(plain_pass)
        cursor.execute(
            "INSERT INTO users (username, password, role, name, email, department, student_id, mobile, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (username, hashed, "Student", name, email if email else f"{s_id.lower()}@college.edu", dept, s_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
        )

    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "Student record saved successfully!", "id": s_id})
    return

#     lk Student Add Endpoint

register_route('POST', '/api/students', handle_post_students)

def handle_post_students_bulk(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return

    default_dept = body.get("department") or (user_dept if role == "HOD" else "Computer Engineering")
    default_year = body.get("year", "First Year")
    default_sem = body.get("semester", "Semester 1")
    default_div = body.get("division", "A")
    students_list = body.get("students", [])

    if not isinstance(students_list, list) or len(students_list) == 0:
        conn.close()
        handler_instance._send_json({"success": False, "message": "No valid student list provided for bulk insertion!"}, 400)
        return

    inserted_cnt = 0
    skipped_cnt = 0

    for s in students_list:
        s_id = s.get("id") or s.get("studentId")
        r_num = s.get("roll_number") or s.get("rollNumber")
        name = s.get("name")
        if not s_id or not r_num or not name:
            continue

        dept = s.get("department") or default_dept
        year = s.get("year") or default_year
        sem = s.get("semester") or default_sem
        div = s.get("division") or default_div
        email = s.get("email") or f"{s_id.lower()}@college.edu"
        mobile = s.get("mobile") or "9876543210"

        # Check duplicate Student ID or Roll Number in dept
        cursor.execute("SELECT id FROM students WHERE id = %s OR (roll_number = %s AND department = %s)", (s_id, r_num, dept))
        if cursor.fetchone():
            skipped_cnt += 1
            continue

        cursor.execute(
            """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Active')""",
            (
                s_id, r_num, name, email, mobile,
                s.get("gender", "Male"), s.get("dob", "2005-01-01"),
                dept, year, sem, div, s.get("admissionYear", "2026"), s.get("address", "Awasari")
            )
        )

        # Insert default user record
        username = s.get("username") or email.split("@")[0]
        hashed = hash_password("student123")
        cursor.execute(
            "INSERT IGNORE INTO users (username, password, role, name, email, department, student_id, mobile, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (username, hashed, "Student", name, email, dept, s_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
        )

        inserted_cnt += 1

    conn.commit()
    conn.close()
    handler_instance._send_json({
        "success": True,
        "message": f"Bulk insertion complete! Added {inserted_cnt} new students. Skipped {skipped_cnt} existing duplicates.",
        "inserted": inserted_cnt,
        "skipped": skipped_cnt
    })
    return

#     sign Students to Faculty Endpoint

register_route('POST', '/api/students/bulk', handle_post_students_bulk)

def handle_post_faculty_students_assign(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return

    fac_id = body.get("faculty_id") or body.get("facultyId")
    stu_ids = body.get("student_ids") or body.get("studentIds") or []

    if not fac_id or not isinstance(stu_ids, list) or len(stu_ids) == 0:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Faculty ID and student ID list are required!"}, 400)
        return

    assigned_cnt = 0
    for sid in stu_ids:
        cursor.execute("INSERT IGNORE INTO faculty_students (faculty_id, student_id) VALUES (%s, %s)", (fac_id, sid))
        assigned_cnt += 1

    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": f"Successfully assigned {assigned_cnt} students to faculty member '{fac_id}'."})
    return

#     move Student Assignment Endpoint

register_route('POST', '/api/faculty-students/assign', handle_post_faculty_students_assign)

def handle_post_faculty_students_remove(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return

    fac_id = body.get("faculty_id") or body.get("facultyId")
    stu_id = body.get("student_id") or body.get("studentId")
    stu_ids = body.get("student_ids") or body.get("studentIds") or ([stu_id] if stu_id else [])

    if not fac_id or not stu_ids:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Faculty ID and student ID are required!"}, 400)
        return

    for sid in stu_ids:
        cursor.execute("DELETE FROM faculty_students WHERE faculty_id = %s AND student_id = %s", (fac_id, sid))

    conn.commit()
    conn.close()
    handler_instance._send_json({"success": True, "message": "Student assignment removed successfully!"})
    return

#     port Students from Excel (.xlsx) Endpoint

register_route('POST', '/api/faculty-students/remove', handle_post_faculty_students_remove)

def handle_post_students_import_excel(handler_instance, query_params, body):
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
        handler_instance._send_json({"success": False, "message": "Students are not permitted to import data"}, 403)
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
    idx_roll = get_col_idx(["rollnumber", "rollno", "roll"], 1)
    idx_name = get_col_idx(["studentname", "fullname", "name"], 2)
    idx_email = get_col_idx(["email"], 3)
    idx_mobile = get_col_idx(["mobilenumber", "mobile", "phone", "contact"], 4)
    idx_gender = get_col_idx(["gender"], 5)
    idx_dob = get_col_idx(["dob", "dateofbirth", "birth"], 6)
    idx_dept = get_col_idx(["department", "dept"], 7)
    idx_year = get_col_idx(["year"], 8)
    idx_sem = get_col_idx(["semester", "sem"], 9)
    idx_div = get_col_idx(["division", "div"], 10)
    idx_adm_year = get_col_idx(["admissionyear", "admission"], 11)
    idx_address = get_col_idx(["address"], 12)
    idx_status = get_col_idx(["status"], 13)

    seen_ids = set()
    seen_rolls = set()
    added_cnt = 0
    dup_cnt = 0
    fail_cnt = 0
    errors = []

    for r_num, r in enumerate(data_rows, start=2):
        def get_val(idx, default=""):
            return r[idx].strip() if idx >= 0 and idx < len(r) else default

        stu_id = get_val(idx_id)
        roll_no = get_val(idx_roll)
        name = get_val(idx_name)
        email = get_val(idx_email)
        mobile = get_val(idx_mobile)
        gender = get_val(idx_gender, "Male")
        dob = get_val(idx_dob, "2005-01-01")
        dept = get_val(idx_dept, user_dept if role in ["HOD", "Faculty"] else "Computer Engineering")
        year = get_val(idx_year, "First Year")
        sem = get_val(idx_sem, "Semester 1")
        div = get_val(idx_div, "A")
        adm_year = get_val(idx_adm_year, "2026")
        address = get_val(idx_address, "Awasari")
        status_val = get_val(idx_status, "Active")

        # Validate Role Scoping
        if role in ["HOD", "Faculty"] and dept != user_dept:
            fail_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": f"Unauthorized department '{dept}'. Restricted to '{user_dept}'."})
            continue

        if not stu_id or not roll_no or not name:
            fail_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": "Missing required field (Student ID, Roll Number, or Student Name)"})
            continue

        # Internal Excel Duplicates
        if stu_id in seen_ids:
            dup_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Duplicate Student ID '{stu_id}' inside Excel file"})
            continue

        if (roll_no, dept) in seen_rolls:
            dup_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Duplicate Roll Number '{roll_no}' in department '{dept}' inside Excel file"})
            continue

        # DB Duplicates
        cursor.execute("SELECT id FROM students WHERE id = %s", (stu_id,))
        if cursor.fetchone():
            dup_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Student ID '{stu_id}' already exists in database"})
            continue

        cursor.execute("SELECT id FROM students WHERE roll_number = %s AND department = %s", (roll_no, dept))
        if cursor.fetchone():
            dup_cnt += 1
            errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Roll Number '{roll_no}' already exists in department '{dept}' in database"})
            continue

        seen_ids.add(stu_id)
        seen_rolls.add((roll_no, dept))

        if not email:
            email = f"{stu_id.lower()}@college.edu"
        if not mobile:
            mobile = "9876543210"

        cursor.execute(
            """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (stu_id, roll_no, name, email, mobile, gender, dob, dept, year, sem, div, adm_year, address, status_val)
        )

        username = email.split("@")[0]
        hashed = hash_password("student123")
        cursor.execute(
            "INSERT IGNORE INTO users (username, password, role, name, email, department, student_id, mobile, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (username, hashed, "Student", name, email, dept, stu_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'))
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

#     port Attendance from Excel (.xlsx) Endpoint

register_route('POST', '/api/students/import-excel', handle_post_students_import_excel)

def handle_delete_students(handler_instance, query_params, body):
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
    if role == "HOD":
        cursor.execute("SELECT department FROM students WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row or row[0] != user_dept:
            conn.close()
            handler_instance._send_json({"success": False, "message": "Cannot delete student from another department"}, 403)
            return
    cursor.execute("DELETE FROM students WHERE id = %s", (item_id,))
    cursor.execute("DELETE FROM users WHERE student_id = %s", (item_id,))
    cursor.execute("DELETE FROM attendance WHERE student_id = %s", (item_id,))
    cursor.execute("DELETE FROM results WHERE student_id = %s", (item_id,))
    cursor.execute("DELETE FROM fees WHERE student_id = %s", (item_id,))


register_route('DELETE', '/api/students', handle_delete_students)

