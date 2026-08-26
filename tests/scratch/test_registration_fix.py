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
    print("TESTING ALL ROLE REGISTRATION AND LOGIN FIXES")
    print("==================================================")

    # 1. Test Faculty Registration
    fac_payload = {
        "role": "Faculty",
        "name": "Prof. Aniket Deshmukh",
        "email": "aniket.deshmukh@college.edu",
        "mobile": "9876543210",
        "department": "Computer Engineering",
        "username": "aniket_fac",
        "password": "facpassword123",
        "confirmPassword": "facpassword123"
    }
    status, fac_res = make_request("/api/register", method="POST", data=fac_payload)
    assert status == 200 and fac_res.get("success"), f"Faculty registration failed: {fac_res}"
    print(f"[PASS] 1. Faculty Registration Successful! Message: '{fac_res.get('message')}'")

    # 2. Test Faculty Login
    status, login_res = make_request("/api/login", method="POST", data={"username": "aniket_fac", "password": "facpassword123"})
    assert status == 200 and login_res.get("success"), f"Faculty login failed: {login_res}"
    assert login_res["user"]["role"] == "Faculty", f"Expected Faculty role, got {login_res['user']['role']}"
    print(f"[PASS] 2. Faculty Login Successful! User: {login_res['user']['name']} ({login_res['user']['role']})")

    # 3. Test HOD Registration & Login
    hod_payload = {
        "role": "HOD",
        "name": "Dr. Sunita Patil",
        "email": "sunita.hod@college.edu",
        "mobile": "9876543211",
        "department": "Information Technology",
        "qualification": "Ph.D. in IT",
        "experience": "15 Years",
        "username": "sunita_hod",
        "password": "hodpassword123",
        "confirmPassword": "hodpassword123"
    }
    status, hod_res = make_request("/api/register", method="POST", data=hod_payload)
    assert status == 200 and hod_res.get("success"), f"HOD registration failed: {hod_res}"
    print(f"[PASS] 3. HOD Registration Successful! Message: '{hod_res.get('message')}'")

    status, hod_login_res = make_request("/api/login", method="POST", data={"username": "sunita_hod", "password": "hodpassword123"})
    assert status == 200 and hod_login_res.get("success"), f"HOD login failed: {hod_login_res}"
    print(f"[PASS] 4. HOD Login Successful! User: {hod_login_res['user']['name']} ({hod_login_res['user']['role']})")

    # 5. Test Administrator Registration & Login
    admin_payload = {
        "role": "Administrator",
        "name": "New Admin User",
        "email": "newadmin@college.edu",
        "mobile": "9876543212",
        "username": "new_admin",
        "password": "adminpassword123",
        "confirmPassword": "adminpassword123"
    }
    status, admin_res = make_request("/api/register", method="POST", data=admin_payload)
    assert status == 200 and admin_res.get("success"), f"Admin registration failed: {admin_res}"
    print(f"[PASS] 5. Admin Registration Successful! Message: '{admin_res.get('message')}'")

    status, admin_login_res = make_request("/api/login", method="POST", data={"username": "new_admin", "password": "adminpassword123"})
    assert status == 200 and admin_login_res.get("success"), f"Admin login failed: {admin_login_res}"
    print(f"[PASS] 6. Admin Login Successful! User: {admin_login_res['user']['name']} ({admin_login_res['user']['role']})")

    print("\n==================================================")
    print("ALL ROLE REGISTRATION & LOGIN TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
