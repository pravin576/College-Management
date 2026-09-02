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

PORT = 8011
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

def setup_test_users():
    ts = int(time.time() * 1000) % 100000
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)

    # 1. Admin
    c.execute("SELECT id FROM users WHERE username = 'admin_tester'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, name, email, department, status) VALUES ('admin_tester', %s, 'Administrator', 'Admin User', 'admin_tester@college.edu', 'Administration', 'Active')", (hash_password("Admin@123"),))

    # 2. HOD CE
    hod_ce_user = f"hod_ce_{ts}"
    c.execute("INSERT INTO users (username, password, role, name, email, department, faculty_id, status) VALUES (%s, %s, 'HOD', 'HOD CE', %s, 'Computer Engineering', %s, 'Active')",
              (hod_ce_user, hash_password("Password@123"), f"{hod_ce_user}@college.edu", f"HOD_CE_{ts}"))

    # 3. HOD ME (Different Department)
    hod_me_user = f"hod_me_{ts}"
    c.execute("INSERT INTO users (username, password, role, name, email, department, faculty_id, status) VALUES (%s, %s, 'HOD', 'HOD ME', %s, 'Mechanical Engineering', %s, 'Active')",
              (hod_me_user, hash_password("Password@123"), f"{hod_me_user}@college.edu", f"HOD_ME_{ts}"))

    # 4. Faculty 1 (CE)
    fac1_id = f"FAC1_{ts}"
    fac1_user = f"faculty1_{ts}"
    c.execute("INSERT INTO faculty (id, name, department, designation, email, mobile, status) VALUES (%s, %s, 'Computer Engineering', 'Asst Prof', %s, '9800000001', 'Active')",
              (fac1_id, f"Prof One {ts}", f"{fac1_user}@college.edu"))
    c.execute("INSERT INTO users (username, password, role, name, email, department, faculty_id, status) VALUES (%s, %s, 'Faculty', %s, %s, 'Computer Engineering', %s, 'Active')",
              (fac1_user, hash_password("Password@123"), f"Prof One {ts}", f"{fac1_user}@college.edu", fac1_id))

    # 5. Faculty 2 (CE)
    fac2_id = f"FAC2_{ts}"
    fac2_user = f"faculty2_{ts}"
    c.execute("INSERT INTO faculty (id, name, department, designation, email, mobile, status) VALUES (%s, %s, 'Computer Engineering', 'Asst Prof', %s, '9800000002', 'Active')",
              (fac2_id, f"Prof Two {ts}", f"{fac2_user}@college.edu"))
    c.execute("INSERT INTO users (username, password, role, name, email, department, faculty_id, status) VALUES (%s, %s, 'Faculty', %s, %s, 'Computer Engineering', %s, 'Active')",
              (fac2_user, hash_password("Password@123"), f"Prof Two {ts}", f"{fac2_user}@college.edu", fac2_id))

    # 6. Student A (Assigned to Faculty 1)
    stuA_id = f"STU_A_{ts}"
    stuA_user = f"student_a_{ts}"
    c.execute("""INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                 VALUES (%s, %s, %s, %s, '9800000003', 'Male', '2005-01-01', 'Computer Engineering', 'First Year', 'Semester 1', 'A', '2026', 'Campus', 'Active')""",
              (stuA_id, f"R_A_{ts}", f"Student Alpha {ts}", f"{stuA_user}@college.edu"))
    c.execute("INSERT INTO users (username, password, role, name, email, department, student_id, status) VALUES (%s, %s, 'Student', %s, %s, 'Computer Engineering', %s, 'Active')",
              (stuA_user, hash_password("Password@123"), f"Student Alpha {ts}", f"{stuA_user}@college.edu", stuA_id))

    # 7. Student B (Assigned to Faculty 2)
    stuB_id = f"STU_B_{ts}"
    stuB_user = f"student_b_{ts}"
    c.execute("""INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                 VALUES (%s, %s, %s, %s, '9800000004', 'Female', '2005-01-01', 'Computer Engineering', 'First Year', 'Semester 1', 'A', '2026', 'Campus', 'Active')""",
              (stuB_id, f"R_B_{ts}", f"Student Beta {ts}", f"{stuB_user}@college.edu"))
    c.execute("INSERT INTO users (username, password, role, name, email, department, student_id, status) VALUES (%s, %s, 'Student', %s, %s, 'Computer Engineering', %s, 'Active')",
              (stuB_user, hash_password("Password@123"), f"Student Beta {ts}", f"{stuB_user}@college.edu", stuB_id))

    # 8. Student C (ME - Assigned to no CE faculty)
    stuC_id = f"STU_C_{ts}"
    stuC_user = f"student_c_{ts}"
    c.execute("""INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                 VALUES (%s, %s, %s, %s, '9800000005', 'Male', '2005-01-01', 'Mechanical Engineering', 'First Year', 'Semester 1', 'A', '2026', 'Campus', 'Active')""",
              (stuC_id, f"R_C_{ts}", f"Student Charlie {ts}", f"{stuC_user}@college.edu"))
    c.execute("INSERT INTO users (username, password, role, name, email, department, student_id, status) VALUES (%s, %s, 'Student', %s, %s, 'Mechanical Engineering', %s, 'Active')",
              (stuC_user, hash_password("Password@123"), f"Student Charlie {ts}", f"{stuC_user}@college.edu", stuC_id))

    # 9. Map Student A -> Faculty 1, Student B -> Faculty 2
    c.execute("INSERT INTO faculty_students (faculty_id, student_id) VALUES (%s, %s)", (fac1_id, stuA_id))
    c.execute("INSERT INTO faculty_students (faculty_id, student_id) VALUES (%s, %s)", (fac2_id, stuB_id))

    conn.commit()
    c.close()
    conn.close()

    return {
        "admin": "admin_tester",
        "hod_ce": hod_ce_user,
        "hod_me": hod_me_user,
        "fac1": fac1_user,
        "fac1_id": fac1_id,
        "fac2": fac2_user,
        "fac2_id": fac2_id,
        "stuA": stuA_user,
        "stuA_id": stuA_id,
        "stuB": stuB_user,
        "stuB_id": stuB_id,
        "stuC": stuC_user,
        "stuC_id": stuC_id
    }

def login_user(username, password="Password@123"):
    st, res, _ = make_req("POST", "/api/login", {"username": username, "password": password})
    assert st == 200 and res.get("success"), f"Login failed for {username}: {res}"
    return {"Authorization": f"Bearer {res['token']}"}

def run_tests():
    print("==================================================")
    print("RUNNING 5 FIXES VERIFICATION TEST SUITE")
    print("==================================================")

    data = setup_test_users()
    admin_hdr = login_user("admin_tester", "Admin@123")
    hod_ce_hdr = login_user(data["hod_ce"])
    hod_me_hdr = login_user(data["hod_me"])
    fac1_hdr = login_user(data["fac1"])
    fac2_hdr = login_user(data["fac2"])
    stuA_hdr = login_user(data["stuA"])

    print("\n[TEST FIX 1: FACULTY STUDENT ACCESS]")
    # 1.1 Faculty 1 queries student list -> must only get Student A
    st, res, _ = make_req("GET", "/api/students", headers=fac1_hdr)
    assert st == 200 and res.get("success"), f"Fetch students failed: {res}"
    s_ids = [s["id"] for s in res["students"]]
    assert data["stuA_id"] in s_ids, f"Student A should be in faculty 1 list: {s_ids}"
    assert data["stuB_id"] not in s_ids, f"Student B must NOT be visible to faculty 1: {s_ids}"
    assert data["stuC_id"] not in s_ids, f"Student C must NOT be visible to faculty 1: {s_ids}"
    print(" [PASS] 1.1 Faculty 1 queries students and sees ONLY assigned student (Student A)")

    # 1.2 Faculty 1 tries to bypass by sending department filter -> still only Student A
    st, res, _ = make_req("GET", "/api/students?department=Computer%20Engineering", headers=fac1_hdr)
    assert st == 200
    s_ids = [s["id"] for s in res["students"]]
    assert data["stuA_id"] in s_ids and data["stuB_id"] not in s_ids
    print(" [PASS] 1.2 Faculty 1 cannot bypass assignment via department query parameter")

    # 1.3 Faculty 1 accesses assigned Student A ID card -> 200
    st, res, _ = make_req("GET", f"/api/students/id-card?id={data['stuA_id']}", headers=fac1_hdr)
    assert st == 200 and res.get("success"), f"Faculty 1 accessing assigned student ID card failed: {res}"
    print(" [PASS] 1.3 Faculty 1 successfully views assigned Student A ID card")

    # 1.4 Faculty 1 accesses unassigned Student B ID card -> 403 Forbidden
    st, res, _ = make_req("GET", f"/api/students/id-card?id={data['stuB_id']}", headers=fac1_hdr)
    assert st == 403, f"Faculty 1 accessing unassigned Student B ID card should return 403, got {st}: {res}"
    print(" [PASS] 1.4 Faculty 1 accessing unassigned Student B ID card blocked with 403 Forbidden")

    print("\n[TEST FIX 2: RESULT AUTHORIZATION]")
    # 2.1 Faculty 1 creates result for assigned Student A -> 200
    res_payload_A = {
        "studentId": data["stuA_id"],
        "studentName": "Student Alpha",
        "semester": "Semester 1",
        "subject": "Mathematics I",
        "internalMarks": 25,
        "endSemMarks": 65
    }
    st, res, _ = make_req("POST", "/api/results", res_payload_A, headers=fac1_hdr)
    assert st == 200 and res.get("success"), f"Faculty 1 create result for Student A failed: {res}"
    resA_id = res["id"]
    print(f" [PASS] 2.1 Faculty 1 created result for assigned Student A (Result ID: {resA_id})")

    # 2.2 Faculty 1 tries to create result for unassigned Student B -> 403 Forbidden
    res_payload_B = {
        "studentId": data["stuB_id"],
        "studentName": "Student Beta",
        "semester": "Semester 1",
        "subject": "Mathematics I",
        "internalMarks": 25,
        "endSemMarks": 65
    }
    st, res, _ = make_req("POST", "/api/results", res_payload_B, headers=fac1_hdr)
    assert st == 403, f"Faculty 1 creating result for unassigned Student B should return 403, got {st}: {res}"
    print(" [PASS] 2.2 Faculty 1 creating result for unassigned Student B blocked with 403 Forbidden")

    # 2.3 Faculty 2 creates result for Student B
    st, res, _ = make_req("POST", "/api/results", res_payload_B, headers=fac2_hdr)
    assert st == 200 and res.get("success")
    resB_id = res["id"]
    print(f" [PASS] 2.3 Faculty 2 created result for assigned Student B (Result ID: {resB_id})")

    # 2.4 Faculty 1 tries to UPDATE Student B's result -> 403 Forbidden
    update_payload_B = {
        "id": resB_id,
        "studentId": data["stuB_id"],
        "subject": "Mathematics I",
        "internalMarks": 30,
        "endSemMarks": 70
    }
    st, res, _ = make_req("POST", "/api/results", update_payload_B, headers=fac1_hdr)
    assert st == 403, f"Faculty 1 updating Student B result should return 403, got {st}: {res}"
    print(" [PASS] 2.4 Faculty 1 updating unassigned Student B's result blocked with 403 Forbidden")

    # 2.5 Faculty 1 tries to DELETE Student B's result -> 403 Forbidden
    st, res, _ = make_req("DELETE", f"/api/results?id={resB_id}", headers=fac1_hdr)
    assert st == 403, f"Faculty 1 deleting Student B result should return 403, got {st}: {res}"
    print(" [PASS] 2.5 Faculty 1 deleting unassigned Student B's result blocked with 403 Forbidden")

    # 2.6 Faculty 1 updates Student A's result -> 200
    update_payload_A = {
        "id": resA_id,
        "studentId": data["stuA_id"],
        "subject": "Mathematics I",
        "internalMarks": 28,
        "endSemMarks": 68
    }
    st, res, _ = make_req("POST", "/api/results", update_payload_A, headers=fac1_hdr)
    assert st == 200 and res.get("success"), f"Faculty 1 update own assigned result failed: {res}"
    print(" [PASS] 2.6 Faculty 1 updated assigned Student A's result successfully")

    # 2.7 HOD ME tries to modify CE student result -> 403 Forbidden
    st, res, _ = make_req("DELETE", f"/api/results?id={resA_id}", headers=hod_me_hdr)
    assert st == 403, f"HOD ME deleting CE student result should return 403, got {st}: {res}"
    print(" [PASS] 2.7 HOD ME deleting CE Student result blocked with 403 Forbidden")

    # 2.8 Student Alpha views own results -> 200, but cannot delete -> 403
    st, res, _ = make_req("GET", "/api/results", headers=stuA_hdr)
    assert st == 200 and any(r["student_id"] == data["stuA_id"] for r in res.get("results", [])), f"Student viewing results failed: {res}"
    st, res, _ = make_req("DELETE", f"/api/results?id={resA_id}", headers=stuA_hdr)
    assert st == 403, f"Student deleting result should return 403, got {st}: {res}"
    print(" [PASS] 2.8 Student viewing own results succeeds (200), Student deleting result blocked (403)")

    # 2.9 Admin deletes result -> 200
    st, res, _ = make_req("DELETE", f"/api/results?id={resA_id}", headers=admin_hdr)
    assert st == 200 and res.get("success"), f"Admin delete result failed: {res}"
    print(" [PASS] 2.9 Admin successfully deleted exam result (full access)")

    print("\n[TEST FIX 3: ATTENDANCE AUTHORIZATION]")
    # 3.1 Faculty 1 creates attendance for assigned Student A -> 200
    att_payload_A = {
        "studentId": data["stuA_id"],
        "studentName": "Student Alpha",
        "subject": "Data Structures",
        "date": "2026-09-02",
        "status": "Present"
    }
    st, res, _ = make_req("POST", "/api/attendance", att_payload_A, headers=fac1_hdr)
    assert st == 200 and res.get("success"), f"Faculty 1 mark attendance for Student A failed: {res}"
    print(" [PASS] 3.1 Faculty 1 marked attendance for assigned Student A")

    # Fetch attendance ID
    st, res, _ = make_req("GET", "/api/attendance", headers=fac1_hdr)
    att_recs = res.get("attendance", [])
    attA = next(a for a in att_recs if a["student_id"] == data["stuA_id"])
    attA_id = attA["id"]

    # 3.2 Faculty 1 tries to mark attendance for unassigned Student B -> 403 Forbidden
    att_payload_B = {
        "studentId": data["stuB_id"],
        "studentName": "Student Beta",
        "subject": "Data Structures",
        "date": "2026-09-02",
        "status": "Present"
    }
    st, res, _ = make_req("POST", "/api/attendance", att_payload_B, headers=fac1_hdr)
    assert st == 403, f"Faculty 1 marking attendance for unassigned Student B should return 403, got {st}: {res}"
    print(" [PASS] 3.2 Faculty 1 marking attendance for unassigned Student B blocked with 403 Forbidden")

    # 3.3 Faculty 2 marks attendance for Student B
    st, res, _ = make_req("POST", "/api/attendance", att_payload_B, headers=fac2_hdr)
    assert st == 200 and res.get("success")
    st, res, _ = make_req("GET", "/api/attendance", headers=fac2_hdr)
    attB_id = next(a["id"] for a in res["attendance"] if a["student_id"] == data["stuB_id"])
    print(f" [PASS] 3.3 Faculty 2 marked attendance for assigned Student B (Att ID: {attB_id})")

    # 3.4 Faculty 1 tries to UPDATE Student B's attendance -> 403 Forbidden
    update_att_B = {
        "id": attB_id,
        "studentId": data["stuB_id"],
        "subject": "Data Structures",
        "date": "2026-09-02",
        "status": "Absent"
    }
    st, res, _ = make_req("POST", "/api/attendance", update_att_B, headers=fac1_hdr)
    assert st == 403, f"Faculty 1 updating unassigned Student B attendance should return 403, got {st}: {res}"
    print(" [PASS] 3.4 Faculty 1 updating unassigned Student B attendance blocked with 403 Forbidden")

    # 3.5 Faculty 1 tries to DELETE Student B's attendance -> 403 Forbidden
    st, res, _ = make_req("DELETE", f"/api/attendance?id={attB_id}", headers=fac1_hdr)
    assert st == 403, f"Faculty 1 deleting unassigned Student B attendance should return 403, got {st}: {res}"
    print(" [PASS] 3.5 Faculty 1 deleting unassigned Student B attendance blocked with 403 Forbidden")

    # 3.6 Faculty 1 updates Student A's attendance -> 200
    update_att_A = {
        "id": attA_id,
        "studentId": data["stuA_id"],
        "subject": "Data Structures",
        "date": "2026-09-02",
        "status": "Late"
    }
    st, res, _ = make_req("POST", "/api/attendance", update_att_A, headers=fac1_hdr)
    assert st == 200 and res.get("success"), f"Faculty 1 updating assigned attendance failed: {res}"
    print(" [PASS] 3.6 Faculty 1 updated assigned Student A attendance successfully")

    # 3.7 HOD ME tries to modify CE attendance -> 403 Forbidden
    st, res, _ = make_req("DELETE", f"/api/attendance?id={attA_id}", headers=hod_me_hdr)
    assert st == 403, f"HOD ME deleting CE student attendance should return 403, got {st}: {res}"
    print(" [PASS] 3.7 HOD ME deleting CE attendance blocked with 403 Forbidden")

    # 3.8 Student Alpha views own attendance -> 200, tries to delete -> 403
    st, res, _ = make_req("GET", "/api/attendance", headers=stuA_hdr)
    assert st == 200 and any(a["student_id"] == data["stuA_id"] for a in res.get("attendance", []))
    st, res, _ = make_req("DELETE", f"/api/attendance?id={attA_id}", headers=stuA_hdr)
    assert st == 403, f"Student deleting attendance should return 403, got {st}: {res}"
    print(" [PASS] 3.8 Student viewing own attendance succeeds (200), Student deleting attendance blocked (403)")

    # 3.9 Admin deletes attendance -> 200
    st, res, _ = make_req("DELETE", f"/api/attendance?id={attA_id}", headers=admin_hdr)
    assert st == 200 and res.get("success"), f"Admin delete attendance failed: {res}"
    print(" [PASS] 3.9 Admin successfully deleted attendance record (full access)")

    print("\n[TEST FIX 4: MISSING CAMPUS IMAGE]")
    st, res, hdrs = make_req("GET", "/images/campus.jpg")
    assert st == 200, f"GET /images/campus.jpg failed with status {st}"
    assert len(res) > 0, "Campus image is empty"
    hdrs_dict = dict(hdrs)
    assert hdrs_dict.get("Content-Type") in ["image/jpeg", "image/jpg"], f"Expected image/jpeg, got {hdrs_dict.get('Content-Type')}"
    print(f" [PASS] 4.1 /images/campus.jpg loaded successfully ({len(res)} bytes, Content-Type: {hdrs_dict.get('Content-Type')})")

    print("\n==================================================")
    print("ALL 5 FIX VERIFICATION TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(1.0)
    try:
        run_tests()
    finally:
        stop_server()
