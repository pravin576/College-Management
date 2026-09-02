import base64
import urllib.parse
import datetime
import json
import time
import os
import re
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod, is_faculty, is_student, is_student_assigned_to_faculty
from core.excel_utils import create_results_template_xlsx, parse_xlsx_bytes

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.normpath(os.path.join(CUR_DIR, "..", "..", "frontend", "uploads"))
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR, exist_ok=True)

def handle_get_results_excel_template(handler_instance, query_params, body):
    xlsx_bytes = create_results_template_xlsx()
    handler_instance.send_response(200)
    handler_instance.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    handler_instance.send_header("Content-Disposition", 'attachment; filename="exam_results_template.xlsx"')
    handler_instance.send_header("Content-Length", str(len(xlsx_bytes)))
    handler_instance.send_header("Access-Control-Allow-Origin", "*")
    handler_instance.end_headers()
    handler_instance.wfile.write(xlsx_bytes)

register_route('GET', '/api/results/excel-template', handle_get_results_excel_template)

def handle_get_results(handler_instance, query_params, body):
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

    try:
        if role == "Student":
            cursor.execute("SELECT * FROM results WHERE student_id = %s ORDER BY semester, subject", (student_id,))
        elif role == "Faculty":
            cursor.execute(
                """SELECT r.* FROM results r
                   JOIN faculty_students fs ON r.student_id = fs.student_id
                   WHERE fs.faculty_id = %s
                   ORDER BY r.student_id, r.semester""",
                (faculty_id,)
            )
        elif role == "HOD":
            cursor.execute(
                """SELECT r.* FROM results r
                   JOIN students s ON r.student_id = s.id
                   WHERE s.department = %s
                   ORDER BY r.student_id, r.semester""",
                (user_dept,)
            )
        else: # Admin
            dept_filter = query_params.get("department", [None])[0]
            if dept_filter and dept_filter != "All":
                cursor.execute(
                    """SELECT r.* FROM results r
                       JOIN students s ON r.student_id = s.id
                       WHERE s.department = %s
                       ORDER BY r.student_id, r.semester""",
                    (dept_filter,)
                )
            else:
                cursor.execute("SELECT * FROM results ORDER BY student_id, semester")
        recs = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "results": recs})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/results', handle_get_results)

def handle_get_results_export(handler_instance, query_params, body):
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
    sem_f = query_params.get("semester", [None])[0]

    try:
        params = []
        if role == "Student":
            sql = "SELECT r.*, '' as department FROM results r WHERE r.student_id = %s"
            params.append(student_id)
        elif role == "Faculty":
            sql = """SELECT r.*, s.department FROM results r
                     JOIN students s ON r.student_id = s.id
                     JOIN faculty_students fs ON s.id = fs.student_id
                     WHERE fs.faculty_id = %s"""
            params.append(faculty_id)
        elif role == "HOD":
            sql = """SELECT r.*, s.department FROM results r
                     JOIN students s ON r.student_id = s.id
                     WHERE s.department = %s"""
            params.append(user_dept)
        else:
            sql = "SELECT r.*, s.department FROM results r LEFT JOIN students s ON r.student_id = s.id WHERE 1=1"
            if dept_f and dept_f != "All":
                sql += " AND s.department = %s"
                params.append(dept_f)

        if sem_f and sem_f != "All":
            sql += " AND r.semester = %s"
            params.append(sem_f)

        cursor.execute(sql, tuple(params))
        recs = cursor.fetchall()

        lines = ["Student ID,Student Name,Department,Semester,Subject,Internal Marks,End Sem Marks,Total Marks,Percentage,Grade,Status,Document File\n"]
        for r in recs:
            rd = dict(r)
            lines.append(f'"{rd.get("student_id")}","{rd.get("student_name")}","{rd.get("department","")}","{rd.get("semester")}","{rd.get("subject")}","{rd.get("internal_marks")}","{rd.get("end_sem_marks")}","{rd.get("total_marks")}","{rd.get("percentage")}%","{rd.get("grade")}","{rd.get("status")}","{rd.get("document","")}"\n')

        filename = f"exam_results_{int(time.time())}.csv"
        handler_instance.send_response(200)
        handler_instance.send_header("Content-type", "text/csv; charset=utf-8")
        handler_instance.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        handler_instance.send_header("Access-Control-Allow-Origin", "*")
        handler_instance.end_headers()
        handler_instance.wfile.write("".join(lines).encode("utf-8"))
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/results/export', handle_get_results_export)

def handle_post_results_import_excel(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')

    if role == "Student":
        return handler_instance._send_json({"success": False, "message": "Students are not permitted to import exam results"}, 403)

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
    idx_name = get_col_idx(["studentname", "fullname", "name"], 1)
    idx_dept = get_col_idx(["department", "dept"], 2)
    idx_sem = get_col_idx(["semester", "sem"], 3)
    idx_subject = get_col_idx(["subjectname", "subject"], 4)
    idx_internal = get_col_idx(["internalmarks", "internal"], 5)
    idx_endsem = get_col_idx(["endsemmarks", "endsem", "external"], 6)

    seen_results = set()
    added_cnt = 0
    dup_cnt = 0
    fail_cnt = 0
    errors = []

    try:
        for r_num, r in enumerate(data_rows, start=2):
            def get_val(idx, default=""):
                return r[idx].strip() if idx >= 0 and idx < len(r) else default

            stu_id = get_val(idx_id)
            name = get_val(idx_name)
            dept = get_val(idx_dept)
            sem = get_val(idx_sem, "Semester 1")
            subject = get_val(idx_subject)
            internal_str = get_val(idx_internal, "0")
            end_sem_str = get_val(idx_endsem, "0")

            if not stu_id or not subject:
                fail_cnt += 1
                errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": "Missing required field (Student ID or Subject)"})
                continue

            try:
                internal = float(internal_str)
                end_sem = float(end_sem_str)
            except ValueError:
                fail_cnt += 1
                errors.append({"row": r_num, "student_id": stu_id, "name": name or "N/A", "reason": f"Invalid marks values: internal='{internal_str}', end_sem='{end_sem_str}'"})
                continue

            cursor.execute("SELECT id, name, department FROM students WHERE id = %s", (stu_id,))
            stu_row = cursor.fetchone()
            if not stu_row:
                fail_cnt += 1
                errors.append({"row": r_num, "student_id": stu_id or "N/A", "name": name or "N/A", "reason": f"Student ID '{stu_id}' does not exist in student database"})
                continue

            target_name = name if name else (stu_row["name"] if stu_row else "Student")
            target_dept = dept if dept else (stu_row["department"] if stu_row else user_dept)

            if role == "Faculty":
                if not is_student_assigned_to_faculty(cursor, faculty_id, stu_id):
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": "Student is not assigned to you."})
                    continue
            elif role == "HOD":
                if target_dept != user_dept:
                    fail_cnt += 1
                    errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Unauthorized department '{target_dept}'. Restricted to '{user_dept}'."})
                    continue

            res_key = (stu_id, subject, sem)
            if res_key in seen_results:
                dup_cnt += 1
                errors.append({"row": r_num, "student_id": stu_id, "name": target_name, "reason": f"Duplicate result for '{stu_id}', subject '{subject}' on '{sem}' inside Excel"})
                continue

            seen_results.add(res_key)

            total = internal + end_sem
            percentage = round((total / 100.0) * 100.0, 1)
            grade = "A+" if percentage >= 85 else "A" if percentage >= 75 else "B" if percentage >= 60 else "C" if percentage >= 50 else "F"
            res_status = "Pass" if percentage >= 40 and end_sem >= 28 else "Fail"

            cursor.execute("SELECT id FROM results WHERE student_id = %s AND subject = %s AND semester = %s", (stu_id, subject, sem))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    """UPDATE results SET student_name=%s, internal_marks=%s, end_sem_marks=%s, total_marks=%s, percentage=%s, grade=%s, status=%s
                       WHERE id=%s""",
                    (target_name, internal, end_sem, total, percentage, grade, res_status, existing["id"])
                )
                dup_cnt += 1
            else:
                cursor.execute(
                    """INSERT INTO results (student_id, student_name, subject, semester, internal_marks, end_sem_marks, total_marks, percentage, grade, status, document)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '')""",
                    (stu_id, target_name, subject, sem, internal, end_sem, total, percentage, grade, res_status)
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

register_route('POST', '/api/results/import-excel', handle_post_results_import_excel)

def handle_post_results_upload_document(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    if is_student(user):
        return handler_instance._send_json({"success": False, "message": "Students cannot upload documents"}, 403)

    role = user.get('role')
    user_dept = user.get('department')
    faculty_id = user.get('faculty_id')

    res_id = body.get("result_id") or body.get("id")
    file_b64 = body.get("file_base64") or body.get("file")
    file_name = body.get("file_name", "marksheet.png")

    if not res_id or not file_b64:
        return handler_instance._send_json({"success": False, "message": "Result ID and file data are required"}, 400)

    if "," in file_b64:
        file_b64 = file_b64.split(",", 1)[1]

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT r.*, s.department FROM results r LEFT JOIN students s ON r.student_id = s.id WHERE r.id = %s", (res_id,))
        row = cursor.fetchone()
        if not row:
            return handler_instance._send_json({"success": False, "message": "Result record not found"}, 404)

        if role == "Faculty":
            if not is_student_assigned_to_faculty(cursor, faculty_id, row["student_id"]):
                return handler_instance._send_json({"success": False, "message": "Permission denied: Student not assigned to you"}, 403)
        elif role == "HOD":
            if row.get("department") != user_dept:
                return handler_instance._send_json({"success": False, "message": "Permission denied: Student not in your department"}, 403)

        raw_bytes = base64.b64decode(file_b64)
        ext = os.path.splitext(file_name)[1].lower() or ".png"
        safe_filename = f"marksheet_{res_id}_{int(time.time())}{ext}"
        target_filepath = os.path.join(UPLOADS_DIR, safe_filename)
        with open(target_filepath, "wb") as f:
            f.write(raw_bytes)

        doc_url = f"/uploads/{safe_filename}"
        cursor.execute("UPDATE results SET document = %s WHERE id = %s", (doc_url, res_id))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Marksheet document/photo uploaded successfully!", "document": doc_url})
    except Exception as ex:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Failed to save uploaded file: {ex}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/results/upload-document', handle_post_results_upload_document)

def handle_post_results(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or is_student(user):
        return handler_instance._send_json({"success": False, "message": "Permission denied: Students cannot enter exam results"}, 403)

    role = user.get('role')
    user_dept = user.get('department')
    faculty_id = user.get('faculty_id')

    res_id = body.get("id")
    s_id = (body.get("studentId") or body.get("student_id") or "").strip()
    s_name = (body.get("studentName") or body.get("student_name") or "Student").strip()
    subject = (body.get("subject") or "").strip()
    semester = body.get("semester", "Semester 1")
    internal = float(body.get("internalMarks", 0))
    end_sem = float(body.get("endSemMarks", 0))
    total = internal + end_sem
    percentage = round((total / 100.0) * 100, 1)
    grade = "A+" if percentage >= 90 else "A" if percentage >= 80 else "B" if percentage >= 70 else "C" if percentage >= 60 else "D" if percentage >= 40 else "F"
    res_status = "Pass" if percentage >= 40 else "Fail"

    if not s_id or not subject:
        return handler_instance._send_json({"success": False, "message": "Student ID and Subject are required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, name, department FROM students WHERE id = %s", (s_id,))
        stu_row = cursor.fetchone()
        if not stu_row:
            return handler_instance._send_json({"success": False, "message": "Student record not found"}, 404)

        if s_name == "Student" and stu_row.get("name"):
            s_name = stu_row["name"]

        if res_id:
            cursor.execute("SELECT r.*, s.department FROM results r LEFT JOIN students s ON r.student_id = s.id WHERE r.id = %s", (res_id,))
            existing_res = cursor.fetchone()
            if not existing_res:
                return handler_instance._send_json({"success": False, "message": "Result record not found"}, 404)

            if role == "Faculty":
                if not is_student_assigned_to_faculty(cursor, faculty_id, existing_res["student_id"]) or not is_student_assigned_to_faculty(cursor, faculty_id, s_id):
                    return handler_instance._send_json({"success": False, "message": "Permission denied: You can only modify results for assigned students"}, 403)
            elif role == "HOD":
                if existing_res.get("department") != user_dept or stu_row.get("department") != user_dept:
                    return handler_instance._send_json({"success": False, "message": "Permission denied: You can only modify results in your department"}, 403)

            cursor.execute(
                """UPDATE results SET student_id=%s, student_name=%s, subject=%s, semester=%s, internal_marks=%s, end_sem_marks=%s, total_marks=%s, percentage=%s, grade=%s, status=%s
                   WHERE id=%s""",
                (s_id, s_name, subject, semester, internal, end_sem, total, percentage, grade, res_status, res_id)
            )
        else:
            if role == "Faculty":
                if not is_student_assigned_to_faculty(cursor, faculty_id, s_id):
                    return handler_instance._send_json({"success": False, "message": "Permission denied: You can only create results for assigned students"}, 403)
            elif role == "HOD":
                if stu_row.get("department") != user_dept:
                    return handler_instance._send_json({"success": False, "message": "Permission denied: You can only create results for students in your department"}, 403)

            cursor.execute(
                """INSERT INTO results (student_id, student_name, subject, semester, internal_marks, end_sem_marks, total_marks, percentage, grade, status, document)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '')""",
                (s_id, s_name, subject, semester, internal, end_sem, total, percentage, grade, res_status)
            )
            res_id = cursor.lastrowid

        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Result record saved successfully!", "id": res_id})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/results', handle_post_results)

def handle_delete_results(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or is_student(user):
        return handler_instance._send_json({"success": False, "message": "Permission denied: Students cannot delete results"}, 403)

    role = user.get('role')
    user_dept = user.get('department')
    faculty_id = user.get('faculty_id')
    item_id = query_params.get("id", [None])[0] or body.get("id")

    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Result ID required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT r.*, s.department FROM results r LEFT JOIN students s ON r.student_id = s.id WHERE r.id = %s", (item_id,))
        row = cursor.fetchone()
        if not row:
            return handler_instance._send_json({"success": False, "message": "Result record not found"}, 404)

        if role == "Faculty":
            if not is_student_assigned_to_faculty(cursor, faculty_id, row["student_id"]):
                return handler_instance._send_json({"success": False, "message": "Permission denied: You can only delete results for assigned students"}, 403)
        elif role == "HOD":
            if row.get("department") != user_dept:
                return handler_instance._send_json({"success": False, "message": "Cannot delete exam result outside your department"}, 403)

        cursor.execute("DELETE FROM results WHERE id = %s", (item_id,))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Exam result deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/results', handle_delete_results)
