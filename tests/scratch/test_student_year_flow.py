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

def test_student_year_flow():
    ts = int(time.time() * 1000) % 100000
    print("--- TESTING STUDENT YEAR FULL FLOW ---")

    username = f"stu_yr_{ts}"
    email = f"stu_yr_{ts}@college.edu"
    student_id = f"STU_YR_{ts}"

    # 1. Register student with Year = "Second Year"
    print("\n1. Registering student with Year = 'Second Year'...")
    status, res = make_request("/api/register", method="POST", body={
        "role": "Student",
        "username": username,
        "password": "password123",
        "confirmPassword": "password123",
        "name": f"Pooja Sharma {ts}",
        "email": email,
        "studentId": student_id,
        "rollNumber": f"R{ts}",
        "mobile": "9876543210",
        "gender": "Female",
        "dob": "2003-08-20",
        "department": "Computer Science",
        "year": "Second Year",
        "semester": "Semester 3",
        "division": "A",
        "admissionYear": "2025",
        "address": "Pune"
    })
    assert status == 200 and res.get("success"), f"Student registration failed: {res}"
    student_token = res["token"]
    print(f"  [PASS] Registered {username} with token: {student_token[:10]}...")

    # 2. Login as Admin to inspect student table
    print("\n2. Logging in as Admin to inspect students table...")
    status, res = make_request("/api/login", method="POST", body={"username": "admin", "password": "admin123"})
    assert status == 200 and res.get("success"), f"Admin login failed: {res}"
    admin_token = res["token"]

    # 3. Retrieve student list and verify 'year' field is 'Second Year'
    print("\n3. Verifying student 'year' field in SQLite via GET /api/students...")
    status, res = make_request("/api/students", token=admin_token)
    assert status == 200 and res.get("success"), f"GET /api/students failed: {res}"
    students = res.get("students", [])
    target = next((s for s in students if s["id"] == student_id), None)
    assert target is not None, f"Registered student {student_id} not found in student list!"
    assert target.get("year") == "Second Year", f"Expected year 'Second Year', got: {target.get('year')}"
    print(f"  [PASS] Student '{student_id}' Year successfully saved as '{target.get('year')}' in SQLite database!")

    # 4. Update student Year to 'Third Year' via POST /api/students (Admin)
    print("\n4. Updating student Year to 'Third Year' via POST /api/students...")
    target["year"] = "Third Year"
    target["studentId"] = student_id
    target["rollNumber"] = target.get("roll_number", "R101")
    target["admissionYear"] = target.get("admission_year", "2025")
    status, res = make_request("/api/students", method="POST", body=target, token=admin_token)
    assert status == 200 and res.get("success"), f"Update student failed: {res}"

    # 5. Re-verify student Year is now 'Third Year'
    print("\n5. Re-verifying updated Year in SQLite...")
    status, res = make_request("/api/students", token=admin_token)
    assert status == 200 and res.get("success")
    updated_target = next((s for s in res.get("students", []) if s["id"] == student_id), None)
    assert updated_target.get("year") == "Third Year", f"Expected 'Third Year', got: {updated_target.get('year')}"
    print(f"  [PASS] Student Year successfully updated to '{updated_target.get('year')}' in SQLite!")

    # 6. Student own access scoping check
    print("\n6. Checking Student own access scoping to view their own Year...")
    status, res = make_request("/api/students", token=student_token)
    assert status == 200 and len(res.get("students", [])) == 1
    self_stu = res["students"][0]
    print(f"  [PASS] Student retrieved own record: Name='{self_stu['name']}', Year='{self_stu['year']}'!")

    print("\n==================================================")
    print("ALL STUDENT YEAR FLOW TESTS PASSED 100% SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    test_student_year_flow()
