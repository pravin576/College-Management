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

def test_all_4_roles_registration():
    ts = int(time.time() * 1000) % 100000
    print("==================================================")
    print("TESTING REGISTRATION DROPDOWN FOR ALL 4 ROLES")
    print("==================================================")

    # 1. Student
    print("\n1. Testing Student Registration...")
    status, res = make_request("/api/register", method="POST", body={
        "role": "Student",
        "name": f"Student {ts}",
        "year": "Third Year",
        "email": f"stu_{ts}@college.edu",
        "phone": "9876543210",
        "studentId": f"STU_FOUR_{ts}",
        "rollNumber": f"R_FOUR_{ts}",
        "department": "Computer Science",
        "username": f"student_user_{ts}",
        "password": "password123",
        "confirmPassword": "password123"
    })
    assert status == 200 and res.get("success")
    print(f"  [PASS] Student registration successful: Role='{res['user']['role']}', User='{res['user']['username']}'")

    # 2. Faculty
    print("\n2. Testing Faculty Registration...")
    status, res = make_request("/api/register", method="POST", body={
        "role": "Faculty",
        "name": f"Prof. Faculty {ts}",
        "department": "Computer Science",
        "username": f"fac_user_{ts}",
        "password": "password123",
        "confirmPassword": "password123"
    })
    assert status == 200 and res.get("success")
    print(f"  [PASS] Faculty registration successful: Role='{res['user']['role']}', User='{res['user']['username']}'")

    # 3. HOD
    print("\n3. Testing HOD Registration...")
    status, res = make_request("/api/register", method="POST", body={
        "role": "HOD",
        "name": f"Dr. HOD {ts}",
        "department": "Computer Science",
        "qualification": "Ph.D. in Computer Engineering",
        "experience": "15 Years",
        "email": f"hod_{ts}@college.edu",
        "username": f"hod_user_{ts}",
        "password": "password123",
        "confirmPassword": "password123"
    })
    assert status == 200 and res.get("success")
    print(f"  [PASS] HOD registration successful: Role='{res['user']['role']}', User='{res['user']['username']}'")

    # 4. Administrator
    print("\n4. Testing Administrator Registration...")
    status, res = make_request("/api/register", method="POST", body={
        "role": "Administrator",
        "name": f"Admin System {ts}",
        "email": f"admin_{ts}@college.edu",
        "username": f"admin_user_{ts}",
        "password": "password123",
        "confirmPassword": "password123"
    })
    assert status == 200 and res.get("success")
    print(f"  [PASS] Administrator registration successful: Role='{res['user']['role']}', User='{res['user']['username']}'")

    print("\n==================================================")
    print("ALL 4 ROLES REGISTRATION DROPDOWN TEST PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_all_4_roles_registration()
