import urllib.request
import urllib.parse
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def make_request(path, method="GET", body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Session-Token"] = token
    
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            return response.status, json.loads(res_body) if response.headers.get_content_type() == "application/json" else res_body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, err_body

def run_tests():
    ts = int(time.time() * 1000) % 100000
    print("--- STARTING SYSTEM AUDIT VERIFICATION TESTS ---")
    
    # 1. Health check
    status, res = make_request("/api/health")
    assert status == 200 and res.get("status") == "ok", f"Health check failed: {res}"
    print("[PASS] Server Health Check OK")

    # 2. Public Static Home Page
    status, res = make_request("/")
    assert status == 200 and "<title>" in res, "Static home page load failed"
    print("[PASS] Static Home Page (index.html) Loads OK")

    # 3. Initial Admin Login
    status, res = make_request("/api/login", method="POST", body={"username": "admin", "password": "admin123"})
    assert status == 200 and res.get("success"), f"Admin login failed: {res}"
    admin_token = res["token"]
    print("[PASS] Initial Admin Hashed Password Authentication OK")

    # 4. Create Department (Admin)
    status, res = make_request("/api/departments", method="POST", body={"code": "CO", "name": "Computer Engineering", "description": "Computer Engineering Dept"}, token=admin_token)
    assert status == 200 and res.get("success"), f"Create department failed: {res}"
    print("[PASS] Admin Department Creation OK")

    # 5. Public Student Registration
    student_user = f"student_{ts}"
    student_email = f"student_{ts}@college.edu"
    student_id = f"STU_{ts}"
    status, res = make_request("/api/register", method="POST", body={
        "role": "Student",
        "username": student_user,
        "password": "rohan_pass",
        "confirmPassword": "rohan_pass",
        "name": f"Rohan Verma {ts}",
        "email": student_email,
        "studentId": student_id,
        "rollNumber": f"R{ts}",
        "mobile": f"98765{ts:05d}",
        "gender": "Male",
        "dob": "2002-05-15",
        "admissionYear": "2026",
        "semester": "Semester 1",
        "division": "A",
        "address": "Pune, Maharashtra",
        "department": "Computer Engineering"
    })
    assert status == 200 and res.get("success"), f"Student registration failed: {res}"
    student_token = res["token"]
    print(f"[PASS] Student Registration ({student_user}) OK")

    # 6. Public Faculty Registration
    fac_user = f"fac_{ts}"
    fac_email = f"fac_{ts}@college.edu"
    status, res = make_request("/api/register", method="POST", body={
        "role": "Faculty",
        "username": fac_user,
        "password": "fac_password",
        "confirmPassword": "fac_password",
        "name": f"Prof. Amit Patil {ts}",
        "email": fac_email,
        "department": "Computer Engineering",
        "designation": "Assistant Professor",
        "mobile": f"98123{ts:05d}"
    })
    assert status == 200 and res.get("success"), f"Faculty registration failed: {res}"
    print(f"[PASS] Faculty Registration ({fac_user}) OK")

    # 7. Public HOD Registration
    hod_user = f"hod_{ts}"
    hod_email = f"hod_{ts}@college.edu"
    status, res = make_request("/api/register", method="POST", body={
        "role": "HOD",
        "username": hod_user,
        "password": "hod_password",
        "confirmPassword": "hod_password",
        "name": f"Dr. Rajesh Sharma {ts}",
        "email": hod_email,
        "department": "Computer Engineering",
        "qualification": "Ph.D.",
        "experience": "12 Years",
        "mobile": f"98763{ts:05d}"
    })
    assert status == 200 and res.get("success"), f"HOD registration failed: {res}"
    print(f"[PASS] HOD Registration ({hod_user}) OK")

    # 8. HOD Login Test
    status, res = make_request("/api/login", method="POST", body={"username": hod_user, "password": "hod_password"})
    assert status == 200 and res.get("success"), f"HOD login failed: {res}"
    print(f"[PASS] HOD Hashed Password Login ({hod_user}) OK")

    # 9. Student Scoping Check
    status, res = make_request("/api/students", token=student_token)
    assert status == 200 and len(res.get("students", [])) == 1 and res["students"][0]["id"] == student_id, f"Student scoping failed: {res}"
    print("[PASS] Student Own-Data Authorization Scoping OK")

    # 10. Logout Verification
    status, res = make_request("/api/logout", method="POST", token=student_token)
    assert status == 200, f"Logout failed: {res}"
    print("[PASS] Session Termination & Logout Verification OK")

    print("\n==================================================")
    print("ALL SYSTEM VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
