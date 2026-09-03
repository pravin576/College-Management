import http.client
import json
import os
import sys
import time
import threading
import socketserver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from server import ERPRequestHandler, init_db
from config.database import get_db_connection
from auth.utils import hash_password

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
    return res.status, parsed

def run_tests():
    ts = int(time.time() * 1000) % 100000
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)

    # 1. Setup Student
    stu_id = f"STU_FP_{ts}"
    stu_user = f"stu_fp_{ts}"
    stu_email = f"student_{ts}@college.edu"
    stu_mobile = f"99{ts:08d}"
    stu_dob = "2004-05-15"
    stu_roll = f"RN_{ts}"

    c.execute("""INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                 VALUES (%s, %s, %s, %s, %s, 'Female', %s, 'Computer Engineering', 'First Year', 'Semester 1', 'A', '2026', 'Hostel', 'Active')""",
              (stu_id, stu_roll, f"Student FP {ts}", stu_email, stu_mobile, stu_dob))
    c.execute("""INSERT INTO users (username, password, role, name, email, department, student_id, mobile, status)
                 VALUES (%s, %s, 'Student', %s, %s, 'Computer Engineering', %s, %s, 'Active')""",
              (stu_user, hash_password("OldPassword@1"), f"Student FP {ts}", stu_email, stu_id, stu_mobile))

    # 2. Setup Faculty
    fac_id = f"FAC_FP_{ts}"
    fac_user = f"fac_fp_{ts}"
    fac_email = f"faculty_{ts}@college.edu"
    fac_mobile = f"98{ts:08d}"

    c.execute("""INSERT INTO faculty (id, name, department, designation, email, mobile, status)
                 VALUES (%s, %s, 'Computer Engineering', 'Asst Prof', %s, %s, 'Active')""",
              (fac_id, f"Prof FP {ts}", fac_email, fac_mobile))
    c.execute("""INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, status)
                 VALUES (%s, %s, 'Faculty', %s, %s, 'Computer Engineering', %s, %s, 'Active')""",
              (fac_user, hash_password("OldPassword@2"), f"Prof FP {ts}", fac_email, fac_id, fac_mobile))

    # 3. Setup HOD
    hod_user = f"hod_fp_{ts}"
    hod_email = f"hod_{ts}@college.edu"
    hod_contact = f"97{ts:08d}"
    hod_fac_id = f"HOD_FP_{ts}"

    c.execute("""INSERT INTO users (username, password, role, name, email, department, faculty_id, mobile, status)
                 VALUES (%s, %s, 'HOD', %s, %s, 'Information Technology', %s, %s, 'Active')""",
              (hod_user, hash_password("OldPassword@3"), f"HOD FP {ts}", hod_email, hod_fac_id, hod_contact))

    conn.commit()
    c.close()
    conn.close()

    print("==================================================")
    print("RUNNING FORGOT PASSWORD COMPREHENSIVE TEST SUITE")
    print("==================================================")

    # TEST 1: Verification lookups
    # 1.1 Find Student by username
    st, res = make_req("POST", "/api/forgot-password", {"action": "verify", "role": "Student", "identifier": stu_user})
    assert st == 200 and res["success"] and res["user"]["username"] == stu_user, f"Failed 1.1: {res}"
    print(" [PASS] 1.1 Find Student by username successfully")

    # 1.2 Find Student by email
    st, res = make_req("POST", "/api/forgot-password", {"action": "verify", "role": "Student", "identifier": stu_email})
    assert st == 200 and res["success"] and res["user"]["username"] == stu_user, f"Failed 1.2: {res}"
    print(" [PASS] 1.2 Find Student by email successfully")

    # 1.3 Find Student by Roll Number (fallback lookup)
    st, res = make_req("POST", "/api/forgot-password", {"action": "verify", "role": "Student", "identifier": stu_roll})
    assert st == 200 and res["success"] and res["user"]["username"] == stu_user, f"Failed 1.3: {res}"
    print(" [PASS] 1.3 Find Student by Roll Number fallback successfully")

    # 1.4 Find Student by Student ID
    st, res = make_req("POST", "/api/forgot-password", {"action": "verify", "role": "Student", "identifier": stu_id})
    assert st == 200 and res["success"] and res["user"]["username"] == stu_user, f"Failed 1.4: {res}"
    print(" [PASS] 1.4 Find Student by Student ID successfully")

    # 1.5 Non-existent account returns 404
    st, res = make_req("POST", "/api/forgot-password", {"action": "verify", "role": "Student", "identifier": "nonexistent_user_123"})
    assert st == 404 and not res["success"], f"Failed 1.5: {res}"
    print(" [PASS] 1.5 Non-existent identifier correctly returns 404")

    # TEST 2: Reset Password for Student
    # 2.1 Reset via Email (frontend sends verificationInput)
    st, res = make_req("POST", "/api/forgot-password", {
        "action": "reset",
        "username": stu_user,
        "verificationInput": stu_email,
        "newPassword": "NewStudentPass@1",
        "confirmPassword": "NewStudentPass@1"
    })
    assert st == 200 and res["success"], f"Failed 2.1: {res}"
    print(" [PASS] 2.1 Student reset password using registered Email successfully")

    # Verify login works with new password
    st, res = make_req("POST", "/api/login", {"username": stu_user, "password": "NewStudentPass@1", "role": "Student"})
    assert st == 200 and res["success"], f"Failed login 2.1: {res}"
    print(" [PASS] 2.1b Student login succeeds with newly reset password")

    # 2.2 Reset via Mobile number
    st, res = make_req("POST", "/api/forgot-password", {
        "action": "reset",
        "username": stu_user,
        "verificationInput": stu_mobile,
        "newPassword": "NewStudentPass@2",
        "confirmPassword": "NewStudentPass@2"
    })
    assert st == 200 and res["success"], f"Failed 2.2: {res}"
    print(" [PASS] 2.2 Student reset password using registered Mobile successfully")

    # 2.3 Reset via DOB (both YYYY-MM-DD and DD-MM-YYYY)
    st, res = make_req("POST", "/api/forgot-password", {
        "action": "reset",
        "username": stu_user,
        "verificationInput": "15-05-2004", # DD-MM-YYYY format
        "newPassword": "NewStudentPass@3",
        "confirmPassword": "NewStudentPass@3"
    })
    assert st == 200 and res["success"], f"Failed 2.3: {res}"
    print(" [PASS] 2.3 Student reset password using DOB (DD-MM-YYYY format) successfully")

    # TEST 3: Reset Password for Faculty & HOD
    # 3.1 Faculty reset via Email
    st, res = make_req("POST", "/api/forgot-password", {
        "action": "reset",
        "username": fac_user,
        "verificationInput": fac_email,
        "newPassword": "NewFacultyPass@1",
        "confirmPassword": "NewFacultyPass@1"
    })
    assert st == 200 and res["success"], f"Failed 3.1: {res}"
    print(" [PASS] 3.1 Faculty reset password using registered Email successfully")

    # 3.2 HOD reset via Mobile/Contact
    st, res = make_req("POST", "/api/forgot-password", {
        "action": "reset",
        "username": hod_user,
        "verificationInput": hod_contact,
        "newPassword": "NewHODPass@1",
        "confirmPassword": "NewHODPass@1"
    })
    assert st == 200 and res["success"], f"Failed 3.2: {res}"
    print(" [PASS] 3.2 HOD reset password using registered Contact successfully")

    # TEST 4: Error Handling & Validation
    # 4.1 Invalid verification details returns 403
    st, res = make_req("POST", "/api/forgot-password", {
        "action": "reset",
        "username": stu_user,
        "verificationInput": "wrong_verification_info@college.edu",
        "newPassword": "SomePassword@123",
        "confirmPassword": "SomePassword@123"
    })
    assert st == 403 and not res["success"], f"Failed 4.1: {res}"
    print(" [PASS] 4.1 Wrong verification information rejected with 403")

    # 4.2 Password mismatch returns 400
    st, res = make_req("POST", "/api/forgot-password", {
        "action": "reset",
        "username": stu_user,
        "verificationInput": stu_email,
        "newPassword": "PasswordA@123",
        "confirmPassword": "PasswordB@123"
    })
    assert st == 400 and not res["success"], f"Failed 4.2: {res}"
    print(" [PASS] 4.2 Password mismatch rejected with 400")

    # 4.3 Short password (< 6 chars) returns 400
    st, res = make_req("POST", "/api/forgot-password", {
        "action": "reset",
        "username": stu_user,
        "verificationInput": stu_email,
        "newPassword": "123",
        "confirmPassword": "123"
    })
    assert st == 400 and not res["success"], f"Failed 4.3: {res}"
    print(" [PASS] 4.3 Short password (< 6 chars) rejected with 400")

    print("==================================================")
    print("ALL FORGOT PASSWORD TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(1)
    try:
        run_tests()
    finally:
        stop_server()
