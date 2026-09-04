import urllib.request
import json
import os
import sys

BASE_URL = "http://localhost:8000"

def api_call(path, method="GET", body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            ct = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="ignore")
            if "application/json" in ct:
                return resp.status, json.loads(raw)
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(raw)
        except:
            return e.code, {"success": False, "message": raw}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}

def check_all_modules():
    print("=" * 80)
    print("STARTING FULL SYSTEM MODULE HEALTH & FUNCTIONALITY VERIFICATION")
    print("=" * 80)
    
    passed_checks = 0
    total_checks = 0

    def assert_check(name, condition, extra=""):
        nonlocal passed_checks, total_checks
        total_checks += 1
        if condition:
            passed_checks += 1
            print(f"  [PASS] {name} {extra}")
        else:
            print(f"  [FAIL] {name} - {extra}")
            raise AssertionError(f"Check failed: {name} - {extra}")

    # =========================================================================
    # 1. SYSTEM HEALTH
    # =========================================================================
    print("\n--- 1. System Health Check ---")
    status, res = api_call("/api/health", "GET")
    assert_check("Server Health Check", status == 200 and res.get("status") in ["ok", "healthy"])

    # =========================================================================
    # 2. AUTHENTICATION & LOGIN (ALL 4 ROLES)
    # =========================================================================
    print("\n--- 2. Authentication & Role Logins ---")
    # Admin
    status, res = api_call("/api/login", "POST", {"username": "admin", "password": "admin123"})
    assert_check("Admin Login", status == 200 and "token" in res)
    admin_token = res.get("token")
    admin_user = res.get("user", {})
    assert_check("Admin Role Verification", admin_user.get("role") in ["Administrator", "Admin"])

    # HOD
    status_hod, res_hod = api_call("/api/hods", "POST", {
        "faculty_id": "FAC_HOD_TEST", "name": "Prof HOD Test", "department": "Computer Engineering",
        "email": "hod.test.auto@college.edu", "contact": "9876543210", "qualification": "Ph.D", "experience": "10",
        "password": "HodPassword#2026", "is_edit": True
    }, token=admin_token)
    hod_username = (res_hod.get("credentials") or {}).get("username") or "hod.test.auto@college.edu"
    status, res = api_call("/api/login", "POST", {"username": hod_username, "password": "HodPassword#2026"})
    assert_check("HOD Login", status == 200 and "token" in res)
    hod_token = res.get("token")
    hod_user = res.get("user", {})
    assert_check("HOD Role Verification", hod_user.get("role") == "HOD")

    # Faculty
    status_fac, res_fac = api_call("/api/faculty", "POST", {
        "faculty_id": "FAC_MODULE_TEST", "name": "Prof Faculty Test", "department": "Computer Engineering",
        "email": "faculty.test.auto@college.edu", "contact": "9876543211", "designation": "Assistant Professor",
        "qualification": "M.Tech", "experience": "5", "password": "FacPassword#2026", "is_edit": True
    }, token=hod_token)
    fac_username = (res_fac.get("credentials") or {}).get("username") or "faculty.test.auto@college.edu"
    status, res = api_call("/api/login", "POST", {"username": fac_username, "password": "FacPassword#2026"})
    assert_check("Faculty Login", status == 200 and "token" in res)
    faculty_token = res.get("token")
    faculty_user = res.get("user", {})
    assert_check("Faculty Role Verification", faculty_user.get("role") == "Faculty")

    # Student
    status_stu, res_stu = api_call("/api/students", "POST", {
        "enrollment_number": "STU_MOD_TEST", "roll_number": "999", "name": "Module Test Student", "department": "Computer Engineering",
        "semester": "Semester 6", "year": "Third Year", "email": "stu.mod.test@college.edu", "contact": "9876543212",
        "password": "StuPassword#2026", "is_edit": True
    }, token=hod_token)
    stu_username = "STU_MOD_TEST"
    status, res = api_call("/api/login", "POST", {"username": stu_username, "password": "StuPassword#2026"})
    assert_check("Student Login", status == 200 and "token" in res)
    student_token = res.get("token")
    student_user = res.get("user", {})
    assert_check("Student Role Verification", student_user.get("role") == "Student")

    # =========================================================================
    # 3. PROFILE & SELF-SERVICE CREDENTIALS MODULE
    # =========================================================================
    print("\n--- 3. Profile Module ---")
    for role_name, token in [("Admin", admin_token), ("HOD", hod_token), ("Faculty", faculty_token), ("Student", student_token)]:
        status, res = api_call("/api/profile", "GET", token=token)
        assert_check(f"{role_name} Fetch Profile (GET /api/profile)", status == 200 and res.get("success"))

    # =========================================================================
    # 4. DASHBOARD STATS MODULE
    # =========================================================================
    print("\n--- 4. Dashboard Stats Module ---")
    status, res = api_call("/api/dashboard/stats", "GET", token=admin_token)
    assert_check("Admin Dashboard Stats (GET /api/dashboard/stats)", status == 200)

    status, res = api_call("/api/hod/dashboard-stats", "GET", token=hod_token)
    assert_check("HOD Dashboard Stats (GET /api/hod/dashboard-stats)", status == 200)

    # =========================================================================
    # 5. DEPARTMENTS MODULE
    # =========================================================================
    print("\n--- 5. Departments Module ---")
    status, res = api_call("/api/departments", "GET", token=admin_token)
    assert_check("Get Departments (Admin)", status == 200)

    status, res = api_call("/api/departments", "GET", token=student_token)
    assert_check("Get Departments (Student read-only)", status == 200)

    # =========================================================================
    # 6. HOD MODULE
    # =========================================================================
    print("\n--- 6. HOD Module ---")
    status, res = api_call("/api/hods", "GET", token=admin_token)
    assert_check("Get All HODs (Admin)", status == 200)

    status, res = api_call("/api/faculty", "GET", token=hod_token)
    assert_check("Get HOD Scoped Faculty List", status == 200)

    status, res = api_call("/api/students", "GET", token=hod_token)
    assert_check("Get HOD Scoped Student List", status == 200)

    status, res = api_call("/api/hod/student-summary", "GET", token=hod_token)
    assert_check("Get HOD Student Summary", status == 200)

    # =========================================================================
    # 7. FACULTY MODULE
    # =========================================================================
    print("\n--- 7. Faculty Module ---")
    status, res = api_call("/api/faculty", "GET", token=admin_token)
    assert_check("Get Faculty List (Admin)", status == 200)

    status, res = api_call("/api/faculty-students", "GET", token=faculty_token)
    assert_check("Get Faculty Assigned Students", status == 200)

    # =========================================================================
    # 8. STUDENTS MODULE
    # =========================================================================
    print("\n--- 8. Students Module ---")
    status, res = api_call("/api/students", "GET", token=admin_token)
    assert_check("Get Students List (Admin)", status == 200)

    status, res = api_call("/api/students/excel-template", "GET", token=hod_token)
    assert_check("Get Student Excel Template", status == 200)

    status, res = api_call("/api/students/id-card?id=STU_MOD_TEST", "GET", token=student_token)
    assert_check("Get Student ID Card", status == 200)

    # =========================================================================
    # 9. ATTENDANCE MODULE
    # =========================================================================
    print("\n--- 9. Attendance Module ---")
    status, res = api_call("/api/attendance", "GET", token=faculty_token)
    assert_check("Get Attendance Records (Faculty)", status == 200)

    status, res = api_call("/api/attendance?student_id=STU_MOD_TEST", "GET", token=student_token)
    assert_check("Get Student Scoped Attendance", status == 200)

    status, res = api_call("/api/attendance/excel-template", "GET", token=faculty_token)
    assert_check("Get Attendance Excel Template", status == 200)

    # =========================================================================
    # 10. RESULTS MODULE
    # =========================================================================
    print("\n--- 10. Results Module ---")
    status, res = api_call("/api/results", "GET", token=faculty_token)
    assert_check("Get Results Records (Faculty)", status == 200)

    status, res = api_call("/api/results?student_id=STU_MOD_TEST", "GET", token=student_token)
    assert_check("Get Student Scoped Results", status == 200)

    status, res = api_call("/api/results/excel-template", "GET", token=faculty_token)
    assert_check("Get Results Excel Template", status == 200)

    # =========================================================================
    # 11. FEES MODULE
    # =========================================================================
    print("\n--- 11. Fees Module ---")
    status, res = api_call("/api/fees", "GET", token=admin_token)
    assert_check("Get Fees Records (Admin)", status == 200)

    status, res = api_call("/api/fees?student_id=STU_MOD_TEST", "GET", token=student_token)
    assert_check("Get Student Fees Status", status == 200)

    # =========================================================================
    # 12. TIMETABLE & SUBJECTS MODULE
    # =========================================================================
    print("\n--- 12. Timetable & Subjects Module ---")
    status, res = api_call("/api/timetable", "GET", token=faculty_token)
    assert_check("Get Timetable (Faculty)", status == 200)

    status, res = api_call("/api/timetable?department=Computer+Engineering", "GET", token=student_token)
    assert_check("Get Timetable (Student)", status == 200)

    status, res = api_call("/api/subjects", "GET", token=admin_token)
    assert_check("Get Subjects List", status == 200)

    # =========================================================================
    # 13. NOTICES & DOCUMENTS MODULE
    # =========================================================================
    print("\n--- 13. Notices & Documents Module ---")
    status, res = api_call("/api/notices", "GET", token=student_token)
    assert_check("Get Notices (Student)", status == 200)

    status, res = api_call("/api/public/notices", "GET")
    assert_check("Get Public Notices (No Auth)", status == 200)

    status, res = api_call("/api/documents", "GET", token=admin_token)
    assert_check("Get Documents (Admin)", status == 200)

    # =========================================================================
    # 14. ADMIN REPORTS & USERS MANAGEMENT MODULE
    # =========================================================================
    print("\n--- 14. Admin Reports & Users Module ---")
    status, res = api_call("/api/reports/data?type=students", "GET", token=admin_token)
    assert_check("Get Academic Reports Data", status == 200)

    status, res = api_call("/api/users", "GET", token=admin_token)
    assert_check("Get All System Users (Admin)", status == 200)

    status, res = api_call("/api/admin/pending-users", "GET", token=admin_token)
    assert_check("Get Pending Users (Admin)", status == 200)

    # =========================================================================
    # 15. STATIC FRONTEND WEB PAGES ACCESSIBILITY
    # =========================================================================
    print("\n--- 15. Frontend Static Pages Availability ---")
    pages = [
        "/index.html",
        "/home.html",
        "/login.html",
        "/dashboard.html",
        "/profile.html",
        "/hod.html",
        "/faculty.html",
        "/students.html",
        "/attendance.html",
        "/results.html",
        "/fees.html",
        "/timetable.html",
        "/notices.html",
        "/documents.html",
        "/reports.html",
        "/settings.html",
        "/contact.html"
    ]
    for page in pages:
        status, res = api_call(page, "GET")
        assert_check(f"Static page '{page}'", status == 200)

    print("\n" + "=" * 80)
    print(f"ALL MODULE HEALTH CHECKS PASSED: {passed_checks}/{total_checks} (100%)")
    print("=" * 80)

if __name__ == "__main__":
    check_all_modules()
