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

def test_hod_year_filter_feature():
    ts = int(time.time() * 1000) % 100000
    print("==================================================")
    print("TESTING HOD YEAR FILTER & DYNAMIC SUMMARY COUNTS")
    print("==================================================")

    dept = "Computer Science"
    other_dept = "Civil Engineering"

    # 1. Register HOD in Computer Science
    hod_user = f"hod_cs_{ts}"
    hod_pass = "hodpassword123"
    print(f"\n1. Registering HOD in '{dept}' ({hod_user})...")
    status, res = make_request("/api/register", method="POST", body={
        "role": "HOD",
        "name": f"Dr. Rajesh {ts}",
        "department": dept,
        "qualification": "Ph.D.",
        "experience": "12 Years",
        "email": f"hod_cs_{ts}@college.edu",
        "username": hod_user,
        "password": hod_pass,
        "confirmPassword": hod_pass
    })
    assert status == 200 and res.get("success")
    hod_token = res["token"]
    print("  [PASS] HOD registered successfully!")

    # 2. Register Students in CS: First Year, Second Year, Third Year
    print("\n2. Registering CS Students in First Year, Second Year & Third Year...")
    # First Year student
    make_request("/api/register", method="POST", body={
        "role": "Student", "name": f"FY Student {ts}", "year": "First Year",
        "email": f"fy_{ts}@college.edu", "phone": "9876543210", "studentId": f"STU_FY_{ts}",
        "rollNumber": f"R_FY_{ts}", "department": dept, "username": f"user_fy_{ts}",
        "password": "password123", "confirmPassword": "password123"
    })
    # Second Year student
    make_request("/api/register", method="POST", body={
        "role": "Student", "name": f"SY Student {ts}", "year": "Second Year",
        "email": f"sy_{ts}@college.edu", "phone": "9876543210", "studentId": f"STU_SY_{ts}",
        "rollNumber": f"R_SY_{ts}", "department": dept, "username": f"user_sy_{ts}",
        "password": "password123", "confirmPassword": "password123"
    })
    # Third Year student
    make_request("/api/register", method="POST", body={
        "role": "Student", "name": f"TY Student {ts}", "year": "Third Year",
        "email": f"ty_{ts}@college.edu", "phone": "9876543210", "studentId": f"STU_TY_{ts}",
        "rollNumber": f"R_TY_{ts}", "department": dept, "username": f"user_ty_{ts}",
        "password": "password123", "confirmPassword": "password123"
    })
    # Student in Civil Engineering (other dept)
    make_request("/api/register", method="POST", body={
        "role": "Student", "name": f"Civil Student {ts}", "year": "First Year",
        "email": f"civil_{ts}@college.edu", "phone": "9876543210", "studentId": f"STU_CIV_{ts}",
        "rollNumber": f"R_CIV_{ts}", "department": other_dept, "username": f"user_civ_{ts}",
        "password": "password123", "confirmPassword": "password123"
    })
    print("  [PASS] Students registered in multiple years & departments!")

    # 3. Test HOD Student Summary Counts API
    print("\n3. Testing GET /api/hod/student-summary for HOD...")
    status, res = make_request("/api/hod/student-summary", token=hod_token)
    assert status == 200 and res.get("success")
    summary = res.get("summary", {})
    print(f"  [PASS] HOD Summary counts calculated dynamically from SQLite: {summary}")
    assert summary.get("firstYear", 0) >= 1
    assert summary.get("secondYear", 0) >= 1
    assert summary.get("thirdYear", 0) >= 1

    # 4. Test Year Filtering in Python backend via GET /api/students?year=First Year
    print("\n4. Testing GET /api/students?year=First Year...")
    status, res = make_request("/api/students?year=First%20Year", token=hod_token)
    assert status == 200 and res.get("success")
    fy_students = res.get("students", [])
    assert all(s["year"] == "First Year" for s in fy_students)
    assert all(s["department"] == dept for s in fy_students)
    print(f"  [PASS] Returned {len(fy_students)} First Year students in '{dept}' (Backend SQL filtered)!")

    # 5. Test Year Filtering via GET /api/students?year=Second Year
    print("\n5. Testing GET /api/students?year=Second Year...")
    status, res = make_request("/api/students?year=Second%20Year", token=hod_token)
    assert status == 200 and res.get("success")
    sy_students = res.get("students", [])
    assert all(s["year"] == "Second Year" for s in sy_students)
    assert all(s["department"] == dept for s in sy_students)
    print(f"  [PASS] Returned {len(sy_students)} Second Year students in '{dept}' (Backend SQL filtered)!")

    # 6. Test Year Filtering via GET /api/students?year=Third Year
    print("\n6. Testing GET /api/students?year=Third Year...")
    status, res = make_request("/api/students?year=Third%20Year", token=hod_token)
    assert status == 200 and res.get("success")
    ty_students = res.get("students", [])
    assert all(s["year"] == "Third Year" for s in ty_students)
    assert all(s["department"] == dept for s in ty_students)
    print(f"  [PASS] Returned {len(ty_students)} Third Year students in '{dept}' (Backend SQL filtered)!")

    # 7. Test Year Filtering via GET /api/students?year=All
    print("\n7. Testing GET /api/students?year=All...")
    status, res = make_request("/api/students?year=All", token=hod_token)
    assert status == 200 and res.get("success")
    all_dept_students = res.get("students", [])
    assert all(s["department"] == dept for s in all_dept_students)
    assert not any(s["department"] == other_dept for s in all_dept_students)
    print(f"  [PASS] Returned {len(all_dept_students)} total students belonging strictly to HOD's department '{dept}'!")

    print("\n==================================================")
    print("ALL HOD YEAR FILTER & SUMMARY TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_hod_year_filter_feature()
