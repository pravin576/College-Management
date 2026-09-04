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

def run_tests():
    print("=" * 60)
    print("RUNNING COMPLETE STUDENT IMPORT & CREDENTIAL VERIFICATION")
    print("=" * 60)

    # 1. Login as Administrator
    print("\n[Step 1] Logging in as Administrator...")
    code, res = api_request("/api/login", "POST", {"username": "admin", "password": "admin123"})
    if code != 200 or not res.get("token"):
        print("FAILED to login as admin:", res)
        sys.exit(1)
    admin_token = res["token"]
    print("Admin logged in successfully. Token obtained.")

    # 2. Test Single Student Creation for GP101, GP102, GP103
    print("\n[Step 2] Testing Single Student Creation for GP101, GP102, GP103...")
    test_students = [
        {"id": "GP101", "rollNumber": "101", "name": "Rahul Patil", "department": "Computer Engineering"},
        {"id": "GP102", "rollNumber": "102", "name": "Priya Patil", "department": "Computer Engineering"},
        {"id": "GP103", "rollNumber": "103", "name": "Amit Deshmukh", "department": "Mechanical Engineering"}
    ]

    student_credentials = {}
    for stu in test_students:
        api_request(f"/api/students?id={stu['id']}", "DELETE", token=admin_token)
        
        code, res = api_request("/api/students", "POST", {
            "id": stu["id"],
            "rollNumber": stu["rollNumber"],
            "name": stu["name"],
            "department": stu["department"],
            "year": "First Year",
            "semester": "Semester 1",
            "division": "A"
        }, token=admin_token)

        assert code == 200 and res.get("success"), f"Failed to create student {stu['id']}: {res}"
        creds = res.get("credentials")
        assert creds, f"No credentials returned for {stu['id']}"
        assert creds["username"] == stu["id"], f"Username mismatch: {creds['username']} vs {stu['id']}"
        assert creds["temporaryPassword"], "No temporary password generated"
        student_credentials[stu["id"]] = creds["temporaryPassword"]
        print(f"Created student {stu['id']}: Username={creds['username']}, Temp Password={creds['temporaryPassword']}")

    # 3. Test First-Login Flow for GP101, GP102, GP103
    print("\n[Step 3] Testing First Login & Password Change Flow...")
    for stu_id, temp_pass in student_credentials.items():
        print(f"\n--- Testing Login for {stu_id} ---")
        code, res = api_request("/api/login", "POST", {"username": stu_id, "password": temp_pass})
        assert code == 200 and res.get("success"), f"Student {stu_id} failed to login with temporary password: {res}"
        assert res.get("must_change_password") == 1 or res.get("user", {}).get("must_change_password") == 1, f"must_change_password flag not set for {stu_id}"
        stu_token = res["token"]
        print(f"  [OK] Successfully logged in with temporary password. must_change_password = 1.")

        new_pass = f"NewPass@{stu_id}#2026"
        code, res = api_request("/api/auth/first-login-change-password", "POST", {
            "currentPassword": temp_pass,
            "newPassword": new_pass,
            "confirmPassword": new_pass
        }, token=stu_token)
        assert code == 200 and res.get("success"), f"Failed first login password change for {stu_id}: {res}"
        print(f"  [OK] Changed password to '{new_pass}'.")

        code, res = api_request("/api/login", "POST", {"username": stu_id, "password": temp_pass})
        assert code == 401 or not res.get("success"), f"Security error: Old temporary password still works for {stu_id}!"
        print(f"  [OK] Old temporary password was rejected (401 Unauthorized).")

        code, res = api_request("/api/login", "POST", {"username": stu_id, "password": new_pass})
        assert code == 200 and res.get("success"), f"New password failed for {stu_id}: {res}"
        assert not res.get("must_change_password"), f"must_change_password should be False/0 after password change"
        print(f"  [OK] Logged in with new password. must_change_password = 0.")

    # 4. Test Student Password Reset by Admin
    print("\n[Step 4] Testing Admin Password Reset for GP101...")
    code, res = api_request("/api/students/reset-password", "POST", {"id": "GP101"}, token=admin_token)
    assert code == 200 and res.get("success"), f"Password reset failed: {res}"
    reset_creds = res.get("credentials")
    assert reset_creds and reset_creds.get("temporaryPassword"), "No new temporary password returned on reset"
    new_temp_pass = reset_creds["temporaryPassword"]
    print(f"  [OK] Password reset successful. New Temp Password={new_temp_pass}")

    code, res = api_request("/api/login", "POST", {"username": "GP101", "password": new_temp_pass})
    assert code == 200 and res.get("success"), f"Login with reset temp password failed: {res}"
    assert res.get("must_change_password") == 1, "must_change_password not set to 1 after reset"
    print(f"  [OK] Student GP101 logged in with newly reset temp password.")

    # 5. Test 1,000 Student Bulk Import
    print("\n[Step 5] Cleaning any previous test records and generating 1,000 Student Records Excel file...")
    from config.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username LIKE 'GP1000_%'")
    cursor.execute("DELETE FROM students WHERE id LIKE 'GP1000_%'")
    conn.commit()
    cursor.close()
    conn.close()

    headers = [
        "Student ID", "Roll Number", "Student Name", "Email", "Mobile Number",
        "Gender", "DOB", "Department", "Year", "Semester", "Division",
        "Admission Year", "Address", "Status"
    ]
    rows = []
    for i in range(1, 1001):
        enroll_no = f"GP1000_{i:04d}"
        roll_no = f"R{i}"
        name = f"Student_{i}"
        email = f"student{i}@college.edu"
        dept = "Computer Engineering" if i <= 500 else "Information Technology"
        rows.append([
            enroll_no, roll_no, name, email, "9876543210",
            "Male" if i % 2 == 1 else "Female", "2005-01-01",
            dept, "First Year", "Semester 1", "A" if i <= 250 else "B",
            "2026", "Campus", "Active"
        ])

    xlsx_bytes = build_xlsx_bytes(headers, rows)
    b64_data = base64.b64encode(xlsx_bytes).decode("utf-8")
    print(f"  [OK] Generated XLSX binary with 1,000 rows (Size: {len(xlsx_bytes)} bytes).")

    print("\n[Step 6] Importing 1,000 Students via POST /api/students/import-excel...")
    t0 = time.time()
    code, res = api_request("/api/students/import-excel", "POST", {"file_base64": b64_data}, token=admin_token)
    t1 = time.time()
    assert code == 200 and res.get("success"), f"Bulk import failed: {res}"

    print(f"  Import finished in {t1 - t0:.2f} seconds.")
    print(f"  Total Records: {res.get('totalRecords')}")
    print(f"  Added Count: {res.get('addedCount')}")
    print(f"  Duplicate Count: {res.get('duplicateCount')}")
    print(f"  Failed Count: {res.get('failedCount')}")

    assert res.get("totalRecords") == 1000, f"Expected 1000 total records, got {res.get('totalRecords')}"
    assert res.get("addedCount") == 1000, f"Expected 1000 added count, got {res.get('addedCount')}"
    assert res.get("failedCount") == 0, f"Expected 0 failed, got {res.get('failedCount')}"
    assert res.get("duplicateCount") == 0, f"Expected 0 duplicates, got {res.get('duplicateCount')}"

    imported_credentials = res.get("credentials", [])
    assert len(imported_credentials) == 1000, f"Expected 1000 credentials, got {len(imported_credentials)}"

    usernames = set()
    passwords = set()
    for c in imported_credentials:
        assert c["username"], "Empty username in credentials"
        assert c["temporaryPassword"], "Empty temporary password in credentials"
        usernames.add(c["username"])
        passwords.add(c["temporaryPassword"])

    assert len(usernames) == 1000, f"Expected 1000 unique usernames, got {len(usernames)}"
    assert len(passwords) == 1000, f"Expected 1000 unique passwords, got {len(passwords)}"
    print(f"  [OK] Verified 1,000 unique usernames and 1,000 unique temporary passwords.")

    # 6. Test Duplicate Import Handling
    print("\n[Step 7] Testing Duplicate Import Handling (Re-importing same 1,000 file)...")
    code, res = api_request("/api/students/import-excel", "POST", {"file_base64": b64_data}, token=admin_token)
    assert code == 200 and res.get("success"), f"Duplicate import call failed: {res}"
    print(f"  Added: {res.get('addedCount')}, Duplicates: {res.get('duplicateCount')}, Failed: {res.get('failedCount')}")
    assert res.get("addedCount") == 0, "Expected 0 added for duplicate import"
    assert res.get("duplicateCount") == 1000, f"Expected 1000 duplicates, got {res.get('duplicateCount')}"
    print(f"  [OK] Duplicate handling verified: 0 added, 1000 marked duplicate.")

    # 7. Test Credential Export
    print("\n[Step 8] Testing Credential Export via POST /api/students/export-credentials...")
    code, export_bytes = api_request("/api/students/export-credentials", "POST", {
        "credentials": imported_credentials
    }, token=admin_token)
    assert code == 200, f"Export credentials failed with code {code}"
    assert len(export_bytes) > 1000, f"Export bytes too small: {len(export_bytes)}"
    print(f"  [OK] Exported credentials XLSX file ({len(export_bytes)} bytes) successfully.")

    # 8. Clean up 1,000 test students and users from database
    print("\n[Step 9] Cleaning up test records from database...")
    from config.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username LIKE 'GP1000_%' OR username IN ('GP101', 'GP102', 'GP103')")
    cursor.execute("DELETE FROM students WHERE id LIKE 'GP1000_%' OR id IN ('GP101', 'GP102', 'GP103')")
    conn.commit()
    cursor.close()
    conn.close()
    print("  [OK] Test cleanup complete.")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY (100% VERIFIED)!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
