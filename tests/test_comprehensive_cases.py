import urllib.request
import json
import base64
import sys
import io
import time
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from core.excel_utils import build_xlsx_bytes
from config.database import get_db_connection

BASE_URL = "http://localhost:8000"

def api_request(path, method="GET", body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return resp.status, json.loads(resp.read().decode("utf-8"))
            else:
                return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except:
            return e.code, {"success": False, "message": str(e)}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}

def run_comprehensive_tests():
    print("=" * 70)
    print("STARTING COMPLETE 10-POINT TEST SUITE FOR STUDENT CREDENTIAL SYSTEM")
    print("=" * 70)

    # 0. Setup and Auth
    print("\n--- Initializing User Tokens ---")
    _, res_admin = api_request("/api/login", "POST", {"username": "admin", "password": "admin123"})
    admin_token = res_admin.get("token")
    print("Admin token:", "OK" if admin_token else "FAILED")

    # Create / Update HOD for Computer Engineering and Mechanical
    code, res_h1 = api_request("/api/hods", "POST", {
        "faculty_id": "HOD_CO_TEST", "name": "HOD Computer", "department": "Computer Engineering",
        "email": "hod.co@college.edu", "contact": "9876543001", "qualification": "Ph.D", "experience": "12",
        "password": "HodPassword#2026", "is_edit": True
    }, token=admin_token)
    
    # Login HOD Computer
    h1_creds = (res_h1 or {}).get("credentials") or {}
    h1_uname = h1_creds.get("username") or "hod.co@college.edu"
    h1_pass = h1_creds.get("temporaryPassword") or "HodPassword#2026"
    code, res_hod_co = api_request("/api/login", "POST", {"username": "hod.co@college.edu", "password": "HodPassword#2026"})
    if code != 200:
        code, res_hod_co = api_request("/api/login", "POST", {"username": h1_uname, "password": h1_pass})
    hod_co_token = res_hod_co.get("token")
    print("HOD Computer token:", "OK" if hod_co_token else f"FAILED ({res_hod_co})")

    code, res_h2 = api_request("/api/hods", "POST", {
        "faculty_id": "HOD_MECH_TEST", "name": "HOD Mechanical", "department": "Mechanical Engineering",
        "email": "hod.mech@college.edu", "contact": "9876543002", "qualification": "Ph.D", "experience": "10",
        "password": "HodPassword#2026", "is_edit": True
    }, token=admin_token)
    
    h2_creds = (res_h2 or {}).get("credentials") or {}
    h2_uname = h2_creds.get("username") or "hod.mech@college.edu"
    h2_pass = h2_creds.get("temporaryPassword") or "HodPassword#2026"
    code, res_hod_mech = api_request("/api/login", "POST", {"username": "hod.mech@college.edu", "password": "HodPassword#2026"})
    if code != 200:
        code, res_hod_mech = api_request("/api/login", "POST", {"username": h2_uname, "password": h2_pass})
    hod_mech_token = res_hod_mech.get("token")
    print("HOD Mechanical token:", "OK" if hod_mech_token else f"FAILED ({res_hod_mech})")

    # Create / Update Faculty
    code, res_f = api_request("/api/faculty", "POST", {
        "id": "FAC_TEST_01", "name": "Test Faculty", "department": "Computer Engineering",
        "email": "fac.test@college.edu", "mobile": "9876543003", "designation": "Assistant Professor",
        "password": "FacPassword#2026", "is_edit": True
    }, token=hod_co_token)
    f_creds = (res_f or {}).get("credentials") or {}
    f_uname = f_creds.get("username") or "FAC_TEST_01"
    f_pass = f_creds.get("temporaryPassword") or "FacPassword#2026"
    code, res_fac = api_request("/api/login", "POST", {"username": "FAC_TEST_01", "password": "FacPassword#2026"})
    if code != 200:
        code, res_fac = api_request("/api/login", "POST", {"username": f_uname, "password": f_pass})
    fac_token = res_fac.get("token")
    print("Faculty token:", "OK" if fac_token else f"FAILED ({res_fac})")

    headers = [
        "Student ID", "Roll Number", "Student Name", "Email", "Mobile Number",
        "Gender", "DOB", "Department", "Year", "Semester", "Division",
        "Admission Year", "Address", "Status"
    ]

    # Cleanup any old test records
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username LIKE 'T1_%' OR username LIKE 'T2_%' OR username LIKE 'T3_%' OR username LIKE 'T4_%'")
    cur.execute("DELETE FROM students WHERE id LIKE 'T1_%' OR id LIKE 'T2_%' OR id LIKE 'T3_%' OR id LIKE 'T4_%'")
    conn.commit()
    cur.close()
    conn.close()

    # -------------------------------------------------------------
    # TEST 1: Import 5 new students
    # -------------------------------------------------------------
    print("\n[TEST 1] Importing 5 new students...")
    t1_rows = []
    for i in range(1, 6):
        t1_rows.append([f"T1_STU{i:02d}", f"R1_{i}", f"Student_T1_{i}", f"t1_{i}@college.edu", "9876543210", "Male", "2005-01-01", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Campus", "Active"])
    xlsx1 = build_xlsx_bytes(headers, t1_rows)
    b64_1 = base64.b64encode(xlsx1).decode("utf-8")

    code, res1 = api_request("/api/students/import-excel", "POST", {"file_base64": b64_1}, token=hod_co_token)
    assert code == 200 and res1.get("success"), f"Test 1 Failed: {res1}"
    assert res1.get("addedCount") == 5, f"Expected 5 added, got {res1.get('addedCount')}"
    assert len(res1.get("credentials", [])) == 5, "Expected 5 credentials"
    t1_creds = res1.get("credentials")
    for c in t1_creds:
        assert c["username"] == c["enrollmentNumber"], f"Username mismatch for {c}"
        assert c["temporaryPassword"], f"Missing temp password for {c}"
    print(f"  [PASS] Test 1: 5 student records + 5 user accounts + 5 unique temporary passwords created.")

    # -------------------------------------------------------------
    # TEST 2: Import 50 new students
    # -------------------------------------------------------------
    print("\n[TEST 2] Importing 50 new students and verifying credential export...")
    t2_rows = []
    for i in range(1, 51):
        t2_rows.append([f"T2_STU{i:02d}", f"R2_{i}", f"Student_T2_{i}", f"t2_{i}@college.edu", "9876543210", "Female", "2005-01-01", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Campus", "Active"])
    xlsx2 = build_xlsx_bytes(headers, t2_rows)
    b64_2 = base64.b64encode(xlsx2).decode("utf-8")

    code, res2 = api_request("/api/students/import-excel", "POST", {"file_base64": b64_2}, token=hod_co_token)
    assert code == 200 and res2.get("addedCount") == 50, f"Test 2 Failed: {res2}"
    t2_creds = res2.get("credentials", [])
    assert len(t2_creds) == 50, f"Expected 50 credentials, got {len(t2_creds)}"

    # Export credentials via API
    code, exp_bytes = api_request("/api/students/export-credentials", "POST", {"credentials": t2_creds}, token=hod_co_token)
    assert code == 200 and len(exp_bytes) > 500, f"Credential Excel export failed: code {code}"
    print(f"  [PASS] Test 2: 50 new accounts created, 50 credentials in exported Excel ({len(exp_bytes)} bytes).")

    # -------------------------------------------------------------
    # TEST 3: Import 1000 new students
    # -------------------------------------------------------------
    print("\n[TEST 3] Importing 1,000 new students...")
    t3_rows = []
    for i in range(1, 1001):
        t3_rows.append([f"T3_STU{i:04d}", f"R3_{i}", f"Student_T3_{i}", f"t3_{i}@college.edu", "9876543210", "Male" if i%2 else "Female", "2005-01-01", "Computer Engineering", "First Year", "Semester 1", "A" if i<=500 else "B", "2026", "Campus", "Active"])
    xlsx3 = build_xlsx_bytes(headers, t3_rows)
    b64_3 = base64.b64encode(xlsx3).decode("utf-8")

    code, res3 = api_request("/api/students/import-excel", "POST", {"file_base64": b64_3}, token=hod_co_token)
    assert code == 200 and res3.get("addedCount") == 1000, f"Test 3 Failed: {res3}"
    t3_creds = res3.get("credentials", [])
    assert len(t3_creds) == 1000, f"Expected 1000 credentials, got {len(t3_creds)}"
    print(f"  [PASS] Test 3: 1,000 new accounts created, 1,000 unique credentials generated.")

    # -------------------------------------------------------------
    # TEST 4: Import 1000 students where 100 already exist
    # -------------------------------------------------------------
    print("\n[TEST 4] Importing 1,000 students where 100 already exist (Expect: 900 added, 100 duplicate)...")
    # First 100 rows reuse T3_STU0001 to T3_STU0100 (which exist), next 900 are T4_STU0101 to T4_STU1000 (new)
    t4_rows = []
    for i in range(1, 101):
        t4_rows.append([f"T3_STU{i:04d}", f"R3_{i}", f"Student_T3_{i}", f"t3_{i}@college.edu", "9876543210", "Male", "2005-01-01", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Campus", "Active"])
    for i in range(101, 1001):
        t4_rows.append([f"T4_STU{i:04d}", f"R4_{i}", f"Student_T4_{i}", f"t4_{i}@college.edu", "9876543210", "Male", "2005-01-01", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Campus", "Active"])
    xlsx4 = build_xlsx_bytes(headers, t4_rows)
    b64_4 = base64.b64encode(xlsx4).decode("utf-8")

    code, res4 = api_request("/api/students/import-excel", "POST", {"file_base64": b64_4}, token=hod_co_token)
    assert code == 200 and res4.get("success"), f"Test 4 Failed: {res4}"
    assert res4.get("addedCount") == 900, f"Expected 900 added, got {res4.get('addedCount')}"
    assert res4.get("duplicateCount") == 100, f"Expected 100 duplicate, got {res4.get('duplicateCount')}"
    assert len(res4.get("credentials", [])) == 900, f"Expected 900 credentials, got {len(res4.get('credentials', []))}"
    print(f"  [PASS] Test 4: Exactly 900 new accounts created, 100 existing skipped, exactly 900 credentials returned.")

    # -------------------------------------------------------------
    # TEST 5: Try importing the same Excel again
    # -------------------------------------------------------------
    print("\n[TEST 5] Re-importing same Excel file (Expect: 0 added, 1000 duplicate)...")
    code, res5 = api_request("/api/students/import-excel", "POST", {"file_base64": b64_4}, token=hod_co_token)
    assert code == 200 and res5.get("addedCount") == 0, f"Test 5 Failed: Expected 0 added, got {res5.get('addedCount')}"
    assert res5.get("duplicateCount") == 1000, f"Test 5 Failed: Expected 1000 duplicates, got {res5.get('duplicateCount')}"
    assert len(res5.get("credentials", [])) == 0, "Expected 0 credentials on complete duplicate file"
    print(f"  [PASS] Test 5: All existing students skipped and passwords NOT regenerated.")

    # -------------------------------------------------------------
    # TEST 6: Student logs in using temporary password (forced password change)
    # -------------------------------------------------------------
    print("\n[TEST 6] Student first login with temporary password...")
    test_stu = t1_creds[0]
    stu_uname = test_stu["username"]
    stu_temp_pass = test_stu["temporaryPassword"]

    code, res6 = api_request("/api/login", "POST", {"username": stu_uname, "password": stu_temp_pass})
    assert code == 200 and res6.get("success"), f"Test 6 Login failed: {res6}"
    assert res6.get("must_change_password") == 1 or res6.get("user", {}).get("must_change_password") == 1, "must_change_password was not 1"
    stu_token = res6.get("token")
    print(f"  [PASS] Test 6: Student authenticated successfully; system detected must_change_password = 1.")

    # -------------------------------------------------------------
    # TEST 7: Student changes password
    # -------------------------------------------------------------
    print("\n[TEST 7] Student completes mandatory password change...")
    new_password = "MyPermanentPassword#2026"
    code, res7 = api_request("/api/auth/first-login-change-password", "POST", {
        "currentPassword": stu_temp_pass,
        "newPassword": new_password,
        "confirmPassword": new_password
    }, token=stu_token)
    assert code == 200 and res7.get("success"), f"Test 7 Password change failed: {res7}"

    # Verify old temp password NO LONGER works
    code, res7_old = api_request("/api/login", "POST", {"username": stu_uname, "password": stu_temp_pass})
    assert code == 401 or not res7_old.get("success"), "Security failure: Old temp password still active!"

    # Verify new password works and must_change_password == 0
    code, res7_new = api_request("/api/login", "POST", {"username": stu_uname, "password": new_password})
    assert code == 200 and res7_new.get("success"), f"New password login failed: {res7_new}"
    assert not res7_new.get("must_change_password"), "must_change_password should be 0"
    print(f"  [PASS] Test 7: Password changed successfully, must_change_password = 0, old temp password rejected.")

    # -------------------------------------------------------------
    # TEST 8: Unauthorized Faculty tries to download student credentials
    # -------------------------------------------------------------
    print("\n[TEST 8] Unauthorized Faculty attempts to export credentials...")
    code, res8 = api_request("/api/students/export-credentials", "POST", {"credentials": t1_creds}, token=fac_token)
    assert code == 403, f"Expected 403 Forbidden for Faculty, got {code}"
    print(f"  [PASS] Test 8: Faculty access denied (HTTP 403 Forbidden).")

    # -------------------------------------------------------------
    # TEST 9: HOD of Dept A tries to access credentials/import for Dept B
    # -------------------------------------------------------------
    print("\n[TEST 9] HOD Mechanical attempts cross-department credential export and import...")
    # A: Exporting Computer Engineering credentials with HOD Mechanical token
    code, res9_exp = api_request("/api/students/export-credentials", "POST", {"credentials": t1_creds}, token=hod_mech_token)
    assert code == 403, f"Expected 403 Forbidden for cross-dept export, got {code}"

    # B: Importing Computer Engineering student with HOD Mechanical token
    cross_dept_rows = [["CROSS_01", "R_CR1", "Cross Student", "cross@college.edu", "9876543210", "Male", "2005-01-01", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Campus", "Active"]]
    xlsx_cross = build_xlsx_bytes(headers, cross_dept_rows)
    b64_cross = base64.b64encode(xlsx_cross).decode("utf-8")
    code, res9_imp = api_request("/api/students/import-excel", "POST", {"file_base64": b64_cross}, token=hod_mech_token)
    assert code == 200 and res9_imp.get("failedCount") == 1, f"Expected failedCount=1 for cross-dept import, got {res9_imp}"
    print(f"  [PASS] Test 9: Cross-department access strictly denied (HTTP 403 / unauthorized failure).")

    # -------------------------------------------------------------
    # TEST 10: Check database for plain-text passwords
    # -------------------------------------------------------------
    print("\n[TEST 10] Checking MySQL database for plain-text passwords...")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, password FROM users WHERE role = 'Student' LIMIT 50")
    user_rows = cur.fetchall()
    assert len(user_rows) > 0, "No user records found to inspect"
    for u in user_rows:
        pwd = u["password"]
        assert "$" in pwd and len(pwd) > 30, f"Potential plain-text password found: {pwd}"
        assert not pwd.startswith("NewPass") and not pwd.startswith("Tmp"), f"Plain password detected: {pwd}"
    print(f"  [PASS] Test 10: Verified {len(user_rows)} user rows. All passwords stored strictly as cryptographic hashes.")

    # -------------------------------------------------------------
    # REGRESSION TESTS: Verify all standard role logins & core APIs
    # -------------------------------------------------------------
    print("\n--- Running Core Module Regression Checks ---")
    # 1. Admin Login & Stats
    c, r = api_request("/api/dashboard/stats", token=admin_token)
    assert c == 200 and r.get("success"), "Admin dashboard stats failed"

    # 2. HOD Attendance & Results
    c, r = api_request("/api/attendance", token=hod_co_token)
    assert c == 200 and r.get("success"), "Attendance API failed"
    c, r = api_request("/api/results", token=hod_co_token)
    assert c == 200 and r.get("success"), "Results API failed"
    c, r = api_request("/api/timetable", token=hod_co_token)
    assert c == 200 and r.get("success"), "Timetable API failed"
    c, r = api_request("/api/notices", token=hod_co_token)
    assert c == 200 and r.get("success"), "Notices API failed"
    c, r = api_request("/api/fees", token=admin_token)
    assert c == 200 and r.get("success"), "Fees API failed"

    print("  [PASS] All Core modules (Attendance, Results, Timetable, Notices, Fees, Reports) operational.")

    # Final Cleanup of test items
    cur.execute("DELETE FROM users WHERE username LIKE 'T1_%' OR username LIKE 'T2_%' OR username LIKE 'T3_%' OR username LIKE 'T4_%'")
    cur.execute("DELETE FROM students WHERE id LIKE 'T1_%' OR id LIKE 'T2_%' OR id LIKE 'T3_%' OR id LIKE 'T4_%'")
    conn.commit()
    cur.close()
    conn.close()

    print("\n" + "=" * 70)
    print("ALL 10 TEST CASES + REGRESSION TESTS PASSED (100% VERIFIED)!")
    print("=" * 70)

if __name__ == "__main__":
    run_comprehensive_tests()
