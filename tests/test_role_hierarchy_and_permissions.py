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
    
    # 1.1 Ensure Admin Account & Login
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "backend")))
    try:
        from config.database import get_db_connection
        from auth.utils import hash_password
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = 'admin'")
            if cur.fetchone():
                cur.execute("UPDATE users SET password = %s, status = 'Active', role = 'Administrator' WHERE username = 'admin'", (hash_password("admin123"),))
            else:
                cur.execute("INSERT INTO users (username, password, role, name, email, department, status) VALUES ('admin', %s, 'Administrator', 'System Administrator', 'admin@college.edu', 'Administration', 'Active')", (hash_password("admin123"),))
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print(f"[!] Warning resetting admin credentials: {e}")

    st, res = request("POST", "/api/login", {"username": "admin", "password": "admin123", "role": "Administrator"})
    assert st == 200, f"Admin login failed: {res}"
    admin_token = res["token"]
    print("[+] Admin login successful")

    # 1.2 Admin Creates/Assigns HOD for Computer Engineering
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

    # 1.3 Admin Creates/Assigns HOD for Civil Engineering (for cross-dept checks)
    st, res = request("POST", "/api/hods", {
        "department": "Civil Engineering",
        "name": "Dr. Civil HOD",
        "username": f"hod_ci_{ts}",
        "password": "Password123!",
        "email": f"hod_ci_{ts}@college.edu",
        "faculty_id": f"HOD_CI_{ts}",
        "reassign": True
    }, token=admin_token)
    assert st in [200, 201], f"Create Civil HOD failed: {res}"

    st, res = request("POST", "/api/login", {"username": f"hod_ci_{ts}", "password": "Password123!", "role": "HOD"})
    assert st == 200, f"Civil HOD login failed: {res}"
    hod_civil_token = res["token"]

    # 1.4 HOD Creates Faculty in Computer Engineering
    st, res = request("POST", "/api/faculty", {
        "id": f"FAC_CO_{ts}",
        "name": "Prof. Test Faculty",
        "department": "Computer Engineering",
        "designation": "Assistant Professor",
        "email": f"fac_{ts}@college.edu",
        "username": f"fac_{ts}",
        "password": "Password123!"
    }, token=hod_token)
    assert st in [200, 201], f"HOD create Faculty failed: {res}"

    st, res = request("POST", "/api/login", {"username": f"fac_{ts}", "password": "Password123!", "role": "Faculty"})
    assert st == 200, f"Faculty login failed: {res}"
    faculty_token = res["token"]
    print(f"[+] Faculty created and logged in: fac_{ts}")

    # 1.5 Civil HOD Creates Faculty in Civil Engineering
    st, res = request("POST", "/api/faculty", {
        "id": f"FAC_CI_{ts}",
        "name": "Prof. Civil Faculty",
        "department": "Civil Engineering",
        "designation": "Assistant Professor",
        "email": f"fac_ci_{ts}@college.edu",
        "username": f"fac_ci_{ts}",
        "password": "Password123!"
    }, token=hod_civil_token)
    assert st in [200, 201], f"Civil HOD create Faculty failed: {res}"

    # 1.6 HOD Creates Students in Computer Engineering
    st, res = request("POST", "/api/students", {
        "id": f"STU_CO_{ts}",
        "rollNumber": f"R_CO_{ts}",
        "name": "Alice Computer",
        "department": "Computer Engineering",
        "email": f"stu_co_{ts}@college.edu",
        "password": "Password123!"
    }, token=hod_token)
    assert st in [200, 201], f"Create Student 1 failed: {res}"

    st, res = request("POST", "/api/students", {
        "id": f"STU_CO2_{ts}",
        "rollNumber": f"R_CO2_{ts}",
        "name": "Bob Computer",
        "department": "Computer Engineering",
        "email": f"stu_co2_{ts}@college.edu",
        "password": "Password123!"
    }, token=hod_token)
    assert st in [200, 201], f"Create Student 2 failed: {res}"

    st, res = request("POST", "/api/login", {"username": f"STU_CO_{ts}", "password": "Password123!", "role": "Student"})
    assert st == 200, f"Student login failed: {res}"
    student_token = res["token"]
    print(f"[+] Student created and logged in: STU_CO_{ts}")

    # 1.7 Civil HOD Creates Student in Civil Engineering
    st, res = request("POST", "/api/students", {
        "id": f"STU_CI_{ts}",
        "rollNumber": f"R_CI_{ts}",
        "name": "Charlie Civil",
        "department": "Civil Engineering",
        "email": f"stu_ci_{ts}@college.edu",
        "password": "Password123!"
    }, token=hod_civil_token)
    assert st in [200, 201], f"Create Civil Student failed: {res}"

    # ----------------------------------------------------
    # 2. ADMINISTRATIVE / PRINCIPAL RESTRICTIONS (MONITORING ONLY)
    # ----------------------------------------------------
    print("\n[TEST 1] Testing Administrative / Principal Monitoring-Only Role...")
    
    # Admin cannot create student -> 403 Forbidden
    st, res = request("POST", "/api/students", {
        "id": f"STU_ADMIN_{ts}",
        "rollNumber": f"R_ADM_{ts}",
        "name": "Admin Student",
        "department": "Computer Engineering"
    }, token=admin_token)
    assert st == 403, f"Expected 403 when Admin adds student, got {st}: {res}"
    print("[PASS] Admin denied from adding students (403 Forbidden)")

    # Admin cannot delete student -> 403 Forbidden
    st, res = request("DELETE", f"/api/students?id=STU_CO_{ts}", token=admin_token)
    assert st == 403, f"Expected 403 when Admin deletes student, got {st}: {res}"
    print("[PASS] Admin denied from deleting students (403 Forbidden)")

    # Admin cannot create faculty -> 403 Forbidden
    st, res = request("POST", "/api/faculty", {
        "id": f"FAC_ADMIN_{ts}",
        "name": "Admin Faculty",
        "department": "Computer Engineering"
    }, token=admin_token)
    assert st == 403, f"Expected 403 when Admin adds faculty, got {st}: {res}"
    print("[PASS] Admin denied from adding faculty (403 Forbidden)")

    # Admin cannot delete faculty -> 403 Forbidden
    st, res = request("DELETE", f"/api/faculty?id=FAC_CO_{ts}", token=admin_token)
    assert st == 403, f"Expected 403 when Admin deletes faculty, got {st}: {res}"
    print("[PASS] Admin denied from deleting faculty (403 Forbidden)")

    # Admin cannot assign students to faculty -> 403 Forbidden
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CO_{ts}"]
    }, token=admin_token)
    assert st == 403, f"Expected 403 for Admin assigning faculty-student, got {st}: {res}"
    print("[PASS] Admin denied from Faculty-Student Assignment (403 Forbidden)")

    # Admin CAN view all students, faculty, reports, dashboard stats
    st, res = request("GET", "/api/students", token=admin_token)
    assert st == 200 and len(res.get("students", [])) >= 3, "Admin student view failed"
    st, res = request("GET", "/api/dashboard/stats", token=admin_token)
    assert st == 200 and ("departmentStats" in res.get("stats", {}) or "departmentStats" in res), "Admin dashboard stats failed"
    print("[PASS] Admin can view college-wide statistics and directories")

    # ----------------------------------------------------
    # 3. HOD MANAGEMENT & SCOPING
    # ----------------------------------------------------
    print("\n[TEST 2] Testing HOD Department Scoping & Assignment...")

    # HOD can assign faculty in own department to students in own department -> 200 OK
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CO_{ts}", f"STU_CO2_{ts}"]
    }, token=hod_token)
    assert st == 200, f"HOD assign within dept failed: {res}"
    print("[PASS] HOD successfully assigned own department faculty to own students")

    # HOD CANNOT assign civil faculty to computer students -> 403 Forbidden
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CI_{ts}",
        "student_ids": [f"STU_CO_{ts}"]
    }, token=hod_token)
    assert st == 403, f"Expected 403 for cross-dept faculty assign, got {st}: {res}"
    print("[PASS] HOD blocked from assigning other department faculty (403 Forbidden)")

    # HOD CANNOT assign computer faculty to civil student -> 403 Forbidden
    st, res = request("POST", "/api/faculty-students/assign", {
        "faculty_id": f"FAC_CO_{ts}",
        "student_ids": [f"STU_CI_{ts}"]
    }, token=hod_token)
    assert st == 403, f"Expected 403 for cross-dept student assign, got {st}: {res}"
    print("[PASS] HOD blocked from assigning other department student (403 Forbidden)")

    # HOD CANNOT manage HOD accounts -> 403 Forbidden
    st, res = request("POST", "/api/hods", {
        "department": "Computer Engineering",
        "name": "Impostor HOD"
    }, token=hod_token)
    assert st == 403, f"Expected 403 for HOD managing HODs, got {st}: {res}"
    print("[PASS] HOD blocked from HOD management (403 Forbidden)")

    # HOD CANNOT reset database -> 403 Forbidden
    st, res = request("POST", "/api/admin/data/reset-database", {"confirmation": "DELETE ALL DATA"}, token=hod_token)
    assert st == 403, f"Expected 403 for HOD reset database, got {st}: {res}"
    print("[PASS] HOD blocked from database controls (403 Forbidden)")

    # ----------------------------------------------------
    # 4. FACULTY PERMISSIONS & SCOPING
    # ----------------------------------------------------
    print("\n[TEST 3] Testing Faculty Scope & Academic Restrictions...")

    # Faculty CAN view assigned students -> 200 OK
    st, res = request("GET", "/api/students", token=faculty_token)
    assert st == 200, f"Faculty get students failed: {res}"
    assigned_stu_ids = [s["id"] for s in res["students"]]
    assert f"STU_CO_{ts}" in assigned_stu_ids and f"STU_CO2_{ts}" in assigned_stu_ids, f"Assigned students missing: {assigned_stu_ids}"
    assert f"STU_CI_{ts}" not in assigned_stu_ids, "Faculty saw unassigned student from another department!"
    print("[PASS] Faculty correctly sees only assigned students")

    # Faculty CAN mark attendance for assigned student -> 200 OK
    st, res = request("POST", "/api/attendance", {
        "studentId": f"STU_CO_{ts}",
        "subject": "Data Structures",
        "status": "Present",
        "date": "2026-09-04"
    }, token=faculty_token)
    assert st == 200, f"Faculty mark attendance failed: {res}"
    print("[PASS] Faculty marked attendance for assigned student")

    # Faculty CANNOT mark attendance for unassigned civil student -> 403 Forbidden
    st, res = request("POST", "/api/attendance", {
        "studentId": f"STU_CI_{ts}",
        "subject": "Surveying",
        "status": "Present",
        "date": "2026-09-04"
    }, token=faculty_token)
    assert st == 403, f"Expected 403 when faculty marks unassigned attendance, got {st}: {res}"
    print("[PASS] Faculty blocked from taking attendance for unassigned student (403 Forbidden)")

    # Faculty CANNOT manage faculty members -> 403 Forbidden
    st, res = request("POST", "/api/faculty", {"id": "FAC_FAKE", "name": "Fake"}, token=faculty_token)
    assert st == 403, f"Expected 403 for Faculty add faculty, got {st}: {res}"
    print("[PASS] Faculty blocked from managing faculty members (403 Forbidden)")

    # Faculty CANNOT access database controls -> 403 Forbidden
    st, res = request("POST", "/api/admin/data/reset-database", {"confirmation": "DELETE ALL DATA"}, token=faculty_token)
    assert st == 403, f"Expected 403 for Faculty reset database, got {st}: {res}"
    print("[PASS] Faculty blocked from database controls (403 Forbidden)")

    # ----------------------------------------------------
    # 5. STUDENT PERMISSIONS & IDOR PROTECTION
    # ----------------------------------------------------
    print("\n[TEST 4] Testing Student Scope & IDOR Protection...")

    # Student CAN view own attendance -> 200 OK
    st, res = request("GET", "/api/attendance", token=student_token)
    assert st == 200, f"Student get attendance failed: {res}"
    for att in res.get("attendance", []):
        assert att["student_id"] == f"STU_CO_{ts}", f"IDOR Leak: Student saw peer attendance {att}"
    print("[PASS] Student sees only own attendance")

    # Student CANNOT view peer's ID card -> 403 Forbidden
    st, res = request("GET", f"/api/students/id-card?id=STU_CO2_{ts}", token=student_token)
    assert st == 403, f"Expected 403 for student ID card IDOR, got {st}: {res}"
    print("[PASS] Student blocked from viewing peer ID card (403 Forbidden)")

    # Student CANNOT mark attendance -> 403 Forbidden
    st, res = request("POST", "/api/attendance", {
        "studentId": f"STU_CO_{ts}",
        "subject": "Data Structures",
        "status": "Present"
    }, token=student_token)
    assert st == 403, f"Expected 403 for student editing attendance, got {st}: {res}"
    print("[PASS] Student blocked from entering attendance (403 Forbidden)")

    # Student CANNOT manage HOD or Database Controls -> 403 Forbidden
    st, res = request("POST", "/api/hods", {"department": "Computer Engineering", "name": "Fake"}, token=student_token)
    assert st == 403
    st, res = request("POST", "/api/admin/data/reset-database", {"confirmation": "DELETE ALL DATA"}, token=student_token)
    assert st == 403
    print("[PASS] Student blocked from administrative and database controls (403 Forbidden)")

    print("\n" + "=" * 70)
    print("ALL 4-ROLE PERMISSION & AUTHORIZATION TESTS PASSED SUCCESSFULLY (100%)")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
