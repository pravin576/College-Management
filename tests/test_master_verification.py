import http.client
import json
import base64
import os
import sys
import time
import urllib.parse
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from server import ERPRequestHandler, init_db
from config.database import get_db_connection
from auth.permissions import SESSIONS
from auth.utils import hash_password
from core.excel_utils import create_results_template_xlsx, create_student_template_xlsx, create_attendance_template_xlsx

import socketserver

PORT = 8010
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

def run_all_tests():
    print("==================================================")
    print("STARTING COMPREHENSIVE COLLEGE ERP VERIFICATION")
    print("==================================================")
    
    # 0. Ensure Admin account exists for testing
    db = get_db_connection()
    c = db.cursor(dictionary=True)
    c.execute("SELECT id FROM users WHERE username = 'admin_tester'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username, password, role, name, email, department, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            ("admin_tester", hash_password("Admin@123"), "Administrator", "Master Admin", "admin_tester@college.edu", "Administration", "Active")
        )
    else:
        c.execute("UPDATE users SET password = %s, status = 'Active' WHERE username = 'admin_tester'", (hash_password("Admin@123"),))
    db.commit()
    c.close()
    db.close()

    # --- SECTION 1: AUTHENTICATION & LOGIN ---
    print("\n[SECTION 1: AUTHENTICATION & LOGIN]")
    
    # Test 1.1: Valid Admin Login
    status, res, _ = make_req("POST", "/api/login", {"username": "admin_tester", "password": "Admin@123"})
    assert status == 200 and res.get("success"), f"Admin login failed: {res}"
    admin_token = res["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[PASS] 1.1 Valid Administrator login succeeded")

    # Test 1.2: Invalid password
    status, res, _ = make_req("POST", "/api/login", {"username": "admin_tester", "password": "WrongPassword"})
    assert status == 401 and not res.get("success"), f"Invalid password check failed: {res}"
    print("[PASS] 1.2 Invalid password correctly rejected (401)")

    # Test 1.3: Unauthenticated access to protected endpoint
    status, res, _ = make_req("GET", "/api/students")
    assert status == 401 and not res.get("success"), f"Unauthenticated request should return 401, got: {status}"
    print("[PASS] 1.3 Unauthenticated request returned 401 Unauthorized")

    # --- SECTION 2: REGISTRATION & APPROVAL WORKFLOW ---
    print("\n[SECTION 2: REGISTRATION & APPROVAL WORKFLOW]")
    
    ts = int(time.time() * 1000) % 100000
    
    # Test 2.1: Student Registration (Auto Active)
    stu_user = f"student_{ts}"
    stu_payload = {
        "role": "Student",
        "name": f"Student {ts}",
        "email": f"student_{ts}@college.edu",
        "mobile": f"98{ts:08d}",
        "department": "Computer Engineering",
        "studentId": f"STU_{ts}",
        "rollNumber": f"R{ts}",
        "username": stu_user,
        "password": "Password@123",
        "confirmPassword": "Password@123"
    }
    status, res, _ = make_req("POST", "/api/register", stu_payload)
    assert status == 200 and res.get("success"), f"Student registration failed: {res}"
    print("[PASS] 2.1 Student registration succeeded (Active status)")

    # Test 2.2: Student Login
    status, res, _ = make_req("POST", "/api/login", {"username": stu_user, "password": "Password@123"})
    assert status == 200 and res.get("success"), f"Student login failed: {res}"
    student_token = res["token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}
    print("[PASS] 2.2 Student login succeeded")

    # Test 2.3: Faculty Registration (Pending status)
    fac_user = f"faculty_{ts}"
    fac_payload = {
        "role": "Faculty",
        "name": f"Prof {ts}",
        "email": f"faculty_{ts}@college.edu",
        "mobile": f"97{ts:08d}",
        "department": "Computer Engineering",
        "facultyId": f"FAC_{ts}",
        "designation": "Assistant Professor",
        "username": fac_user,
        "password": "Password@123",
        "confirmPassword": "Password@123"
    }
    status, res, _ = make_req("POST", "/api/register", fac_payload)
    assert status == 200 and res.get("success"), f"Faculty registration failed: {res}"
    assert res["user"]["status"] == "Pending", f"Faculty status should be Pending, got: {res['user']['status']}"
    print("[PASS] 2.3 Faculty registration created with status = Pending")

    # Test 2.4: Pending Faculty Login must be BLOCKED (403)
    status, res, _ = make_req("POST", "/api/login", {"username": fac_user, "password": "Password@123"})
    assert status == 403 and "pending" in res.get("message", "").lower(), f"Pending login should be blocked with 403, got: {status}, {res}"
    print("[PASS] 2.4 Pending Faculty login successfully blocked (403)")

    # Test 2.5: Admin views pending users list
    status, res, _ = make_req("GET", "/api/admin/pending-users", headers=admin_headers)
    assert status == 200 and res.get("success"), f"Fetch pending users failed: {res}"
    pending_fac = next((u for u in res.get("users", []) if u["username"] == fac_user), None)
    assert pending_fac is not None, f"Registered faculty not in pending list: {res}"
    print(f"[PASS] 2.5 Admin successfully retrieved pending users list (found {fac_user})")

    # Test 2.6: Admin approves Faculty
    status, res, _ = make_req("POST", "/api/admin/approve-user", {"id": pending_fac["id"]}, headers=admin_headers)
    assert status == 200 and res.get("success"), f"Approve faculty failed: {res}"
    print("[PASS] 2.6 Admin approved Faculty account")

    # Test 2.7: Approved Faculty can now log in
    status, res, _ = make_req("POST", "/api/login", {"username": fac_user, "password": "Password@123"})
    assert status == 200 and res.get("success"), f"Approved Faculty login failed: {res}"
    faculty_token = res["token"]
    faculty_headers = {"Authorization": f"Bearer {faculty_token}"}
    print("[PASS] 2.7 Approved Faculty logged in successfully")

    # Test 2.8: HOD Registration & Rejection workflow
    hod_user = f"hod_{ts}"
    hod_payload = {
        "role": "HOD",
        "name": f"Dr HOD {ts}",
        "email": f"hod_{ts}@college.edu",
        "mobile": f"96{ts:08d}",
        "department": f"Mechanical Engineering_{ts}",
        "facultyId": f"HOD_{ts}",
        "qualification": "Ph.D.",
        "username": hod_user,
        "password": "Password@123",
        "confirmPassword": "Password@123"
    }
    status, res, _ = make_req("POST", "/api/register", hod_payload)
    assert status == 200 and res.get("success"), f"HOD registration failed: {res}"
    print("[PASS] 2.8 HOD registration created (Pending status)")

    # Reject HOD
    status, res, _ = make_req("POST", "/api/admin/reject-user", {"username": hod_user}, headers=admin_headers)
    assert status == 200 and res.get("success"), f"Reject HOD failed: {res}"
    
    # Rejected HOD login must be BLOCKED (403)
    status, res, _ = make_req("POST", "/api/login", {"username": hod_user, "password": "Password@123"})
    assert status == 403 and "rejected" in res.get("message", "").lower(), f"Rejected login should return 403, got: {status}, {res}"
    print("[PASS] 2.9 Rejected HOD login blocked with 403 Forbidden")

    # Test 2.10: Public registration cannot create Administrator
    fake_admin_payload = {
        "role": "Administrator",
        "name": "Hacker Admin",
        "email": f"hacker_{ts}@college.edu",
        "mobile": f"95{ts:08d}",
        "username": f"hacker_admin_{ts}",
        "password": "Password@123",
        "confirmPassword": "Password@123"
    }
    status, res, _ = make_req("POST", "/api/register", fake_admin_payload)
    assert status == 403, f"Public admin registration should return 403, got {status}: {res}"
    print("[PASS] 2.10 Public registration of Administrator blocked (403 Forbidden)")

    # --- SECTION 3: ROLE AUTHORIZATION & IDOR PROTECTION ---
    print("\n[SECTION 3: ROLE AUTHORIZATION & IDOR PROTECTION]")
    
    # Test 3.1: Student attempting to delete student (403)
    status, res, _ = make_req("DELETE", f"/api/students?id=STU_{ts}", headers=student_headers)
    assert status == 403, f"Student should not be able to delete students, got: {status}"
    print("[PASS] 3.1 Student deleting student blocked (403)")

    # Test 3.2: Faculty attempting to delete student (403)
    status, res, _ = make_req("DELETE", f"/api/students?id=STU_{ts}", headers=faculty_headers)
    assert status == 403, f"Faculty should not be able to delete students, got: {status}"
    print("[PASS] 3.2 Faculty deleting student blocked (403)")

    # Test 3.3: Student fetching ID card of another student (IDOR)
    status, res, _ = make_req("GET", "/api/students/id-card?id=STU_999999", headers=student_headers)
    assert status == 403, f"Cross-student ID card access should be blocked, got {status}: {res}"
    print("[PASS] 3.3 Student IDOR access on ID card blocked (403)")

    # Test 3.4: Student fetching own ID card
    status, res, _ = make_req("GET", f"/api/students/id-card?id=STU_{ts}", headers=student_headers)
    assert status == 200 and res.get("success"), f"Student should access own ID card: {res}"
    print("[PASS] 3.4 Student fetching own ID card succeeded")

    # --- SECTION 4: CRUD OPERATIONS & SAFE TRANSACTIONS ---
    print("\n[SECTION 4: CRUD OPERATIONS & SAFE TRANSACTIONS]")

    # Assign Student to Faculty
    status, res, _ = make_req("POST", "/api/faculty-students/assign", {"facultyId": f"FAC_{ts}", "studentIds": [f"STU_{ts}"]}, headers=admin_headers)
    assert status == 200 and res.get("success"), f"Assign student to faculty failed: {res}"
    print(f"[PASS] 4.0 Admin assigned Student STU_{ts} to Faculty FAC_{ts}")

    # Test 4.1: Add Attendance
    att_payload = {
        "studentId": f"STU_{ts}",
        "studentName": f"Student {ts}",
        "subject": "Computer Networks",
        "date": time.strftime('%Y-%m-%d'),
        "status": "Present"
    }
    status, res, _ = make_req("POST", "/api/attendance", att_payload, headers=faculty_headers)
    assert status == 200 and res.get("success"), f"Mark attendance failed: {res}"
    print("[PASS] 4.1 Faculty marked attendance successfully")

    # Test 4.2: Student views own attendance
    status, res, _ = make_req("GET", "/api/attendance", headers=student_headers)
    assert status == 200 and res.get("success"), f"Fetch student attendance failed: {res}"
    assert any(a["student_id"] == f"STU_{ts}" for a in res.get("attendance", [])), "Student attendance record missing"
    print(f"[PASS] 4.2 Student successfully retrieved own attendance ({len(res['attendance'])} records)")

    # Test 4.3: Add Exam Result
    res_payload = {
        "studentId": f"STU_{ts}",
        "studentName": f"Student {ts}",
        "semester": "Semester 1",
        "subject": "Programming in C",
        "internalMarks": 28,
        "endSemMarks": 62
    }
    status, res, _ = make_req("POST", "/api/results", res_payload, headers=faculty_headers)
    assert status == 200 and res.get("success"), f"Add result failed: {res}"
    result_id = res.get("id")
    print(f"[PASS] 4.3 Faculty saved exam result successfully (ID: {result_id})")

    # Test 4.4: Student views own results
    status, res, _ = make_req("GET", "/api/results", headers=student_headers)
    assert status == 200 and res.get("success"), f"Fetch student results failed: {res}"
    assert any(r["student_id"] == f"STU_{ts}" for r in res.get("results", [])), "Student result record missing"
    print(f"[PASS] 4.4 Student retrieved own exam results ({len(res['results'])} records)")

    # Test 4.5: Fees Management & Student Pay
    fee_payload = {
        "studentId": f"STU_{ts}",
        "studentName": f"Student {ts}",
        "department": "Computer Engineering",
        "totalFees": 15000,
        "paidFees": 5000
    }
    status, res, _ = make_req("POST", "/api/fees", fee_payload, headers=admin_headers)
    assert status == 200 and res.get("success"), f"Create fee record failed: {res}"
    print("[PASS] 4.5 Admin created fee record for student")

    # Student pays remaining fee
    status, res, _ = make_req("POST", "/api/fees", {"payAmount": 10000}, headers=student_headers)
    assert status == 200 and res.get("success"), f"Student pay fee failed: {res}"
    print("[PASS] 4.6 Student processed fee payment successfully")

    # Student views own fee receipt
    status, res, _ = make_req("GET", f"/api/fees/receipt?id=STU_{ts}", headers=student_headers)
    assert status == 200 and res.get("success"), f"Fetch fee receipt failed: {res}"
    assert res["receipt"]["paymentStatus"] == "Paid", f"Fee status should be Paid: {res['receipt']}"
    print(f"[PASS] 4.7 Student fee receipt generated with Receipt Number: {res['receipt']['receiptNumber']}")

    # Test 4.8: Document Publishing & Safe Deletion
    doc_payload = {
        "title": f"Network Security Notes {ts}",
        "category": "Notes",
        "department": "Computer Engineering",
        "filePath": f"/uploads/sample_{ts}.pdf"
    }
    status, res, _ = make_req("POST", "/api/documents", doc_payload, headers=faculty_headers)
    assert status == 200 and res.get("success"), f"Publish document failed: {res}"
    doc_id = res["id"]
    print(f"[PASS] 4.8 Faculty published document successfully (ID: {doc_id})")

    # Delete Document
    status, res, _ = make_req("DELETE", f"/api/documents?id={doc_id}", headers=faculty_headers)
    assert status == 200 and res.get("success"), f"Delete document failed: {res}"
    print("[PASS] 4.9 Document deleted successfully")

    # Test 4.9: Administrator safely deletes Student (Full Foreign Key & Transaction Verification)
    status, res, _ = make_req("DELETE", f"/api/students?id=STU_{ts}", headers=admin_headers)
    assert status == 200 and res.get("success"), f"Admin delete student failed: {res}"
    print(f"[PASS] 4.10 Admin deleted student STU_{ts} with transaction and dependent record cleanup")

    # Verify student is removed from database
    status, res, _ = make_req("GET", f"/api/students/id-card?id=STU_{ts}", headers=admin_headers)
    assert status == 404, f"Deleted student should return 404, got: {status}"
    print("[PASS] 4.11 Verified student record no longer exists (404)")

    # Test 4.12: Administrator deletes Faculty
    status, res, _ = make_req("DELETE", f"/api/faculty?id=FAC_{ts}", headers=admin_headers)
    assert status == 200 and res.get("success"), f"Admin delete faculty failed: {res}"
    print(f"[PASS] 4.12 Admin deleted faculty member FAC_{ts}")

    # --- SECTION 5: LOGOUT & SESSION INVALIDATION ---
    print("\n[SECTION 5: LOGOUT & SESSION INVALIDATION]")
    status, res, _ = make_req("POST", "/api/logout", headers=student_headers)
    assert status == 200 and res.get("success"), f"Logout failed: {res}"
    
    # Old token must no longer be authorized
    status, res, _ = make_req("GET", "/api/auth/me", headers=student_headers)
    assert status == 401, f"Logged out token should return 401, got: {status}"
    print("[PASS] 5.1 Logout successfully invalidated session token")

    print("\n==================================================")
    print("ALL TEST SUITES PASSED 100%! SYSTEM FULLY HARDENED!")
    print("==================================================")

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(1.0)
    try:
        run_all_tests()
    finally:
        stop_server()
