import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user

def handle_get_health(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    handler_instance._send_json({"status": "ok", "message": "College ERP Python Server Running"})
    return


register_route('GET', '/api/health', handle_get_health)

def handle_get_reports_data(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    report_type = query_params.get("type", ["student"])[0]
    dept_f = query_params.get("department", [None])[0]
    year_f = query_params.get("year", [None])[0]
    search_q = query_params.get("search", [None])[0]

    data = []
    summary = {}

    if report_type == "student":
        sql = "SELECT * FROM students WHERE 1=1"
        p = []
        if role in ["HOD", "Faculty"]:
            sql += " AND department = %s"; p.append(user_dept)
        elif dept_f and dept_f != "All":
            sql += " AND department = %s"; p.append(dept_f)
        if year_f and year_f != "All":
            sql += " AND year = %s"; p.append(year_f)
        if search_q:
            sql += " AND (name LIKE %s OR id LIKE %s OR roll_number LIKE %s)"
            p.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])
        sql += " ORDER BY department, year, name"
        cursor.execute(sql, tuple(p))
        data = [dict(r) for r in cursor.fetchall()]
        summary = {"totalCount": len(data)}

    elif report_type == "faculty":
        sql = "SELECT * FROM faculty WHERE 1=1"
        p = []
        if role in ["HOD", "Faculty"]:
            sql += " AND department = %s"; p.append(user_dept)
        elif dept_f and dept_f != "All":
            sql += " AND department = %s"; p.append(dept_f)
        cursor.execute(sql, tuple(p))
        data = [dict(r) for r in cursor.fetchall()]
        summary = {"totalCount": len(data)}

    elif report_type == "attendance":
        sql = "SELECT * FROM attendance WHERE 1=1"
        p = []
        if role in ["HOD", "Faculty"]:
            sql += " AND department = %s"; p.append(user_dept)
        elif dept_f and dept_f != "All":
            sql += " AND department = %s"; p.append(dept_f)
        cursor.execute(sql, tuple(p))
        data = [dict(r) for r in cursor.fetchall()]
        summary = {"totalCount": len(data), "presentCount": sum(1 for d in data if d.get("status") == "Present")}

    elif report_type == "results":
        sql = "SELECT r.*, s.department, s.year FROM results r JOIN students s ON r.student_id = s.id WHERE 1=1"
        p = []
        if role in ["HOD", "Faculty"]:
            sql += " AND s.department = %s"; p.append(user_dept)
        elif dept_f and dept_f != "All":
            sql += " AND s.department = %s"; p.append(dept_f)
        cursor.execute(sql, tuple(p))
        data = [dict(r) for r in cursor.fetchall()]
        summary = {"totalCount": len(data), "passCount": sum(1 for d in data if d.get("status") == "Pass")}

    elif report_type == "fees":
        sql = "SELECT * FROM fees WHERE 1=1"
        p = []
        if role in ["HOD", "Faculty"]:
            sql += " AND department = %s"; p.append(user_dept)
        elif dept_f and dept_f != "All":
            sql += " AND department = %s"; p.append(dept_f)
        cursor.execute(sql, tuple(p))
        data = [dict(r) for r in cursor.fetchall()]
        summary = {
            "totalPaid": sum(d.get("paid_fees", 0) for d in data),
            "totalPending": sum(d.get("pending_fees", 0) for d in data)
        }

    conn.close()
    handler_instance._send_json({"success": True, "type": report_type, "summary": summary, "data": data})
    return

#     ports CSV Export Endpoint

register_route('GET', '/api/reports/data', handle_get_reports_data)

def handle_get_reports_export(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    report_type = query_params.get("type", ["student"])[0]
    dept_f = query_params.get("department", [None])[0]

    lines = []
    filename = f"{report_type}_report.csv"

    if report_type == "student":
        sql = "SELECT * FROM students WHERE 1=1"
        p = []
        if role in ["HOD", "Faculty"]:
            sql += " AND department = %s"; p.append(user_dept)
        elif dept_f and dept_f != "All":
            sql += " AND department = %s"; p.append(dept_f)
        cursor.execute(sql, tuple(p))
        rows = [dict(r) for r in cursor.fetchall()]
        lines.append("Student ID,Roll Number,Name,Department,Year,Semester,Division,Email,Mobile,Status\n")
        for r in rows:
            lines.append(f'"{r["id"]}","{r["roll_number"]}","{r["name"]}","{r["department"]}","{r.get("year","")}","{r["semester"]}","{r["division"]}","{r["email"]}","{r["mobile"]}","{r.get("status","")}"\n')

    elif report_type == "fees":
        sql = "SELECT * FROM fees WHERE 1=1"
        p = []
        if role in ["HOD", "Faculty"]:
            sql += " AND department = %s"; p.append(user_dept)
        elif dept_f and dept_f != "All":
            sql += " AND department = %s"; p.append(dept_f)
        cursor.execute(sql, tuple(p))
        rows = [dict(r) for r in cursor.fetchall()]
        lines.append("Student ID,Student Name,Department,Total Fees,Paid Fees,Pending Fees,Status,Payment Date\n")
        for r in rows:
            lines.append(f'"{r["student_id"]}","{r["student_name"]}","{r["department"]}","{r["total_fees"]}","{r["paid_fees"]}","{r["pending_fees"]}","{r["payment_status"]}","{r.get("payment_date","")}"\n')

    else:
        lines.append("Report Export Data\n")

    conn.close()
    handler_instance.send_response(200)
    handler_instance.send_header("Content-type", "text/csv; charset=utf-8")
    handler_instance.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler_instance.end_headers()
    handler_instance.wfile.write("".join(lines).encode("utf-8"))
    return

#     D Student Year Summary Count Endpoint

register_route('GET', '/api/reports/export', handle_get_reports_export)

def handle_post_dashboard_stats(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    stats = {}
    if role in ["Administrator", "Admin"]:
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
        stats["totalPaidFees"] = row["paid"] or 0
        stats["totalPendingFees"] = row["pending"] or 0
        cursor.execute("SELECT COUNT(*) as count FROM notices")
        stats["totalNotices"] = cursor.fetchone()["count"]
    elif role == "HOD":
        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s", (user_dept,))
        stats["totalStudents"] = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM faculty WHERE department = %s", (user_dept,))
        stats["totalFaculty"] = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM notices WHERE department = %s OR department = 'All'", (user_dept,))
        stats["totalNotices"] = cursor.fetchone()["count"]
        cursor.execute("SELECT SUM(paid_fees) as paid, SUM(pending_fees) as pending FROM fees WHERE department = %s", (user_dept,))
        row = cursor.fetchone()
        stats["totalPaidFees"] = row["paid"] or 0
        stats["totalPendingFees"] = row["pending"] or 0
    elif role == "Faculty":
        cursor.execute("SELECT COUNT(*) as count FROM students WHERE department = %s", (user_dept,))
        stats["totalStudents"] = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM notices WHERE department = %s OR department = 'All'", (user_dept,))
        stats["totalNotices"] = cursor.fetchone()["count"]
        stats["assignedSubjects"] = 3
        stats["totalClasses"] = 12
    elif role == "Student":
        cursor.execute("SELECT COUNT(*) as count FROM notices WHERE (department = %s OR department = 'All') AND (target_role = 'Student' OR target_role = 'All')", (user_dept,))
        stats["totalNotices"] = cursor.fetchone()["count"]
        cursor.execute("SELECT total_fees, paid_fees, pending_fees FROM fees WHERE student_id = %s", (student_id,))
        fee_row = cursor.fetchone()
        cursor.execute("SELECT AVG(percentage) FROM results WHERE student_id = %s", (student_id,))
        avg_p = cursor.fetchone()[0]
        stats["avgPercentage"] = round(avg_p, 1) if avg_p else 0.0

    conn.close()
    handler_instance._send_json({"success": True, "stats": stats})
    return

#     .close()
#     ._send_json({"error": "API endpoint not found"}, 404)

    ed_url = urllib.parse.urlparse(self.path)
#      = parsed_url.path

#     nary / Multipart Upload Handling

register_route('GET', '/api/dashboard/stats', handle_post_dashboard_stats)

def handle_post_upload(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    user = self.get_current_user()
    if not user:
        handler_instance._send_json({"success": False, "message": "Authentication required"}, 401)
        return

    content_type = self.headers.get("Content-Type", "")
    content_length = int(self.headers.get("Content-Length", 0))
    body = self.rfile.read(content_length)

    if "boundary=" in content_type:
        # Extract boundary value safely handling quotes and parameters
        boundary_val = content_type.split("boundary=")[1].split(";")[0].strip().strip('"').strip("'")
        boundary = boundary_val.encode('utf-8')
        delimiter = b"--" + boundary
        parts = body.split(delimiter)
        for part in parts:
            if b"filename=" in part:
                if part.startswith(b"\r\n"):
                    part = part[2:]
                if b"\r\n\r\n" in part:
                    headers_part, file_data = part.split(b"\r\n\r\n", 1)
                    # Remove trailing \r\n (or \r\n--) before the boundary delimiter
                    if file_data.endswith(b"\r\n"):
                        file_data = file_data[:-2]
                    elif file_data.endswith(b"\r\n--"):
                        file_data = file_data[:-4]

                    headers_str = headers_part.decode('utf-8', errors='ignore')
                    fn_match = re.search(r'filename=["\']%s([^"\'\r\n;]+)["\']%s', headers_str)
                    raw_fn = fn_match.group(1).strip() if fn_match else f"upload_{int(time.time())}.dat"
                    safe_basename = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(raw_fn))
                    safe_fn = f"{int(time.time())}_{safe_basename}"
                    out_path = os.path.join(UPLOADS_DIR, safe_fn)
                    with open(out_path, "wb") as f:
                        f.write(file_data)
                    rel_path = f"/uploads/{safe_fn}"
                    handler_instance._send_json({"success": True, "filePath": rel_path, "fileName": safe_fn})
                    return

    filename = self.headers.get("X-File-Name", f"file_{int(time.time())}.dat")
    safe_basename = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(filename))
    safe_fn = f"{int(time.time())}_{safe_basename}"
    out_path = os.path.join(UPLOADS_DIR, safe_fn)
    with open(out_path, "wb") as f:
        f.write(body)
    handler_instance._send_json({"success": True, "filePath": f"/uploads/{safe_fn}", "fileName": safe_fn})
    return

    ent_length = int(self.headers.get("Content-Length", 0))
    _data = self.rfile.read(content_length)
    oad = json.loads(post_data.decode("utf-8")) if post_data else {}

#      Login Endpoint

register_route('POST', '/api/upload', handle_post_upload)

