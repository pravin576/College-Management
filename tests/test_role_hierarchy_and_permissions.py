import os
import sys
import time
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def request(method, path, body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Session-Token"] = token
    
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            try:
                return resp.status, json.loads(content.decode("utf-8"))
            except Exception:
                return resp.status, content
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 500, {"error": str(e)}

def run_tests():
    print("=" * 70)
    print("RUNNING STRICT 4-ROLE PERMISSIONS & AUTHORIZATION VERIFICATION")
    print("=" * 70)

    ts = int(time.time())

    # ----------------------------------------------------
    # 1. SETUP TEST ACCOUNTS ACROSS ALL 4 ROLES
    # ----------------------------------------------------
    print("\n[SETUP] Initializing Accounts...")
    
    # 1.1 Admin Login
    st, res = request("POST", "/api/login", {"username": "admin", "password": "admin123", "role": "Administrator"})
    assert st == 200, f"Admin login failed: {res}"
    admin_token = res["token"]
    print("[+] Admin login successful")

    # 1.2 Create or Assign HOD for Computer Engineering
    st, res = request("POST", "/api/hods", {
        "department": "Computer Engineering",
        "name": "Dr. Test HOD",
        "username": f"hod_co_{ts}",
        "password": "Password123!",
        "email": f"hod_co_{ts}@college.edu",
        "faculty_id": f"HOD_CO_{ts}",
        "reassign": True
    }, token=admin_token)
    assert st in [200, 201], f"Create HOD failed: {res}"

    st, res = request("POST", "/api/login", {"username": f"hod_co_{ts}", "password": "Password123!", "role": "HOD"})
    assert st == 200, f"HOD login failed: {res}"
    hod_token = res["token"]
    print(f"[+] HOD created and logged in: hod_co_{ts}")

    # 1.3 Create Faculty in Computer Engineering
    st, res = request("POST", "/api/faculty", {
        "id": f"FAC_CO_{ts}",
        "name": "Prof. Test Faculty",
        "department": "Computer Engineering",
        "designation": "Assistant Professor",
        "email": f"fac_{ts}@college.edu",
        "username": f"fac_{ts}",
        "password": "Password123!"
    }, token=admin_token)
    assert st in [200, 201], f"Create Faculty failed: {res}"

    st, res = request("POST", "/api/login", {"username": f"fac_{ts}", "password": "Password123!", "role": "Faculty"})
    assert st == 200, f"Faculty login failed: {res}"
    faculty_token = res["token"]
    print(f"[+] Faculty created and logged in: fac_{ts}")

    # 1.4 Create Faculty in Civil Engineering (for cross-dept test)
    st, res = request("POST", "/api/faculty", {
        "id": f"FAC_CI_{ts}",
        "name": "Prof. Civil Faculty",
        "department": "Civil Engineering",
        "designation": "Assistant Professor",
        "email": f"fac_ci_{ts}@college.edu",
        "username": f"fac_ci_{ts}",
        "password": "Password123!"
    }, token=admin_token)
    assert st in [200, 201], f"Create Civil Faculty failed: {res}"

    # 1.5 Create Students in Computer Engineering
    st, res = request("POST", "/api/students", {
        "id": f"STU_CO_{ts}",
        "roll_number": f"R_CO_{ts}",
        "name": "Student CO One",
        "department": "Computer Engineering",
        "year": "First Year",
        "semester": "Semester 1",
        "division": "A",
        "email": f"stu_co_{ts}@college.edu",
        "username": f"stu_co_{ts}",
        "password": "Password123!"
    }, token=admin_token)
    assert st in [200, 201], f"Create Student CO failed: {res}"

    st, res = request("POST", "/api/login", {"username": f"stu_co_{ts}", "password": "Password123!", "role": "Student"})
    assert st == 200, f"Student CO login failed: {res}"
    student_token = res["token"]
    print(f"[+] Student CO created and logged in: stu_co_{ts}")

    # 1.6 Create Student in Civil Engineering (for cross-dept test)
    st, res = request("POST", "/api/students", {
        "id": f"STU_CI_{ts}",
        "roll_number": f"R_CI_{ts}",
        "name": "Student CI Two",
        "department": "Civil Engineering",
        "year": "First Year",
        "semester": "Semester 1",
        "division": "A",
        "email": f"stu_ci_{ts}@college.edu",
        "username": f"stu_ci_{ts}",
        "password": "Password123!"
    }, token=admin_token)
    assert st in [200, 201], f"Create Student CI failed: {res}"

    # ====================================================
    # TEST 1 — ADMINISTRATIVE PERMISSIONS & RESTRICTIONS
    # ====================================================
    print("\n[TEST 1: ADMINISTRATIVE PERMISSIONS & RESTRICTIONS]")
    
    # 1.1 Admin Dashboard stats returned with college-wide stats
    st, res = request("GET", "/api/dashboard/stats", token=admin_token)
    print("DEBUG Admin stats res:", res)
    assert st == 200, f"Admin dashboard stats failed: {res}"
    stats = res.get("stats", {})
    assert "totalStudents" in stats and "totalFaculty" in stats and "totalHODs" in stats and "totalDepartments" in stats
    assert "attendancePercentage" in stats and "resultPassPercentage" in stats and "departmentStats" in stats
    print("[PASS] 1.1 Admin Dashboard provides full institute-wide stats and department matrix")

    # 1.2 Admin can manage Students, Faculty, HODs, Departments
    st, _ = request("GET", "/api/students", token=admin_token)
    assert st == 200
    st, _ = request("GET", "/api/faculty", token=admin_token)
    assert st == 200
    st, _ = request("GET", "/api/hods", token=admin_token)
    assert st == 200
    st, _ = request("GET", "/api/departments", token=admin_token)
    assert st == 200
    print("[PASS] 1.2 Admin has access to all college-wide management modules")

    # 1.3 CRITICAL: Admin MUST NOT be able to use Faculty-Student Assignment endpoints!
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CO_{ts}"]
    }, token=admin_token)
    assert st == 403, f"Admin should be BLOCKED (403) from assign endpoint, got: {st} {res}"
    print(f"[PASS] 1.3 POST /api/faculty-students/assign correctly BLOCKED for Admin (403 Forbidden)")

    st, res = request("POST", "/api/faculty-students/remove", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CO_{ts}"]
    }, token=admin_token)
    assert st == 403, f"Admin should be BLOCKED (403) from remove assignment endpoint, got: {st} {res}"
    print(f"[PASS] 1.4 POST /api/faculty-students/remove correctly BLOCKED for Admin (403 Forbidden)")

    st, res = request("GET", f"/api/faculty-students?faculty_id=FAC_CO_{ts}", token=admin_token)
    assert st == 403, f"Admin should be BLOCKED (403) from faculty-students query, got: {st} {res}"
    print(f"[PASS] 1.5 GET /api/faculty-students correctly BLOCKED for Admin (403 Forbidden)")

    # ====================================================
    # TEST 2 — HOD PERMISSIONS & DEPARTMENT ISOLATION
    # ====================================================
    print("\n[TEST 2: HOD PERMISSIONS & DEPARTMENT ISOLATION]")

    # 2.1 HOD Dashboard isolated to own department
    st, res = request("GET", "/api/dashboard/stats", token=hod_token)
    assert st == 200, f"HOD dashboard stats failed: {res}"
    assert res.get("stats", {}).get("department") == "Computer Engineering"
    print("[PASS] 2.1 HOD Dashboard strictly isolated to Computer Engineering")

    # 2.2 HOD can assign students to faculty in own department
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CO_{ts}"]
    }, token=hod_token)
    assert st == 200, f"HOD failed to assign student to faculty in own dept: {st} {res}"
    print("[PASS] 2.2 HOD successfully assigned student to faculty in own department")

    # 2.3 HOD query assigned students
    st, res = request("GET", f"/api/faculty-students?faculty_id=FAC_CO_{ts}", token=hod_token)
    assert st == 200 and len(res.get("students", [])) > 0
    print("[PASS] 2.3 HOD successfully queries assigned students in own department")

    # 2.4 HOD CANNOT assign cross-department (Faculty in Civil Engineering)
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CI_{ts}",
        "student_ids": [f"STU_CO_{ts}"]
    }, token=hod_token)
    assert st == 403, f"HOD should be BLOCKED from assigning other department faculty: {st} {res}"
    print("[PASS] 2.4 HOD cross-department faculty assignment BLOCKED (403 Forbidden)")

    # 2.5 HOD CANNOT assign student from another department
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CI_{ts}"]
    }, token=hod_token)
    assert st == 403, f"HOD should be BLOCKED from assigning other department student: {st} {res}"
    print("[PASS] 2.5 HOD cross-department student assignment BLOCKED (403 Forbidden)")

    # 2.6 HOD CANNOT create or delete HOD accounts
    st, res = request("POST", "/api/hods", {"department": "Mechanical Engineering", "name": "Fake HOD"}, token=hod_token)
    assert st == 403
    print("[PASS] 2.6 HOD managing HOD leadership accounts BLOCKED (403 Forbidden)")

    # ====================================================
    # TEST 3 — FACULTY PERMISSIONS & ASSIGNED STUDENT RESTRICTION
    # ====================================================
    print("\n[TEST 3: FACULTY PERMISSIONS & ASSIGNED STUDENTS]")

    # 3.1 Faculty queries students -> sees ONLY assigned student STU_CO_{ts}
    st, res = request("GET", "/api/students", token=faculty_token)
    assert st == 200
    stu_list = res.get("students", [])
    stu_ids = [s["id"] for s in stu_list]
    assert f"STU_CO_{ts}" in stu_ids, f"Assigned student should be visible: {stu_list}"
    assert f"STU_CI_{ts}" not in stu_ids, f"Unassigned student must NOT be visible: {stu_list}"
    print(f"[PASS] 3.1 Faculty only accesses assigned students ({len(stu_list)} assigned)")

    # 3.2 Faculty marks attendance for assigned student -> 200 OK
    st, res = request("POST", "/api/attendance", {
        "studentId": f"STU_CO_{ts}",
        "subject": "Data Structures",
        "date": time.strftime('%Y-%m-%d'),
        "status": "Present"
    }, token=faculty_token)
    assert st == 200, f"Faculty marking attendance for assigned student failed: {st} {res}"
    print("[PASS] 3.2 Faculty successfully marked attendance for assigned student")

    # 3.3 Faculty CANNOT mark attendance for unassigned student
    st, res = request("POST", "/api/attendance", {
        "studentId": f"STU_CI_{ts}",
        "subject": "Data Structures",
        "date": time.strftime('%Y-%m-%d'),
        "status": "Present"
    }, token=faculty_token)
    assert st == 403, f"Faculty marking attendance for unassigned student should be BLOCKED: {st} {res}"
    print("[PASS] 3.3 Faculty marking attendance for unassigned student BLOCKED (403 Forbidden)")

    # 3.4 Faculty CANNOT assign students
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CO_{ts}"]
    }, token=faculty_token)
    assert st == 403
    print("[PASS] 3.4 Faculty attempting to use assignment portal BLOCKED (403 Forbidden)")

    # ====================================================
    # TEST 4 — STUDENT PERMISSIONS & STRICT IDOR DEFENSE
    # ====================================================
    print("\n[TEST 4: STUDENT PERMISSIONS & IDOR DEFENSE]")

    # 4.1 Student queries students -> returns ONLY own record
    st, res = request("GET", "/api/students", token=student_token)
    assert st == 200
    stus = res.get("students", [])
    assert len(stus) == 1 and stus[0]["id"] == f"STU_CO_{ts}"
    print("[PASS] 4.1 Student queries /api/students -> returns only own record")

    # 4.2 Student queries ID card of another student -> BLOCKED (403)
    st, res = request("GET", f"/api/students/id-card?id=STU_CI_{ts}", token=student_token)
    assert st == 403, f"Student ID card IDOR should be blocked: {st} {res}"
    print("[PASS] 4.2 Student accessing another student's ID card BLOCKED (403 Forbidden - IDOR protected)")

    # 4.3 Student CANNOT modify attendance, results, fees
    st, res = request("POST", "/api/attendance", {"studentId": f"STU_CO_{ts}", "status": "Present"}, token=student_token)
    assert st == 403
    st, res = request("POST", "/api/results", {"studentId": f"STU_CO_{ts}", "subject": "Math"}, token=student_token)
    assert st == 403
    print("[PASS] 4.3 Student attempting to modify attendance/results BLOCKED (403 Forbidden)")

    # 4.4 Student CANNOT access assignment, faculty, or hod management
    st, res = request("POST", "/api/faculty-students/assign", {"faculty_id": "test", "student_ids": ["test"]}, token=student_token)
    assert st == 403
    st, res = request("POST", "/api/faculty", {"name": "test"}, token=student_token)
    assert st == 403
    st, res = request("POST", "/api/hods", {"department": "test"}, token=student_token)
    assert st == 403
    print("[PASS] 4.4 Student attempting to access management APIs BLOCKED (403 Forbidden)")

    # 4.5 Clean up: HOD removes student assignment
    st, res = request("POST", "/api/faculty-students/remove", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CO_{ts}"]
    }, token=hod_token)
    assert st == 200
    print("[PASS] 4.5 HOD successfully removed student assignment")

    print("\n" + "=" * 70)
    print("ALL 4 ROLES & PERMISSION REQUIREMENTS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
