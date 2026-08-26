import urllib.request
import json

BASE_URL = "http://localhost:8000"

def make_request(url, method="GET", data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(f"{BASE_URL}{url}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read()
            return response.status, json.loads(res_body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        res_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(res_body)
        except Exception:
            return e.code, res_body

def run_tests():
    print("==================================================")
    print("TESTING PASSWORD ENHANCEMENTS & REGISTRATION SUCCESS")
    print("==================================================")

    # 1. Test Registration
    reg_payload = {
        "role": "Student",
        "name": "Karan Sharma",
        "year": "First Year",
        "email": "karan.sharma@college.edu",
        "mobile": "9876543219",
        "studentId": "STU9001",
        "rollNumber": "R9001",
        "department": "Computer Engineering",
        "username": "karan_student",
        "password": "Password@123",
        "confirmPassword": "Password@123"
    }

    status, reg_res = make_request("/api/register", method="POST", data=reg_payload)
    assert status == 200 and reg_res.get("success"), f"Registration failed: {reg_res}"
    print(f"[PASS] 1. Student Registration Successful! User: {reg_res['user']['username']}")

    # 2. Test Login with Registered User Credentials
    status, login_res = make_request("/api/login", method="POST", data={"username": "karan_student", "password": "Password@123"})
    assert status == 200 and login_res.get("success"), f"Login failed: {login_res}"
    print(f"[PASS] 2. Login Successful for registered user '{login_res['user']['username']}'")

    print("\n==================================================")
    print("ALL PASSWORD ENHANCEMENT TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
