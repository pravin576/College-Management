import http.client
import json
import os
import sys
import time
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from server import ERPRequestHandler, init_db
from config.database import get_db_connection
from auth.utils import hash_password
import socketserver

PORT = 8012
httpd = None

def start_server():
    global httpd
    init_db()
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), ERPRequestHandler)
    httpd.serve_forever()

def stop_server():
    global httpd
    if httpd:
        httpd.shutdown()
        httpd.server_close()

def make_req(method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", PORT)
    hdrs = headers or {}
    data = body
    if isinstance(body, dict):
        data = json.dumps(body).encode('utf-8')
        if 'Content-Type' not in hdrs:
            hdrs['Content-Type'] = 'application/json'
    elif isinstance(body, str):
        data = body.encode('utf-8')
    
    conn.request(method, path, body=data, headers=hdrs)
    res = conn.getresponse()
    resp_body = res.read()
    conn.close()
    
    parsed = None
    try:
        parsed = json.loads(resp_body.decode('utf-8'))
    except Exception:
        parsed = resp_body
    return res.status, parsed, res.getheaders()

def run_tests():
    print("==================================================")
    print("TESTING USER REGISTRATION, APPROVAL & LOGIN STATUS")
    print("==================================================")

    db = get_db_connection()
    c = db.cursor(dictionary=True)

    # Clean up test accounts if existing
    c.execute("DELETE FROM users WHERE username LIKE 'test_%'")
    c.execute("DELETE FROM faculty WHERE id LIKE 'TFAC_%'")
    c.execute("DELETE FROM hods WHERE faculty_id LIKE 'THOD_%'")
    db.commit()

    # Ensure main admin exists
    c.execute("SELECT id FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username, password, role, name, email, department, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            ("admin", hash_password("admin123"), "Administrator", "System Administrator", "admin@college.edu", "Administration", "Active")
        )
    else:
        c.execute("UPDATE users SET password = %s, status = 'Active' WHERE username = 'admin'", (hash_password("admin123"),))
    db.commit()

    # --- TEST SUITE 1: FACULTY AUTHORIZATION FLOW ---
    print("\n--- 1. FACULTY AUTHORIZATION & STATUS SYNCHRONIZATION ---")
    ts = int(time.time() * 1000) % 100000
    fac_user = f"test_fac_{ts}"
    fac_id = f"TFAC_{ts}"
    fac_email = f"test_fac_{ts}@college.edu"

    # A. Register Faculty -> Pending
    fac_reg_payload = {
        "role": "Faculty",
        "name": f"Dr. Faculty {ts}",
        "email": fac_email,
        "mobile": f"98{ts:08d}",
        "department": "Computer Engineering",
        "facultyId": fac_id,
        "designation": "Assistant Professor",
        "experience": "4 Years",
        "username": fac_user,
        "password": "FacultyPassword@123",
        "confirmPassword": "FacultyPassword@123"
    }
    status, res, _ = make_req("POST", "/api/register", fac_reg_payload)
    assert status == 200 and res.get("success"), f"Faculty registration failed: {res}"
    print("[PASS] 1.A Faculty registered successfully with Pending status")

    # Verify database values in MySQL for both tables
    c.execute("SELECT status, role FROM users WHERE username = %s", (fac_user,))
    user_row = c.fetchone()
    assert user_row and user_row["status"] == "Pending", f"users.status not Pending: {user_row}"

    c.execute("SELECT status FROM faculty WHERE id = %s", (fac_id,))
    fac_row = c.fetchone()
    assert fac_row and fac_row["status"] == "Pending", f"faculty.status not Pending: {fac_row}"
    print("[PASS] 1.A.1 Database verified: users.status = 'Pending' AND faculty.status = 'Pending'")

    # E. Pending Faculty Login -> MUST be rejected with 403
    status, res, _ = make_req("POST", "/api/login", {"username": fac_user, "password": "FacultyPassword@123"})
    assert status == 403, f"Pending faculty login must be 403, got: {status}, {res}"
    assert "pending authorization" in res.get("message", "").lower(), f"Pending message mismatch: {res}"
    print("[PASS] 1.E Pending Faculty login blocked with exact pending message (403)")

    # Login as Admin to approve Faculty
    status, res, _ = make_req("POST", "/api/login", {"username": "admin", "password": "admin123"})
    assert status == 200 and res.get("success"), "Admin login failed"
    admin_headers = {"Authorization": f"Bearer {res['token']}"}

    # B. Admin Approves Faculty
    db.commit()
    c.execute("SELECT id FROM users WHERE username = %s", (fac_user,))
    user_db_id = c.fetchone()["id"]

    status, res, _ = make_req("POST", "/api/admin/approve-user", {"id": user_db_id}, headers=admin_headers)
    assert status == 200 and res.get("success"), f"Admin approve faculty failed: {res}"
    print("[PASS] 1.B Administrator approved Faculty account")

    # Verify both tables are updated to Active in MySQL
    db.commit()
    c.execute("SELECT status FROM users WHERE id = %s", (user_db_id,))
    assert c.fetchone()["status"] == "Active", "users.status not updated to Active after approval"

    db.commit()
    c.execute("SELECT status FROM faculty WHERE id = %s", (fac_id,))
    assert c.fetchone()["status"] == "Active", "faculty.status not updated to Active after approval"
    print("[PASS] 1.B.1 Database verified: users.status = 'Active' AND faculty.status = 'Active'")

    # C. Faculty Login with correct password -> SUCCESS (200)
    status, res, _ = make_req("POST", "/api/login", {"username": fac_user, "password": "FacultyPassword@123"})
    assert status == 200 and res.get("success"), f"Approved Faculty login failed: {res}"
    assert res["user"]["role"] == "Faculty" and res["user"]["status"] == "Active"
    print("[PASS] 1.C Approved Faculty logged in successfully (200)")

    # Login by email
    status, res, _ = make_req("POST", "/api/login", {"username": fac_email, "password": "FacultyPassword@123"})
    assert status == 200 and res.get("success"), f"Faculty login by email failed: {res}"
    print("[PASS] 1.C.1 Faculty login by email succeeded (200)")

    # D. Faculty wrong password -> 401
    status, res, _ = make_req("POST", "/api/login", {"username": fac_user, "password": "WrongPassword"})
    assert status == 401, f"Wrong password should return 401, got: {status}"
    print("[PASS] 1.D Faculty wrong password rejected (401)")


    # --- TEST SUITE 2: HOD AUTHORIZATION FLOW ---
    print("\n--- 2. HOD AUTHORIZATION & STATUS SYNCHRONIZATION ---")
    hod_ts = ts + 1
    hod_user = f"test_hod_{hod_ts}"
    hod_id = f"THOD_{hod_ts}"
    hod_email = f"test_hod_{hod_ts}@college.edu"
    hod_dept = f"Automobile Engineering"

    # Clear any existing HOD for this department
    db.commit()
    c.execute("DELETE FROM hods WHERE department = %s", (hod_dept,))
    db.commit()

    # A. Register HOD -> Pending
    hod_reg_payload = {
        "role": "HOD",
        "name": f"Dr. HOD {hod_ts}",
        "email": hod_email,
        "mobile": f"97{hod_ts:08d}",
        "department": hod_dept,
        "facultyId": hod_id,
        "qualification": "Ph.D. in Automobile Engineering",
        "experience": "12 Years",
        "username": hod_user,
        "password": "HODPassword@123",
        "confirmPassword": "HODPassword@123"
    }
    status, res, _ = make_req("POST", "/api/register", hod_reg_payload)
    assert status == 200 and res.get("success"), f"HOD registration failed: {res}"
    print("[PASS] 2.A HOD registered successfully with Pending status")

    # Verify both tables in MySQL
    db.commit()
    c.execute("SELECT status, role FROM users WHERE username = %s", (hod_user,))
    user_row = c.fetchone()
    assert user_row and user_row["status"] == "Pending", f"users.status not Pending: {user_row}"

    db.commit()
    c.execute("SELECT status FROM hods WHERE faculty_id = %s", (hod_id,))
    hod_row = c.fetchone()
    assert hod_row and hod_row["status"] == "Pending", f"hods.status not Pending: {hod_row}"
    print("[PASS] 2.A.1 Database verified: users.status = 'Pending' AND hods.status = 'Pending'")

    # E. Pending HOD Login -> MUST be rejected with 403
    status, res, _ = make_req("POST", "/api/login", {"username": hod_user, "password": "HODPassword@123"})
    assert status == 403, f"Pending HOD login must be 403, got: {status}, {res}"
    assert "pending authorization" in res.get("message", "").lower(), f"Pending message mismatch: {res}"
    print("[PASS] 2.E Pending HOD login blocked with exact pending message (403)")

    # F. Second HOD for same department -> MUST be rejected
    second_hod_payload = {
        "role": "HOD",
        "name": "Another HOD",
        "email": f"another_hod_{hod_ts}@college.edu",
        "mobile": f"96{hod_ts:08d}",
        "department": hod_dept,
        "facultyId": f"THOD_2_{hod_ts}",
        "username": f"test_hod2_{hod_ts}",
        "password": "HODPassword@123",
        "confirmPassword": "HODPassword@123"
    }
    status, res, _ = make_req("POST", "/api/register", second_hod_payload)
    assert status == 400 and "already has an assigned hod" in res.get("message", "").lower(), f"Second HOD should be rejected: {status}, {res}"
    print("[PASS] 2.F Department-wise single HOD constraint verified (Second HOD rejected)")

    # B. Admin Approves HOD
    db.commit()
    c.execute("SELECT id FROM users WHERE username = %s", (hod_user,))
    hod_db_id = c.fetchone()["id"]

    status, res, _ = make_req("POST", "/api/admin/approve-user", {"id": hod_db_id}, headers=admin_headers)
    assert status == 200 and res.get("success"), f"Admin approve HOD failed: {res}"
    print("[PASS] 2.B Administrator approved HOD account")

    # Verify both tables are Active in MySQL
    db.commit()
    c.execute("SELECT status FROM users WHERE id = %s", (hod_db_id,))
    assert c.fetchone()["status"] == "Active", "users.status not Active"

    db.commit()
    c.execute("SELECT status FROM hods WHERE faculty_id = %s", (hod_id,))
    assert c.fetchone()["status"] == "Active", "hods.status not Active"
    print("[PASS] 2.B.1 Database verified: users.status = 'Active' AND hods.status = 'Active'")

    # C. HOD Login with correct password -> SUCCESS (200)
    status, res, _ = make_req("POST", "/api/login", {"username": hod_user, "password": "HODPassword@123"})
    assert status == 200 and res.get("success"), f"Approved HOD login failed: {res}"
    assert res["user"]["role"] == "HOD" and res["user"]["status"] == "Active"
    print("[PASS] 2.C Approved HOD logged in successfully (200)")

    # D. HOD wrong password -> 401
    status, res, _ = make_req("POST", "/api/login", {"username": hod_user, "password": "WrongPassword"})
    assert status == 401, f"Wrong password should return 401: {status}"
    print("[PASS] 2.D HOD wrong password rejected (401)")


    # --- TEST SUITE 3: ADMINISTRATOR AUTHORIZATION FLOW ---
    print("\n--- 3. ADMINISTRATOR AUTHORIZATION FLOW ---")

    # A. Default Administrator login
    status, res, _ = make_req("POST", "/api/login", {"username": "admin", "password": "admin123"})
    assert status == 200 and res.get("success"), f"Default Admin login failed: {res}"
    assert res["user"]["role"] == "Administrator" and res["user"]["status"] == "Active"
    print("[PASS] 3.A Default Administrator login succeeded (200, Active)")

    # B. Administrator wrong password
    status, res, _ = make_req("POST", "/api/login", {"username": "admin", "password": "WrongAdminPassword"})
    assert status == 401, f"Admin wrong password should return 401: {status}"
    print("[PASS] 3.B Administrator wrong password rejected (401)")

    # C. Unauthorized public user cannot register Administrator account
    public_admin_payload = {
        "role": "Administrator",
        "name": "Attacker Admin",
        "email": f"attacker_{ts}@college.edu",
        "mobile": f"91{ts:08d}",
        "username": f"test_fake_admin_{ts}",
        "password": "Password@123",
        "confirmPassword": "Password@123"
    }
    status, res, _ = make_req("POST", "/api/register", public_admin_payload)
    assert status == 403, f"Public admin registration must be blocked with 403, got: {status}, {res}"
    print("[PASS] 3.C Unauthorized public user blocked from registering Administrator (403 Forbidden)")

    # D. Authenticated Administrator creates new Administrator account
    new_admin_user = f"test_subadmin_{ts}"
    auth_admin_payload = {
        "role": "Administrator",
        "name": f"Sub Admin {ts}",
        "email": f"subadmin_{ts}@college.edu",
        "mobile": f"92{ts:08d}",
        "username": new_admin_user,
        "password": "SubAdminPassword@123",
        "confirmPassword": "SubAdminPassword@123"
    }
    status, res, _ = make_req("POST", "/api/register", auth_admin_payload, headers=admin_headers)
    assert status == 200 and res.get("success"), f"Authenticated admin creation failed: {res}"
    print("[PASS] 3.D Authenticated Administrator created new Administrator account")

    # New Admin Login -> Active
    status, res, _ = make_req("POST", "/api/login", {"username": new_admin_user, "password": "SubAdminPassword@123"})
    assert status == 200 and res.get("success"), f"New Administrator login failed: {res}"
    assert res["user"]["role"] == "Administrator" and res["user"]["status"] == "Active"
    print("[PASS] 3.D.1 New Administrator logged in successfully (200)")

    # Cleanup test accounts
    c.execute("DELETE FROM users WHERE username LIKE 'test_%'")
    c.execute("DELETE FROM faculty WHERE id LIKE 'TFAC_%'")
    c.execute("DELETE FROM hods WHERE faculty_id LIKE 'THOD_%'")
    db.commit()
    c.close()
    db.close()

    print("\n==================================================")
    print("ALL TEST SCENARIOS PASSED WITH 100% SYNCHRONIZATION!")
    print("==================================================")

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(1.0)
    try:
        run_tests()
    finally:
        stop_server()
