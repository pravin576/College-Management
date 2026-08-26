import urllib.request
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

def test_reverted_system_verification():
    ts = int(time.time() * 1000) % 100000
    print("==================================================")
    print("TESTING REVERTED COLLEGE ERP SYSTEM (NO SMS / NO OTP)")
    print("==================================================")

    # 1. Normal Student Registration with user-defined Username & Password
    print("\n1. Testing Normal Student Registration...")
    stu_user = f"rev_stu_{ts}"
    stu_pass = "MySecretPass123!"
    status, res = make_request("/api/register", method="POST", body={
        "role": "Student",
        "name": f"Reverted Student {ts}",
        "year": "Second Year",
        "email": f"rev_stu_{ts}@college.edu",
        "mobile": f"98765{ts:05d}",
        "studentId": f"STU_REV_{ts}",
        "rollNumber": f"R_REV_{ts}",
        "department": "Computer Science",
        "username": stu_user,
        "password": stu_pass,
        "confirmPassword": stu_pass
    })
    assert status == 200 and res.get("success"), f"Student registration failed: {res}"
    assert res.get("username") == stu_user, f"Expected user-defined username '{stu_user}', got '{res.get('username')}'"
    assert "sms_sent" not in res, "SMS status should not exist in normal registration response"
    print(f"  [PASS] Student registered! Username: '{stu_user}'")

    # 2. Normal Student Login (No must_change_password)
    print("\n2. Testing Normal Student Login...")
    status, res = make_request("/api/login", method="POST", body={
        "username": stu_user,
        "password": stu_pass
    })
    assert status == 200 and res.get("success"), f"Student login failed: {res}"
    assert "must_change_password" not in res, "must_change_password flag should not be present in login response"
    stu_token = res["token"]
    print("  [PASS] Student login successful! Direct dashboard access without password-change prompt.")

    # 3. Normal Faculty Registration & Login
    print("\n3. Testing Normal Faculty Registration & Login...")
    fac_user = f"rev_fac_{ts}"
    fac_pass = "FacultyPass123!"
    status, res = make_request("/api/register", method="POST", body={
        "role": "Faculty",
        "name": f"Prof. Faculty {ts}",
        "department": "Information Technology",
        "email": f"rev_fac_{ts}@college.edu",
        "mobile": f"98764{ts:05d}",
        "username": fac_user,
        "password": fac_pass,
        "confirmPassword": fac_pass
    })
    assert status == 200 and res.get("success"), f"Faculty registration failed: {res}"
    
    status, res = make_request("/api/login", method="POST", body={"username": fac_user, "password": fac_pass})
    assert status == 200 and res.get("success"), f"Faculty login failed: {res}"
    print(f"  [PASS] Faculty registered and logged in! Username: '{fac_user}'")

    # 4. Verify Removed Endpoints (OTP, Change Password, SMS Logs/Config) return 401 or 404
    print("\n4. Verifying Removed Feature Endpoints Return Error / Not Found...")
    removed_endpoints = [
        "/api/auth/send-otp",
        "/api/auth/verify-otp",
        "/api/auth/change-password",
        "/api/admin/resend-credentials",
        "/api/admin/sms-logs",
        "/api/admin/sms-config"
    ]
    for path in removed_endpoints:
        status, res = make_request(path, method="POST", body={}, token=stu_token)
        assert status in [404, 405, 401], f"Expected endpoint {path} to return 404/405/401, got {status}"
        print(f"  [PASS] Removed endpoint '{path}' returned status {status} (No longer available)")

    print("\n==================================================")
    print("REVERTED COLLEGE ERP SYSTEM TEST PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_reverted_system_verification()
