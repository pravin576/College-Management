import base64
import urllib.parse
import datetime
import json
import time
import os
import re
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, SESSIONS

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.normpath(os.path.join(CUR_DIR, "..", "..", "frontend", "uploads"))
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR, exist_ok=True)

# ----------------------------------------------------
# Health Check
# ----------------------------------------------------
def handle_get_health(handler_instance, query_params, body):
    handler_instance._send_json({"status": "ok", "message": "College ERP Python Server Running"})

register_route('GET', '/api/health', handle_get_health)

# ----------------------------------------------------
# Reports API (Role-Scoped)
# ----------------------------------------------------
def handle_get_reports_data(handler_instance, query_params, body):
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

    report_type = query_params.get("type", ["student"])[0]
    dept_f = query_params.get("department", [None])[0]
    year_f = query_params.get("year", [None])[0]
    search_q = query_params.get("search", [None])[0]

    data = []
    summary = {}

    try:
        if report_type == "student":
            if role == "Student":
                sql = "SELECT * FROM students WHERE id = %s"
                cursor.execute(sql, (student_id,))
            elif role == "Faculty":
                sql = """SELECT DISTINCT s.* FROM students s
                         JOIN faculty_students fs ON s.id = fs.student_id
                         WHERE fs.faculty_id = %s"""
                p = [faculty_id or ""]
                if year_f and year_f != "All":
                    sql += " AND s.year = %s"
                    p.append(year_f)
                if search_q:
                    sql += " AND (s.name LIKE %s OR s.id LIKE %s OR s.roll_number LIKE %s)"
                    p.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])
                sql += " ORDER BY s.department, s.year, s.name"
                cursor.execute(sql, tuple(p))
            else:
                sql = "SELECT * FROM students WHERE 1=1"
                p = []
                if role == "HOD":
                    sql += " AND department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = %s"
                    p.append(dept_f)
                if year_f and year_f != "All":
                    sql += " AND year = %s"
                    p.append(year_f)
                if search_q:
                    sql += " AND (name LIKE %s OR id LIKE %s OR roll_number LIKE %s)"
                    p.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])
                sql += " ORDER BY department, year, name"
                cursor.execute(sql, tuple(p))
            data = [dict(r) for r in cursor.fetchall()]
            summary = {"totalCount": len(data)}

        elif report_type == "faculty":
            if role == "Student":
                sql = "SELECT id, name, department, designation, email FROM faculty WHERE department = %s"
                cursor.execute(sql, (user_dept,))
            else:
                sql = "SELECT * FROM faculty WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = %s"
                    p.append(dept_f)
                cursor.execute(sql, tuple(p))
            data = [dict(r) for r in cursor.fetchall()]
            summary = {"totalCount": len(data)}

        elif report_type == "attendance":
            if role == "Student":
                sql = "SELECT * FROM attendance WHERE student_id = %s ORDER BY date DESC"
                cursor.execute(sql, (student_id,))
            elif role == "Faculty":
                sql = """SELECT DISTINCT a.* FROM attendance a
                         JOIN faculty_students fs ON a.student_id = fs.student_id
                         WHERE fs.faculty_id = %s ORDER BY a.date DESC"""
                cursor.execute(sql, (faculty_id or "",))
            else:
                sql = "SELECT * FROM attendance WHERE 1=1"
                p = []
                if role == "HOD":
                    sql += " AND department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = %s"
                    p.append(dept_f)
                sql += " ORDER BY date DESC"
                cursor.execute(sql, tuple(p))
            data = [dict(r) for r in cursor.fetchall()]
            summary = {"totalCount": len(data), "presentCount": sum(1 for d in data if d.get("status") == "Present")}

        elif report_type == "results":
            if role == "Student":
                sql = "SELECT * FROM results WHERE student_id = %s"
                cursor.execute(sql, (student_id,))
            elif role == "Faculty":
                sql = """SELECT r.*, s.department, s.year FROM results r
                         JOIN students s ON r.student_id = s.id
                         JOIN faculty_students fs ON s.id = fs.student_id
                         WHERE fs.faculty_id = %s"""
                cursor.execute(sql, (faculty_id or "",))
            else:
                sql = "SELECT r.*, s.department, s.year FROM results r JOIN students s ON r.student_id = s.id WHERE 1=1"
                p = []
                if role == "HOD":
                    sql += " AND s.department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND s.department = %s"
                    p.append(dept_f)
                cursor.execute(sql, tuple(p))
            data = [dict(r) for r in cursor.fetchall()]
            summary = {"totalCount": len(data), "passCount": sum(1 for d in data if d.get("status") == "Pass")}

        elif report_type == "fees":
            if role == "Student":
                sql = "SELECT * FROM fees WHERE student_id = %s"
                cursor.execute(sql, (student_id,))
            else:
                sql = "SELECT * FROM fees WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = %s"
                    p.append(dept_f)
                cursor.execute(sql, tuple(p))
            data = [dict(r) for r in cursor.fetchall()]
            summary = {
                "totalPaid": sum(float(d.get("paid_fees") or 0) for d in data),
                "totalPending": sum(float(d.get("pending_fees") or 0) for d in data)
            }

        return handler_instance._send_json({"success": True, "type": report_type, "summary": summary, "data": data})
    except Exception as e:
        return handler_instance._send_json({"success": False, "message": f"Error fetching report: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/reports/data', handle_get_reports_data)

def handle_get_reports_export(handler_instance, query_params, body):
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

    report_type = query_params.get("type", ["student"])[0]
    dept_f = query_params.get("department", [None])[0]

    lines = []
    filename = f"{report_type}_report.csv"

    try:
        if report_type == "student":
            if role == "Student":
                sql = "SELECT * FROM students WHERE id = %s"
                cursor.execute(sql, (student_id,))
            elif role == "Faculty":
                sql = """SELECT DISTINCT s.* FROM students s
                         JOIN faculty_students fs ON s.id = fs.student_id
                         WHERE fs.faculty_id = %s ORDER BY s.department, s.year, s.name"""
                cursor.execute(sql, (faculty_id or "",))
            else:
                sql = "SELECT * FROM students WHERE 1=1"
                p = []
                if role == "HOD":
                    sql += " AND department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = %s"
                    p.append(dept_f)
                cursor.execute(sql, tuple(p))
            rows = [dict(r) for r in cursor.fetchall()]
            lines.append("Enrollment Number,Roll Number,Name,Department,Year,Semester,Division,Email,Mobile,Status\n")
            for r in rows:
                lines.append(f'"{r["id"]}","{r["roll_number"]}","{r["name"]}","{r["department"]}","{r.get("year","")}","{r["semester"]}","{r["division"]}","{r["email"]}","{r["mobile"]}","{r.get("status","")}"\n')

        elif report_type == "faculty":
            if role == "Student":
                sql = "SELECT id, name, department, designation, email, mobile, experience FROM faculty WHERE department = %s ORDER BY name ASC"
                cursor.execute(sql, (user_dept,))
            else:
                sql = "SELECT id, name, department, designation, email, mobile, experience FROM faculty WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = %s"
                    p.append(dept_f)
                sql += " ORDER BY department, name ASC"
                cursor.execute(sql, tuple(p))
            rows = [dict(r) for r in cursor.fetchall()]
            lines.append("Faculty ID,Name,Department,Designation,Email,Mobile,Experience\n")
            for r in rows:
                lines.append(f'"{r["id"]}","{r["name"]}","{r["department"]}","{r["designation"]}","{r["email"]}","{r["mobile"]}","{r.get("experience","")}"\n')

        elif report_type == "attendance":
            if role == "Student":
                sql = "SELECT * FROM attendance WHERE student_id = %s ORDER BY date DESC"
                cursor.execute(sql, (student_id,))
            elif role == "Faculty":
                sql = """SELECT DISTINCT a.* FROM attendance a
                         JOIN faculty_students fs ON a.student_id = fs.student_id
                         WHERE fs.faculty_id = %s ORDER BY a.date DESC"""
                cursor.execute(sql, (faculty_id or "",))
            else:
                sql = "SELECT * FROM attendance WHERE 1=1"
                p = []
                if role == "HOD":
                    sql += " AND department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = %s"
                    p.append(dept_f)
                sql += " ORDER BY date DESC"
                cursor.execute(sql, tuple(p))
            rows = [dict(r) for r in cursor.fetchall()]
            lines.append("ID,Student ID,Student Name,Department,Subject,Date,Status\n")
            for r in rows:
                lines.append(f'"{r["id"]}","{r["student_id"]}","{r["student_name"]}","{r.get("department","")}","{r["subject"]}","{r["date"]}","{r["status"]}"\n')

        elif report_type == "results":
            if role == "Student":
                sql = "SELECT * FROM results WHERE student_id = %s"
                cursor.execute(sql, (student_id,))
            elif role == "Faculty":
                sql = """SELECT r.*, s.department, s.year FROM results r
                         JOIN students s ON r.student_id = s.id
                         JOIN faculty_students fs ON s.id = fs.student_id
                         WHERE fs.faculty_id = %s ORDER BY r.student_id ASC"""
                cursor.execute(sql, (faculty_id or "",))
            else:
                sql = "SELECT r.*, s.department, s.year FROM results r JOIN students s ON r.student_id = s.id WHERE 1=1"
                p = []
                if role == "HOD":
                    sql += " AND s.department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND s.department = %s"
                    p.append(dept_f)
                sql += " ORDER BY s.department, r.student_id ASC"
                cursor.execute(sql, tuple(p))
            rows = [dict(r) for r in cursor.fetchall()]
            lines.append("Student ID,Student Name,Department,Subject,Semester,Internal Marks,End Sem Marks,Total Marks,Percentage,Grade,Status\n")
            for r in rows:
                lines.append(f'"{r["student_id"]}","{r["student_name"]}","{r.get("department","")}","{r["subject"]}","{r["semester"]}","{r["internal_marks"]}","{r["end_sem_marks"]}","{r["total_marks"]}","{r["percentage"]}","{r["grade"]}","{r["status"]}"\n')

        elif report_type == "fees":
            if role == "Student":
                sql = "SELECT * FROM fees WHERE student_id = %s"
                cursor.execute(sql, (student_id,))
            else:
                sql = "SELECT * FROM fees WHERE 1=1"
                p = []
                if role in ["HOD", "Faculty"]:
                    sql += " AND department = %s"
                    p.append(user_dept)
                elif dept_f and dept_f != "All":
                    sql += " AND department = %s"
                    p.append(dept_f)
                cursor.execute(sql, tuple(p))
            rows = [dict(r) for r in cursor.fetchall()]
            lines.append("Enrollment Number,Student Name,Department,Total Fees,Paid Fees,Pending Fees,Status,Payment Date\n")
            for r in rows:
                lines.append(f'"{r["student_id"]}","{r["student_name"]}","{r["department"]}","{r["total_fees"]}","{r["paid_fees"]}","{r["pending_fees"]}","{r["payment_status"]}","{r.get("payment_date","")}"\n')
        else:
            lines.append("Report Export Data\n")

        handler_instance.send_response(200)
        handler_instance.send_header("Content-type", "text/csv; charset=utf-8")
        handler_instance.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        handler_instance.end_headers()
        handler_instance.wfile.write("".join(lines).encode("utf-8"))
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/reports/export', handle_get_reports_export)

# ----------------------------------------------------
# Dashboard Stats (Role-Scoped)
# ----------------------------------------------------
def handle_post_dashboard_stats(handler_instance, query_params, body):
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

    stats = {}
    try:
        if is_admin(user):
            cursor.execute("SELECT COUNT(*) as count FROM students")
            stats["totalStudents"] = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM faculty")
            stats["totalFaculty"] = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM hods")
            stats["totalHODs"] = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM departments")
            stats["totalDepartments"] = cursor.fetchone()["count"]
            cursor.execute("SELECT SUM(paid_fees) as paid, SUM(pending_fees) as pending FROM fees")
            row = cursor.fetchone()
            stats["totalPaidFees"] = float(row["paid"] or 0)
            stats["totalPendingFees"] = float(row["pending"] or 0)
            cursor.execute("SELECT COUNT(*) as count FROM notices")
            stats["totalNotices"] = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = 'Pending'")
            stats["pendingUsers"] = cursor.fetchone()["count"]

            # College-wide Attendance & Results Summary
            cursor.execute("SELECT COUNT(*) as total_att, SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as pres_att FROM attendance")
            att_row = cursor.fetchone()
            tot_att = (att_row['total_att'] if att_row else 0) or 0
            pres_att = (att_row['pres_att'] if att_row else 0) or 0
            stats["attendancePercentage"] = round((float(pres_att) / float(tot_att) * 100), 1) if tot_att > 0 else None

            cursor.execute("SELECT COUNT(*) as total_res, SUM(CASE WHEN status = 'Pass' THEN 1 ELSE 0 END) as pass_res FROM results")
            res_row = cursor.fetchone()
            tot_res = (res_row['total_res'] if res_row else 0) or 0
            pass_res = (res_row['pass_res'] if res_row else 0) or 0
            stats["resultPassPercentage"] = round((float(pass_res) / float(tot_res) * 100), 1) if tot_res > 0 else None

            # Query list of pending users for Admin Quick Action queue
            cursor.execute("SELECT id, username, name, role, department, created_at, status FROM users WHERE status = 'Pending' ORDER BY created_at DESC LIMIT 10")
            stats["pendingUsersList"] = [dict(r) for r in cursor.fetchall()]

            # Fetch Department-Wise Performance & Staff Matrix
            cursor.execute("SELECT id, name, code FROM departments ORDER BY name ASC")
            dept_rows = cursor.fetchall()
            dept_stats = []
            for d in dept_rows:
                d_name = d["name"]
                cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s", (d_name,))
                s_cnt = cursor.fetchone()["count"]
                cursor.execute("SELECT COUNT(*) as count FROM faculty WHERE department = %s", (d_name,))
                f_cnt = cursor.fetchone()["count"]
                cursor.execute("SELECT name FROM hods WHERE department = %s LIMIT 1", (d_name,))
                hod_row = cursor.fetchone()
                hod_name = hod_row["name"] if hod_row else "Not Assigned"
                cursor.execute("SELECT SUM(paid_fees) as paid, SUM(pending_fees) as pending FROM fees WHERE department = %s", (d_name,))
                f_row = cursor.fetchone()
                paid_amt = float(f_row["paid"] or 0) if f_row else 0.0
                pending_amt = float(f_row["pending"] or 0) if f_row else 0.0

                cursor.execute("SELECT COUNT(*) as total_att, SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as pres_att FROM attendance WHERE department = %s", (d_name,))
                att_row = cursor.fetchone()
                tot_att = (att_row['total_att'] if att_row else 0) or 0
                pres_att = (att_row['pres_att'] if att_row else 0) or 0
                att_pct = round((float(pres_att) / float(tot_att) * 100), 1) if tot_att > 0 else None

                dept_stats.append({
                    "department": d_name,
                    "code": d.get("code") or d_name[:2].upper(),
                    "students": s_cnt,
                    "faculty": f_cnt,
                    "hod": hod_name,
                    "paidFees": paid_amt,
                    "pendingFees": pending_amt,
                    "attendanceRate": att_pct
                })
            stats["departmentStats"] = dept_stats

        elif role == "HOD":
            stats["isDepartmentView"] = True
            stats["department"] = user_dept or "Computer Engineering"
            target_dept = user_dept or "Computer Engineering"

            cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s", (target_dept,))
            stats["totalStudents"] = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND (year = 'First Year' OR year IS NULL OR year = '')", (target_dept,))
            stats["firstYearStudents"] = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND year = 'Second Year'", (target_dept,))
            stats["secondYearStudents"] = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s AND year = 'Third Year'", (target_dept,))
            stats["thirdYearStudents"] = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM faculty WHERE department = %s", (target_dept,))
            stats["totalFaculty"] = cursor.fetchone()["count"]
            stats["totalHODs"] = 1
            cursor.execute("SELECT COUNT(*) as count FROM notices WHERE department = %s OR department = 'All'", (target_dept,))
            stats["totalNotices"] = cursor.fetchone()["count"]
            cursor.execute("SELECT SUM(paid_fees) as paid, SUM(pending_fees) as pending FROM fees WHERE department = %s", (target_dept,))
            row = cursor.fetchone()
            stats["totalPaidFees"] = float(row["paid"] or 0) if row else 0.0
            stats["totalPendingFees"] = float(row["pending"] or 0) if row else 0.0

            cursor.execute("SELECT COUNT(*) as total_att, SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as pres_att FROM attendance WHERE department = %s", (target_dept,))
            att_row = cursor.fetchone()
            tot_att = (att_row['total_att'] if att_row else 0) or 0
            pres_att = (att_row['pres_att'] if att_row else 0) or 0
            stats["attendancePercentage"] = round((float(pres_att) / float(tot_att) * 100), 1) if tot_att > 0 else None

            cursor.execute("SELECT COUNT(*) as total_res, SUM(CASE WHEN r.status = 'Pass' THEN 1 ELSE 0 END) as pass_res FROM results r JOIN students s ON r.student_id = s.id WHERE s.department = %s", (target_dept,))
            res_row = cursor.fetchone()
            tot_res = (res_row['total_res'] if res_row else 0) or 0
            pass_res = (res_row['pass_res'] if res_row else 0) or 0
            stats["resultPassPercentage"] = round((float(pass_res) / float(tot_res) * 100), 1) if tot_res > 0 else None

            # List of department faculty
            cursor.execute("SELECT id, name, designation, email, mobile, experience FROM faculty WHERE department = %s ORDER BY name ASC", (target_dept,))
            stats["departmentFaculty"] = [dict(r) for r in cursor.fetchall()]

            # Recent department students
            cursor.execute("SELECT id, name, roll_number, year, semester, email, mobile FROM students WHERE department = %s ORDER BY id DESC LIMIT 5", (target_dept,))
            stats["recentStudents"] = [dict(r) for r in cursor.fetchall()]

        elif role == "Faculty":
            fac_id = faculty_id or ""
            if fac_id:
                cursor.execute("SELECT COUNT(*) as count FROM faculty_students WHERE faculty_id = %s", (fac_id,))
                assigned_cnt = cursor.fetchone()["count"]
                stats["totalStudents"] = assigned_cnt
                stats["assignedStudentsCount"] = assigned_cnt
            else:
                stats["totalStudents"] = 0
                stats["assignedStudentsCount"] = 0
            cursor.execute("SELECT COUNT(*) as count FROM notices WHERE department = %s OR department = 'All'", (user_dept,))
            stats["totalNotices"] = cursor.fetchone()["count"]

        elif role == "Student":
            cursor.execute("SELECT COUNT(*) as count FROM notices WHERE (department = %s OR department = 'All') AND (target_role = 'Student' OR target_role = 'All')", (user_dept,))
            stats["totalNotices"] = cursor.fetchone()["count"]
            cursor.execute("SELECT total_fees, paid_fees, pending_fees FROM fees WHERE student_id = %s", (student_id,))
            fee_row = cursor.fetchone()
            if fee_row:
                stats["totalFees"] = float(fee_row["total_fees"])
                stats["paidFees"] = float(fee_row["paid_fees"])
                stats["pendingFees"] = float(fee_row["pending_fees"])
            cursor.execute("SELECT AVG(percentage) as avg_pct FROM results WHERE student_id = %s", (student_id,))
            avg_row = cursor.fetchone()
            stats["avgPercentage"] = round(float(avg_row["avg_pct"]), 1) if avg_row and avg_row["avg_pct"] else 0.0

        return handler_instance._send_json({"success": True, "stats": stats})
    except Exception as e:
        return handler_instance._send_json({"success": False, "message": f"Stats error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/dashboard/stats', handle_post_dashboard_stats)

# ----------------------------------------------------
# Multipart File Upload (Protected against path traversal)
# ----------------------------------------------------
def handle_post_upload(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Authentication required"}, 401)

    content_type = handler_instance.headers.get("Content-Type", "")
    content_length = int(handler_instance.headers.get("Content-Length", 0))
    raw_body = getattr(handler_instance, "_raw_body", b"")
    if not raw_body and content_length > 0:
        try:
            raw_body = handler_instance.rfile.read(content_length)
        except Exception:
            raw_body = b""

    try:
        if "boundary=" in content_type:
            boundary_val = content_type.split("boundary=")[1].split(";")[0].strip().strip('"').strip("'")
            boundary = boundary_val.encode('utf-8')
            delimiter = b"--" + boundary
            parts = raw_body.split(delimiter)
            for part in parts:
                if b"filename=" in part:
                    if part.startswith(b"\r\n"):
                        part = part[2:]
                    if b"\r\n\r\n" in part:
                        headers_part, file_data = part.split(b"\r\n\r\n", 1)
                        if file_data.endswith(b"\r\n"):
                            file_data = file_data[:-2]
                        elif file_data.endswith(b"\r\n--"):
                            file_data = file_data[:-4]

                        headers_str = headers_part.decode('utf-8', errors='ignore')
                        fn_match = re.search(r'filename=["\']?([^"\'\r\n;]+)["\']?', headers_str)
                        raw_fn = fn_match.group(1).strip() if fn_match else f"upload_{int(time.time())}.dat"
                        safe_basename = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(raw_fn))
                        safe_fn = f"{int(time.time())}_{safe_basename}"
                        out_path = os.path.join(UPLOADS_DIR, safe_fn)
                        with open(out_path, "wb") as f:
                            f.write(file_data)
                        return handler_instance._send_json({"success": True, "filePath": f"/uploads/{safe_fn}", "fileName": safe_fn})

        filename = handler_instance.headers.get("X-File-Name", f"file_{int(time.time())}.dat")
        safe_basename = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(filename))
        safe_fn = f"{int(time.time())}_{safe_basename}"
        out_path = os.path.join(UPLOADS_DIR, safe_fn)
        with open(out_path, "wb") as f:
            f.write(raw_body)
        return handler_instance._send_json({"success": True, "filePath": f"/uploads/{safe_fn}", "fileName": safe_fn})
    except Exception as ex:
        return handler_instance._send_json({"success": False, "message": f"Upload error: {str(ex)}"}, 500)

register_route('POST', '/api/upload', handle_post_upload)

# ----------------------------------------------------
# User Management & Pending Approvals (Admin Only)
# ----------------------------------------------------
def handle_get_pending_users(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Only Administrators can view pending user authorizations"}, 403)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, username, name, role, email, mobile, department, student_id, faculty_id, status, created_at FROM users WHERE status = 'Pending' ORDER BY created_at DESC")
        pending_users = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "users": pending_users})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/admin/pending-users', handle_get_pending_users)
register_route('GET', '/api/users/pending', handle_get_pending_users)

def handle_post_approve_user(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Only Administrators can approve user accounts"}, 403)
        
    user_id = body.get("user_id") or body.get("id") or query_params.get("user_id", [None])[0] or query_params.get("id", [None])[0]
    username = body.get("username")
    email = body.get("email")
    faculty_id = body.get("faculty_id") or body.get("facultyId")
    student_id = body.get("student_id") or body.get("studentId")
    department = body.get("department")
    
    if not user_id and not username and not email and not faculty_id and not student_id and not department:
        return handler_instance._send_json({"success": False, "message": "User identifier required for approval"}, 400)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        target_user = None
        if user_id:
            if str(user_id).isdigit():
                cursor.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
                target_user = cursor.fetchone()
            if not target_user:
                cursor.execute("SELECT * FROM users WHERE faculty_id = %s OR student_id = %s OR username = %s OR email = %s", (user_id, user_id, user_id, user_id))
                target_user = cursor.fetchone()

        if not target_user and username:
            cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, username))
            target_user = cursor.fetchone()

        if not target_user and email:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            target_user = cursor.fetchone()

        if not target_user and faculty_id:
            cursor.execute("SELECT * FROM users WHERE faculty_id = %s", (faculty_id,))
            target_user = cursor.fetchone()

        if not target_user and student_id:
            cursor.execute("SELECT * FROM users WHERE student_id = %s", (student_id,))
            target_user = cursor.fetchone()

        if not target_user and department:
            cursor.execute("SELECT * FROM users WHERE role = 'HOD' AND LOWER(TRIM(department)) = LOWER(TRIM(%s))", (department,))
            target_user = cursor.fetchone()

        if not target_user:
            return handler_instance._send_json({"success": False, "message": "User not found for authorization approval"}, 404)
            
        # Update user status to Active in users table using the exact users.id
        cursor.execute("UPDATE users SET status = 'Active' WHERE id = %s", (target_user["id"],))
        
        # Update status in corresponding role table
        role = target_user.get("role")
        fac_id = target_user.get("faculty_id") or ""
        u_email = target_user.get("email") or ""
        u_dept = target_user.get("department") or ""
        stu_id = target_user.get("student_id") or ""

        if role == "Faculty":
            if fac_id:
                cursor.execute("UPDATE faculty SET status = 'Active' WHERE id = %s", (fac_id,))
            elif u_email:
                cursor.execute("UPDATE faculty SET status = 'Active' WHERE email = %s", (u_email,))
        elif role == "HOD":
            if fac_id:
                cursor.execute("UPDATE hods SET status = 'Active' WHERE faculty_id = %s", (fac_id,))
            elif u_email:
                cursor.execute("UPDATE hods SET status = 'Active' WHERE email = %s", (u_email,))
            elif u_dept:
                cursor.execute("UPDATE hods SET status = 'Active' WHERE department = %s", (u_dept,))
        elif role == "Student":
            if stu_id:
                cursor.execute("UPDATE students SET status = 'Active' WHERE id = %s", (stu_id,))
            elif u_email:
                cursor.execute("UPDATE students SET status = 'Active' WHERE email = %s", (u_email,))
            
        conn.commit()
        return handler_instance._send_json({
            "success": True, 
            "message": f"User '{target_user['name']}' ({target_user['role']}) approved successfully and can now log in.",
            "user_id": target_user["id"]
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Approval error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/admin/approve-user', handle_post_approve_user)
register_route('POST', '/api/users/approve', handle_post_approve_user)

def handle_post_reject_user(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Only Administrators can reject user accounts"}, 403)
        
    user_id = body.get("user_id") or body.get("id") or query_params.get("user_id", [None])[0] or query_params.get("id", [None])[0]
    username = body.get("username")
    email = body.get("email")
    faculty_id = body.get("faculty_id") or body.get("facultyId")
    student_id = body.get("student_id") or body.get("studentId")
    department = body.get("department")
    
    if not user_id and not username and not email and not faculty_id and not student_id and not department:
        return handler_instance._send_json({"success": False, "message": "User identifier required for rejection"}, 400)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        target_user = None
        if user_id:
            if str(user_id).isdigit():
                cursor.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
                target_user = cursor.fetchone()
            if not target_user:
                cursor.execute("SELECT * FROM users WHERE faculty_id = %s OR student_id = %s OR username = %s OR email = %s", (user_id, user_id, user_id, user_id))
                target_user = cursor.fetchone()

        if not target_user and username:
            cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, username))
            target_user = cursor.fetchone()

        if not target_user and email:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            target_user = cursor.fetchone()

        if not target_user and faculty_id:
            cursor.execute("SELECT * FROM users WHERE faculty_id = %s", (faculty_id,))
            target_user = cursor.fetchone()

        if not target_user and student_id:
            cursor.execute("SELECT * FROM users WHERE student_id = %s", (student_id,))
            target_user = cursor.fetchone()

        if not target_user and department:
            cursor.execute("SELECT * FROM users WHERE role = 'HOD' AND LOWER(TRIM(department)) = LOWER(TRIM(%s))", (department,))
            target_user = cursor.fetchone()

        if not target_user:
            return handler_instance._send_json({"success": False, "message": "User not found"}, 404)
            
        cursor.execute("UPDATE users SET status = 'Rejected' WHERE id = %s", (target_user["id"],))
        
        role = target_user.get("role")
        fac_id = target_user.get("faculty_id") or ""
        u_email = target_user.get("email") or ""
        u_dept = target_user.get("department") or ""
        stu_id = target_user.get("student_id") or ""

        if role == "Faculty":
            if fac_id:
                cursor.execute("UPDATE faculty SET status = 'Rejected' WHERE id = %s", (fac_id,))
            elif u_email:
                cursor.execute("UPDATE faculty SET status = 'Rejected' WHERE email = %s", (u_email,))
        elif role == "HOD":
            if fac_id:
                cursor.execute("UPDATE hods SET status = 'Rejected' WHERE faculty_id = %s", (fac_id,))
            elif u_email:
                cursor.execute("UPDATE hods SET status = 'Rejected' WHERE email = %s", (u_email,))
            elif u_dept:
                cursor.execute("UPDATE hods SET status = 'Rejected' WHERE department = %s", (u_dept,))
        elif role == "Student":
            if stu_id:
                cursor.execute("UPDATE students SET status = 'Rejected' WHERE id = %s", (stu_id,))
            elif u_email:
                cursor.execute("UPDATE students SET status = 'Rejected' WHERE email = %s", (u_email,))
            
        conn.commit()
        return handler_instance._send_json({
            "success": True, 
            "message": f"Registration request for '{target_user['name']}' has been rejected."
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Rejection error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/admin/reject-user', handle_post_reject_user)
register_route('POST', '/api/users/reject', handle_post_reject_user)

def handle_get_users(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Only Administrators can view all user accounts"}, 403)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    role_filter = query_params.get("role", [None])[0]
    status_filter = query_params.get("status", [None])[0]

    try:
        sql = "SELECT id, username, name, role, email, mobile, department, student_id, faculty_id, status, created_at FROM users WHERE 1=1"
        p = []
        if role_filter and role_filter != "All":
            sql += " AND role = %s"
            p.append(role_filter)
        if status_filter and status_filter != "All":
            sql += " AND status = %s"
            p.append(status_filter)
            
        sql += " ORDER BY id DESC"
        cursor.execute(sql, tuple(p))
        users_list = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "users": users_list})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/users', handle_get_users)

def handle_post_user_status(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Only Administrators can modify user status"}, 403)
        
    user_id = body.get("user_id") or body.get("id")
    new_status = body.get("status")
    
    if not user_id or not new_status or new_status not in ["Active", "Inactive", "Pending", "Rejected"]:
        return handler_instance._send_json({"success": False, "message": "Valid User ID and Status (Active/Inactive/Pending/Rejected) required"}, 400)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        target_user = None
        if str(user_id).isdigit():
            cursor.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
            target_user = cursor.fetchone()
        if not target_user:
            cursor.execute("SELECT * FROM users WHERE faculty_id = %s OR student_id = %s OR username = %s OR email = %s", (user_id, user_id, user_id, user_id))
            target_user = cursor.fetchone()

        if not target_user:
            return handler_instance._send_json({"success": False, "message": "User not found"}, 404)

        cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, target_user["id"]))

        role = target_user.get("role")
        fac_id = target_user.get("faculty_id") or ""
        u_email = target_user.get("email") or ""
        u_dept = target_user.get("department") or ""
        stu_id = target_user.get("student_id") or ""

        if role == "Faculty":
            if fac_id:
                cursor.execute("UPDATE faculty SET status = %s WHERE id = %s", (new_status, fac_id))
            elif u_email:
                cursor.execute("UPDATE faculty SET status = %s WHERE email = %s", (new_status, u_email))
        elif role == "HOD":
            if fac_id:
                cursor.execute("UPDATE hods SET status = %s WHERE faculty_id = %s", (new_status, fac_id))
            elif u_email:
                cursor.execute("UPDATE hods SET status = %s WHERE email = %s", (new_status, u_email))
            elif u_dept:
                cursor.execute("UPDATE hods SET status = %s WHERE department = %s", (new_status, u_dept))
        elif role == "Student":
            if stu_id:
                cursor.execute("UPDATE students SET status = %s WHERE id = %s", (new_status, stu_id))
            elif u_email:
                cursor.execute("UPDATE students SET status = %s WHERE email = %s", (new_status, u_email))

        conn.commit()
        return handler_instance._send_json({"success": True, "message": f"User status changed to {new_status}."})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/admin/users/status', handle_post_user_status)
register_route('POST', '/api/users/status', handle_post_user_status)

# ----------------------------------------------------
# Admin Password Reset for Any User
# ----------------------------------------------------
def handle_admin_reset_password(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Only Administrators can reset user passwords"}, 403)

    user_id = body.get("user_id") or body.get("id") or body.get("username")
    if not user_id:
        return handler_instance._send_json({"success": False, "message": "User ID or Username is required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        target_user = None
        if str(user_id).isdigit():
            cursor.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
            target_user = cursor.fetchone()
        if not target_user:
            cursor.execute("SELECT * FROM users WHERE username = %s OR student_id = %s OR faculty_id = %s OR email = %s", (user_id, user_id, user_id, user_id))
            target_user = cursor.fetchone()

        if not target_user:
            return handler_instance._send_json({"success": False, "message": "User account not found"}, 404)

        from auth.utils import generate_temp_password, hash_password
        temp_pass = generate_temp_password()
        hashed = hash_password(temp_pass)

        cursor.execute(
            "UPDATE users SET password = %s, must_change_password = 1, temp_password_created_at = NOW() WHERE id = %s",
            (hashed, target_user["id"])
        )
        conn.commit()

        # Build credentials payload
        cred = {
            "name": target_user.get("name"),
            "role": target_user.get("role"),
            "username": target_user.get("username"),
            "enrollmentNumber": target_user.get("student_id") if target_user.get("role") == "Student" else "",
            "facultyId": target_user.get("faculty_id") if target_user.get("role") in ["Faculty", "HOD"] else "",
            "department": target_user.get("department") or "",
            "temporaryPassword": temp_pass,
            "loginUrl": "/login.html"
        }

        return handler_instance._send_json({
            "success": True,
            "message": f"Temporary password generated for {target_user['name']}.",
            "credentials": cred
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/admin/reset-password', handle_admin_reset_password)
register_route('POST', '/api/admin/users/reset-password', handle_admin_reset_password)



# ----------------------------------------------------
# Destructive Operations & Database Reset (Admin Only)
# ----------------------------------------------------
def handle_post_delete_students_bulk(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Only Administrators can perform bulk deletion"}, 403)
        
    student_ids = body.get("student_ids", [])
    delete_all = body.get("delete_all", False)
    
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if delete_all:
            cursor.execute("DELETE FROM faculty_students")
            cursor.execute("DELETE FROM attendance")
            cursor.execute("DELETE FROM results")
            cursor.execute("DELETE FROM fees")
            cursor.execute("DELETE FROM users WHERE role = 'Student'")
            cursor.execute("DELETE FROM students")
            conn.commit()
            return handler_instance._send_json({"success": True, "message": "All student records deleted successfully."})
        elif isinstance(student_ids, list) and len(student_ids) > 0:
            for s_id in student_ids:
                cursor.execute("DELETE FROM faculty_students WHERE student_id = %s", (s_id,))
                cursor.execute("DELETE FROM attendance WHERE student_id = %s", (s_id,))
                cursor.execute("DELETE FROM results WHERE student_id = %s", (s_id,))
                cursor.execute("DELETE FROM fees WHERE student_id = %s", (s_id,))
                cursor.execute("DELETE FROM users WHERE student_id = %s", (s_id,))
                cursor.execute("DELETE FROM students WHERE id = %s", (s_id,))
            conn.commit()
            return handler_instance._send_json({"success": True, "message": f"Successfully deleted {len(student_ids)} student records."})
        else:
            return handler_instance._send_json({"success": False, "message": "No students selected for deletion"}, 400)
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/admin/data/delete-students', handle_post_delete_students_bulk)

def handle_post_reset_database(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_admin(user):
        return handler_instance._send_json({"success": False, "message": "Only Administrators can reset system data"}, 403)
        
    confirmation = body.get("confirmation", "").strip()
    if confirmation != "DELETE ALL DATA":
        return handler_instance._send_json({
            "success": False, 
            "message": "Confirmation mismatch. You must explicitly pass confirmation: 'DELETE ALL DATA' to perform a complete data reset."
        }, 400)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        # Clear transactional tables while preserving admin user
        cursor.execute("DELETE FROM faculty_students")
        cursor.execute("DELETE FROM attendance")
        cursor.execute("DELETE FROM results")
        cursor.execute("DELETE FROM fees")
        cursor.execute("DELETE FROM timetable")
        cursor.execute("DELETE FROM notices")
        cursor.execute("DELETE FROM documents")
        cursor.execute("DELETE FROM contact_messages")
        cursor.execute("DELETE FROM students")
        cursor.execute("DELETE FROM faculty")
        cursor.execute("DELETE FROM hods")
        cursor.execute("DELETE FROM users WHERE role NOT IN ('Administrator', 'Admin')")
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Database successfully reset. Non-admin data cleared."})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Reset error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/admin/data/reset-database', handle_post_reset_database)
