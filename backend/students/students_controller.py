import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod, is_faculty, is_student, is_student_assigned_to_faculty
from auth.utils import hash_password, generate_temp_password
from core.excel_utils import create_student_template_xlsx, parse_xlsx_bytes

# ----------------------------------------------------
# Student Excel Format Template Download
# ----------------------------------------------------
def handle_get_students_excel_template(handler_instance, query_params, body):
    xlsx_bytes = create_student_template_xlsx()
    handler_instance.send_response(200)
    handler_instance.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    handler_instance.send_header("Content-Disposition", 'attachment; filename="student_import_template.xlsx"')
    handler_instance.send_header("Content-Length", str(len(xlsx_bytes)))
    handler_instance.send_header("Access-Control-Allow-Origin", "*")
    handler_instance.end_headers()
    handler_instance.wfile.write(xlsx_bytes)

register_route('GET', '/api/students/excel-template', handle_get_students_excel_template)

# ----------------------------------------------------
# Students Query (Role-Scoped & IDOR Protected)
# ----------------------------------------------------
def handle_get_students(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')
    student_id = user.get('student_id')
    faculty_id = user.get('faculty_id')

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    dept_f = query_params.get("department", [None])[0]
    year_f = query_params.get("year", [None])[0]
    sem_f = query_params.get("semester", [None])[0]
    div_f = query_params.get("division", [None])[0]
    search_q = query_params.get("search", [None])[0]
    fac_f = query_params.get("faculty_id", [None])[0]
    assigned_only = query_params.get("assigned_only", [None])[0]

    try:
        if role == "Student":
            cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        else:
            sql = "SELECT DISTINCT s.* FROM students s"
            joins = []
            where_clauses = []
            params = []

            # Faculty role handling: Faculty can ONLY access assigned students
            if role == "Faculty":
                joins.append("JOIN faculty_students fs ON s.id = fs.student_id")
                where_clauses.append("fs.faculty_id = %s")
                params.append(faculty_id or "")
            elif role == "HOD":
                where_clauses.append("s.department = %s")
                params.append(user_dept)
            else: # Administrator
                if fac_f:
                    joins.append("JOIN faculty_students fs ON s.id = fs.student_id")
                    where_clauses.append("fs.faculty_id = %s")
                    params.append(fac_f)
                if dept_f and dept_f != "All":
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
        return handler_instance._send_json({"success": True, "students": students})
    except Exception as e:
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/students', handle_get_students)

# ----------------------------------------------------
# Faculty-Student Assignments Query
# ----------------------------------------------------
def handle_get_faculty_students(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')
    faculty_id = user.get('faculty_id')

    if role == "Student":
        return handler_instance._send_json({"success": False, "message": "Forbidden"}, 403)

    target_faculty_id = query_params.get("faculty_id", [faculty_id if role == "Faculty" else None])[0]
    if not target_faculty_id:
        return handler_instance._send_json({"success": False, "message": "faculty_id is required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if role == "Faculty" and target_faculty_id != faculty_id:
            return handler_instance._send_json({"success": False, "message": "Faculty can only access their own assigned students"}, 403)

        if role == "HOD":
            cursor.execute("SELECT department FROM faculty WHERE id = %s", (target_faculty_id,))
            fac_row = cursor.fetchone()
            if not fac_row or fac_row["department"] != user_dept:
                return handler_instance._send_json({"success": False, "message": "HOD can only view faculty in their department"}, 403)

        sql = """
            SELECT s.* FROM students s
            JOIN faculty_students fs ON s.id = fs.student_id
            WHERE fs.faculty_id = %s
            ORDER BY s.department, s.year, s.semester, s.division, s.roll_number
        """
        cursor.execute(sql, (target_faculty_id,))
        students = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "students": students, "faculty_id": target_faculty_id})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/faculty-students', handle_get_faculty_students)

# ----------------------------------------------------
# Student ID Card (IDOR Protected)
# ----------------------------------------------------
def handle_get_students_id_card(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')
    student_id = user.get('student_id')
    faculty_id = user.get('faculty_id')

    target_id = query_params.get("id", [student_id])[0]
    if role == "Student" and target_id != student_id:
        return handler_instance._send_json({"success": False, "message": "Students can only access their own ID card"}, 403)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM students WHERE id = %s", (target_id,))
        s_row = cursor.fetchone()
        if not s_row:
            return handler_instance._send_json({"success": False, "message": "Student record not found"}, 404)
        
        s = dict(s_row)
        if role == "Faculty":
            if not is_student_assigned_to_faculty(cursor, faculty_id, target_id):
                return handler_instance._send_json({"success": False, "message": "Faculty can only access assigned students' ID card"}, 403)

        if role == "HOD" and s["department"] != user_dept:
            return handler_instance._send_json({"success": False, "message": "Cannot access student ID card outside your department"}, 403)

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
            "dob": str(s.get("dob") or ""),
            "status": s.get("status", "Active")
        }
        return handler_instance._send_json({"success": True, "card": card})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/students/id-card', handle_get_students_id_card)

# ----------------------------------------------------
# HOD Department Summary
# ----------------------------------------------------
def handle_get_hod_student_summary(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')
    target_dept = user_dept if role in ["HOD", "Faculty", "Student"] else query_params.get("department", ["Computer Engineering"])[0]

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND (year = 'First Year' OR year IS NULL OR year = '')", (target_dept,))
        cnt_first = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND year = 'Second Year'", (target_dept,))
        cnt_second = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND year = 'Third Year'", (target_dept,))
        cnt_third = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s", (target_dept,))
        cnt_total = cursor.fetchone()['count']

        return handler_instance._send_json({
            "success": True,
            "department": target_dept,
            "summary": {
                "firstYear": cnt_first,
                "secondYear": cnt_second,
                "thirdYear": cnt_third,
                "total": cnt_total
            }
        })
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/hod/student-summary', handle_get_hod_student_summary)

# ----------------------------------------------------
# Add / Update Student (Admin / HOD Only)
# ----------------------------------------------------
def handle_post_students(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Permission denied: Only Admin and HOD can manage student records"}, 403)

    role = user.get('role')
    user_dept = user.get('department')

    s_id = (body.get("id") or body.get("studentId") or body.get("enrollmentNumber") or body.get("enrollment_number") or "").strip()
    roll_number = (body.get("rollNumber") or body.get("roll_number") or "").strip()
    dept = user_dept if is_hod(user) else (body.get("department") or "Computer Engineering").strip()
    mobile = (body.get("mobile", "") or body.get("phone", "")).strip()
    email = body.get("email", "").strip()
    name = body.get("name", "").strip()
    is_edit = body.get("is_edit", False)

    if not s_id or not roll_number or not name:
        return handler_instance._send_json({"success": False, "message": "Enrollment Number, Roll Number, and Name are required!"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if not is_edit:
            cursor.execute("SELECT id FROM students WHERE id = %s", (s_id,))
            if cursor.fetchone():
                return handler_instance._send_json({"success": False, "message": f"This Enrollment Number '{s_id}' is already registered. Please use a unique Enrollment Number."}, 400)

            cursor.execute("SELECT id FROM users WHERE username = %s OR student_id = %s", (s_id, s_id))
            if cursor.fetchone():
                return handler_instance._send_json({"success": False, "message": f"A login account already exists for Enrollment Number '{s_id}'."}, 400)

            cursor.execute("SELECT id FROM students WHERE roll_number = %s AND department = %s", (roll_number, dept))
            if cursor.fetchone():
                return handler_instance._send_json({"success": False, "message": f"Duplicate Error: Roll Number '{roll_number}' already exists in department '{dept}'!"}, 400)

        cursor.execute("SELECT id FROM students WHERE id = %s", (s_id,))
        existing_stu = cursor.fetchone()

        if existing_stu or is_edit:
            cursor.execute(
                """UPDATE students 
                   SET roll_number = %s, name = %s, email = %s, mobile = %s, gender = %s, dob = %s, department = %s,
                       year = %s, semester = %s, division = %s, admission_year = %s, address = %s, status = %s, photo = %s
                   WHERE id = %s""",
                (
                    roll_number,
                    name,
                    email if email else f"{s_id.lower()}@college.edu",
                    mobile if mobile else "9876543210",
                    body.get("gender", "Male"),
                    body.get("dob", "2005-01-01"),
                    dept,
                    body.get("year", "First Year"),
                    body.get("semester", "Semester 1"),
                    body.get("division", "A"),
                    body.get("admissionYear", "2026"),
                    body.get("address", "College Campus"),
                    body.get("status", "Active"),
                    body.get("photo", ""),
                    s_id
                )
            )
        else:
            cursor.execute(
                """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status, photo)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    s_id,
                    roll_number,
                    name,
                    email if email else f"{s_id.lower()}@college.edu",
                    mobile if mobile else "9876543210",
                    body.get("gender", "Male"),
                    body.get("dob", "2005-01-01"),
                    dept,
                    body.get("year", "First Year"),
                    body.get("semester", "Semester 1"),
                    body.get("division", "A"),
                    body.get("admissionYear", "2026"),
                    body.get("address", "College Campus"),
                    body.get("status", "Active"),
                    body.get("photo", "")
                )
            )

        cursor.execute("SELECT id FROM users WHERE student_id = %s OR username = %s", (s_id, s_id))
        existing_user = cursor.fetchone()
        if existing_user:
            cursor.execute(
                "UPDATE users SET name = %s, department = %s, email = %s, mobile = %s WHERE id = %s",
                (name, dept, email if email else f"{s_id.lower()}@college.edu", mobile if mobile else "9876543210", existing_user["id"])
            )
            success_msg = "Student record updated successfully!"
            cred_payload = None
        else:
            username = s_id  # Enrollment Number is the login identifier
            plain_pass = body.get("password") or generate_temp_password()
            hashed = hash_password(plain_pass)
            cursor.execute(
                "INSERT INTO users (username, password, role, name, email, department, student_id, mobile, created_at, status, must_change_password, temp_password_created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Active', 1, %s)",
                (username, hashed, "Student", name, email if email else f"{s_id.lower()}@college.edu", dept, s_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'), time.strftime('%Y-%m-%d %H:%M:%S'))
            )
            success_msg = f"Student created successfully.\n\nEnrollment Number: {s_id}\nTemporary Password: {plain_pass}\n\nThe student can now log in directly using the Enrollment Number and temporary password."
            cred_payload = {
                "name": name,
                "enrollmentNumber": s_id,
                "rollNumber": roll_number,
                "role": "Student",
                "department": dept,
                "username": s_id,
                "temporaryPassword": plain_pass,
                "loginUrl": "/login.html"
            }

        conn.commit()
        return handler_instance._send_json({
            "success": True, 
            "message": success_msg, 
            "id": s_id, 
            "enrollmentNumber": s_id,
            "credentials": cred_payload
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Database error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/students', handle_post_students)

# ----------------------------------------------------
# Bulk Student Add
# ----------------------------------------------------
def handle_post_students_bulk(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)

    user_dept = user.get('department')
    default_dept = user_dept if is_hod(user) else (body.get("department") or "Computer Engineering")
    default_year = body.get("year", "First Year")
    default_sem = body.get("semester", "Semester 1")
    default_div = body.get("division", "A")
    students_list = body.get("students", [])

    if not isinstance(students_list, list) or len(students_list) == 0:
        return handler_instance._send_json({"success": False, "message": "No valid student list provided for bulk insertion!"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    inserted_cnt = 0
    skipped_cnt = 0

    try:
        for s in students_list:
            s_id = (s.get("id") or s.get("studentId") or s.get("enrollmentNumber") or "").strip()
            r_num = (s.get("roll_number") or s.get("rollNumber") or "").strip()
            name = (s.get("name") or "").strip()
            if not s_id or not r_num or not name:
                continue

            dept = default_dept if is_hod(user) else (s.get("department") or default_dept)
            year = s.get("year") or default_year
            sem = s.get("semester") or default_sem
            div = s.get("division") or default_div
            email = s.get("email") or f"{s_id.lower()}@college.edu"
            mobile = s.get("mobile") or "9876543210"

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
                    dept, year, sem, div, s.get("admissionYear", "2026"), s.get("address", "College Campus")
                )
            )

            username = s_id
            temp_pass = generate_temp_password()
            hashed = hash_password(temp_pass)
            cursor.execute(
                "INSERT IGNORE INTO users (username, password, role, name, email, department, student_id, mobile, created_at, status, must_change_password, temp_password_created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Active', 1, %s)",
                (username, hashed, "Student", name, email, dept, s_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'), time.strftime('%Y-%m-%d %H:%M:%S'))
            )

            inserted_cnt += 1

        conn.commit()
        return handler_instance._send_json({
            "success": True,
            "message": f"Bulk insertion complete! Added {inserted_cnt} new students. Skipped {skipped_cnt} existing duplicates.",
            "inserted": inserted_cnt,
            "skipped": skipped_cnt
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/students/bulk', handle_post_students_bulk)

# ----------------------------------------------------
# Assign Students to Faculty
# ----------------------------------------------------
def handle_post_faculty_students_assign(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Permission denied: Only Admin and HOD can assign students"}, 403)

    fac_id = (body.get("faculty_id") or body.get("facultyId") or "").strip()
    stu_ids = body.get("student_ids") or body.get("studentIds") or []

    if not fac_id or not isinstance(stu_ids, list) or len(stu_ids) == 0:
        return handler_instance._send_json({"success": False, "message": "Faculty ID and student ID list are required!"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if is_hod(user):
            cursor.execute("SELECT department FROM faculty WHERE id = %s", (fac_id,))
            fac_row = cursor.fetchone()
            if not fac_row or fac_row["department"] != user.get("department"):
                return handler_instance._send_json({"success": False, "message": "HOD can only assign students to faculty in their department"}, 403)

        assigned_cnt = 0
        for sid in stu_ids:
            cursor.execute("INSERT IGNORE INTO faculty_students (faculty_id, student_id) VALUES (%s, %s)", (fac_id, sid))
            assigned_cnt += 1

        conn.commit()
        return handler_instance._send_json({"success": True, "message": f"Successfully assigned {assigned_cnt} students to faculty member '{fac_id}'."})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/faculty-students/assign', handle_post_faculty_students_assign)

def handle_post_faculty_students_remove(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)

    fac_id = (body.get("faculty_id") or body.get("facultyId") or "").strip()
    stu_id = body.get("student_id") or body.get("studentId")
    stu_ids = body.get("student_ids") or body.get("studentIds") or ([stu_id] if stu_id else [])

    if not fac_id or not stu_ids:
        return handler_instance._send_json({"success": False, "message": "Faculty ID and student ID are required!"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if is_hod(user):
            cursor.execute("SELECT department FROM faculty WHERE id = %s", (fac_id,))
            fac_row = cursor.fetchone()
            if not fac_row or fac_row["department"] != user.get("department"):
                return handler_instance._send_json({"success": False, "message": "HOD can only manage assignments in their department"}, 403)

        for sid in stu_ids:
            cursor.execute("DELETE FROM faculty_students WHERE faculty_id = %s AND student_id = %s", (fac_id, sid))

        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Student assignment removed successfully!"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/faculty-students/remove', handle_post_faculty_students_remove)

# ----------------------------------------------------
# Import Students from Excel (.xlsx)
# ----------------------------------------------------
def handle_post_students_import_excel(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')

    if not (is_admin(user) or is_hod(user)):
        return handler_instance._send_json({"success": False, "message": "Permission denied: Only Admin and HOD can import student records"}, 403)

    file_b64 = body.get("file_base64") or body.get("file")
    if not file_b64:
        return handler_instance._send_json({"success": False, "message": "No Excel file data provided"}, 400)

    if "," in file_b64:
        file_b64 = file_b64.split(",", 1)[1]

    try:
        raw_bytes = base64.b64decode(file_b64)
        rows = parse_xlsx_bytes(raw_bytes)
    except Exception as ex:
        return handler_instance._send_json({"success": False, "message": f"Failed to parse Excel file: {ex}"}, 400)

    if not rows or len(rows) <= 1:
        return handler_instance._send_json({"success": False, "message": "Excel file contains no data rows"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

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

    try:
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
            address = get_val(idx_address, "College Campus")
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

            if stu_id in seen_ids:
                dup_cnt += 1
                errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Duplicate Student ID '{stu_id}' inside Excel file"})
                continue

            if (roll_no, dept) in seen_rolls:
                dup_cnt += 1
                errors.append({"row": r_num, "student_id": stu_id, "name": name, "reason": f"Duplicate Roll Number '{roll_no}' in department '{dept}' inside Excel file"})
                continue

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

            username = stu_id
            temp_pass = generate_temp_password()
            hashed = hash_password(temp_pass)
            cursor.execute(
                "INSERT IGNORE INTO users (username, password, role, name, email, department, student_id, mobile, created_at, status, must_change_password, temp_password_created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Active', 1, %s)",
                (username, hashed, "Student", name, email, dept, stu_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'), time.strftime('%Y-%m-%d %H:%M:%S'))
            )

            added_cnt += 1

        conn.commit()
        return handler_instance._send_json({
            "success": True,
            "totalRecords": len(data_rows),
            "addedCount": added_cnt,
            "duplicateCount": dup_cnt,
            "failedCount": fail_cnt,
            "errors": errors
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/students/import-excel', handle_post_students_import_excel)

# ----------------------------------------------------
# Delete Student (Administrator Only)
# ----------------------------------------------------
def handle_delete_students(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    if not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Forbidden: Only Administrator can delete student records"}, 403)

    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Student ID required for deletion"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM students WHERE id = %s", (item_id,))
        stu = cursor.fetchone()
        if not stu:
            return handler_instance._send_json({"success": False, "message": "Student not found"}, 404)

        cursor.execute("DELETE FROM faculty_students WHERE student_id = %s", (item_id,))
        cursor.execute("DELETE FROM attendance WHERE student_id = %s", (item_id,))
        cursor.execute("DELETE FROM results WHERE student_id = %s", (item_id,))
        cursor.execute("DELETE FROM fees WHERE student_id = %s", (item_id,))
        cursor.execute("DELETE FROM users WHERE student_id = %s", (item_id,))
        cursor.execute("DELETE FROM students WHERE id = %s", (item_id,))

        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Student deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Database deletion error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/students', handle_delete_students)
