import urllib.request
import urllib.parse
import json
import time

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

def test_full_registration_module():
    ts = int(time.time() * 1000) % 100000
    print("==================================================")
    print("TESTING COLLEGE ERP REGISTRATION MODULE REQUIREMENTS")
    print("==================================================")

    # ----------------------------------------------------
    # TEST 1: STUDENT REGISTRATION (All 10 required fields)
    # ----------------------------------------------------
    print("\n1. Testing Student Registration (10 fields)...")
    stu_name = f"Rahul Sharma {ts}"
    stu_year = "Second Year"
    stu_email = f"rahul_{ts}@college.edu"
    stu_phone = f"98765{ts:05d}"
    stu_id = f"STU_{ts}"
    stu_roll = f"R_{ts}"
    stu_dept = "Computer Science"
    stu_user = f"rahul_{ts}"
    stu_pass = "password123"

    payload_student = {
        "role": "Student",
        "name": stu_name,
        "year": stu_year,
        "email": stu_email,
        "phone": stu_phone,
        "studentId": stu_id,
        "rollNumber": stu_roll,
        "department": stu_dept,
        "username": stu_user,
        "password": stu_pass,
        "confirmPassword": stu_pass
    }

    status, res = make_request("/api/register", method="POST", body=payload_student)
    assert status == 200 and res.get("success"), f"Student registration failed: {res}"
    print(f"  [PASS] Student Account '{stu_user}' created successfully!")
    student_token = res["token"]

    # ----------------------------------------------------
    # TEST 2: STUDENT LOGIN & DASHBOARD SCOPING
    # ----------------------------------------------------
    print("\n2. Testing Student Login & Dashboard Scoping...")
    status, res = make_request("/api/login", method="POST", body={"username": stu_user, "password": stu_pass})
    assert status == 200 and res.get("success"), f"Student login failed: {res}"
    print(f"  [PASS] Student '{stu_user}' logged in successfully!")

    # Fetch student data as student
    status, res = make_request("/api/students", token=student_token)
    assert status == 200 and res.get("success")
    students = res.get("students", [])
    assert len(students) == 1, f"Expected 1 scoped record for student, got {len(students)}"
    assert students[0]["id"] == stu_id
    assert students[0]["year"] == "Second Year"
    assert students[0]["roll_number"] == stu_roll
    print(f"  [PASS] Student dashboard strictly scope-enforced: Name='{students[0]['name']}', Year='{students[0]['year']}'!")

    # ----------------------------------------------------
    # TEST 3: FACULTY REGISTRATION (All 5 required fields)
    # ----------------------------------------------------
    print("\n3. Testing Faculty Registration (5 fields)...")
    fac_name = f"Prof. Amit Patil {ts}"
    fac_dept = "Computer Science"
    fac_user = f"prof_amit_{ts}"
    fac_pass = "facpass123"

    payload_faculty = {
        "role": "Faculty",
        "name": fac_name,
        "department": fac_dept,
        "username": fac_user,
        "password": fac_pass,
        "confirmPassword": fac_pass
    }

    status, res = make_request("/api/register", method="POST", body=payload_faculty)
    assert status == 200 and res.get("success"), f"Faculty registration failed: {res}"
    print(f"  [PASS] Faculty Account '{fac_user}' created successfully!")
    faculty_token = res["token"]

    # ----------------------------------------------------
    # TEST 4: FACULTY LOGIN & PROFILE SCOPING
    # ----------------------------------------------------
    print("\n4. Testing Faculty Login...")
    status, res = make_request("/api/login", method="POST", body={"username": fac_user, "password": fac_pass})
    assert status == 200 and res.get("success"), f"Faculty login failed: {res}"
    print(f"  [PASS] Faculty '{fac_user}' logged in successfully!")

    status, res = make_request("/api/auth/me", token=faculty_token)
    assert status == 200 and res.get("success")
    assert res["user"]["role"] == "Faculty"
    assert res["user"]["department"] == "Computer Science"
    print(f"  [PASS] Faculty profile retrieved: Role='{res['user']['role']}', Dept='{res['user']['department']}'!")

    # ----------------------------------------------------
    # TEST 5: DUPLICATE & VALIDATION REJECTIONS
    # ----------------------------------------------------
    print("\n5. Testing Duplicate Rejections & Field Validations...")

    # Duplicate Username
    p_dup_user = dict(payload_student)
    p_dup_user["studentId"] = f"STU_NEW_{ts}"
    p_dup_user["rollNumber"] = f"R_NEW_{ts}"
    p_dup_user["email"] = f"email_new_{ts}@college.edu"
    status, res = make_request("/api/register", method="POST", body=p_dup_user)
    assert status == 400 and not res.get("success")
    print(f"  [PASS] Duplicate Username correctly rejected: '{res.get('message')}'")

    # Duplicate Student ID
    p_dup_id = dict(payload_student)
    p_dup_id["username"] = f"user_new_{ts}"
    p_dup_id["rollNumber"] = f"R_NEW_{ts}"
    p_dup_id["email"] = f"email_new_{ts}@college.edu"
    status, res = make_request("/api/register", method="POST", body=p_dup_id)
    assert status == 400 and not res.get("success")
    print(f"  [PASS] Duplicate Student ID correctly rejected: '{res.get('message')}'")

    # Duplicate Roll Number
    p_dup_roll = dict(payload_student)
    p_dup_roll["username"] = f"user_new2_{ts}"
    p_dup_roll["studentId"] = f"STU_NEW2_{ts}"
    p_dup_roll["email"] = f"email_new2_{ts}@college.edu"
    status, res = make_request("/api/register", method="POST", body=p_dup_roll)
    assert status == 400 and not res.get("success")
    print(f"  [PASS] Duplicate Roll Number correctly rejected: '{res.get('message')}'")

    # Duplicate Email
    p_dup_email = dict(payload_student)
    p_dup_email["username"] = f"user_new3_{ts}"
    p_dup_email["studentId"] = f"STU_NEW3_{ts}"
    p_dup_email["rollNumber"] = f"R_NEW3_{ts}"
    status, res = make_request("/api/register", method="POST", body=p_dup_email)
    assert status == 400 and not res.get("success")
    print(f"  [PASS] Duplicate Email correctly rejected: '{res.get('message')}'")

    # Password Mismatch
    p_pass_mismatch = dict(payload_student)
    p_pass_mismatch["username"] = f"user_mismatch_{ts}"
    p_pass_mismatch["confirmPassword"] = "wrongpass"
    status, res = make_request("/api/register", method="POST", body=p_pass_mismatch)
    assert status == 400 and not res.get("success")
    print(f"  [PASS] Password Mismatch correctly rejected: '{res.get('message')}'")

    print("\n==================================================")
    print("ALL REGISTRATION & ROLE TESTS PASSED 100% SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    test_full_registration_module()
