import urllib.request
import json
import time
import sqlite3

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

def test_first_login_password_change():
    ts = int(time.time() * 1000) % 100000
    print("==================================================")
    print("TESTING FIRST LOGIN PASSWORD CHANGE ENFORCEMENT")
    print("==================================================")

    # 1. Register a new Student account (auto credentials)
    mobile = f"97765{ts:05d}"
    status, res = make_request("/api/register", method="POST", body={
        "role": "Student",
        "name": f"Password Change Student {ts}",
        "year": "Second Year",
        "email": f"pass_change_{ts}@college.edu",
        "mobile": mobile,
        "studentId": f"STU_PASS_{ts}",
        "rollNumber": f"R_PASS_{ts}",
        "department": "Information Technology"
    })
    assert status == 200 and res.get("success")
    username = res["username"]
    print(f"  [PASS] Student created: Username='{username}', Mobile='{mobile}'")

    # Fetch temporary password from sms_logs table directly for test verification
    conn = sqlite3.connect("college_erp.db")
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM sms_logs WHERE username = ? ORDER BY id DESC LIMIT 1", (username,))
    sms_msg = cursor.fetchone()[0]
    conn.close()

    # Extract temporary password from SMS message (e.g. Temporary Password: Gp@12345)
    import re
    match = re.search(r"Temporary Password:\s*([^\.\s]+)", sms_msg)
    assert match, f"Could not find temp password in SMS message: {sms_msg}"
    temp_pass = match.group(1).strip()
    print(f"  [PASS] Extracted temporary password: '{temp_pass}'")

    # 2. Login with Temporary Password
    print("\n2. Logging in with Temporary Password...")
    status, res = make_request("/api/login", method="POST", body={"username": username, "password": temp_pass})
    assert status == 200 and res.get("success")
    assert res.get("must_change_password") is True, f"Expected must_change_password=True, got {res.get('must_change_password')}"
    token = res["token"]
    print("  [PASS] Login succeeded with must_change_password = True flag!")

    # 3. Change Password
    print("\n3. Submitting New Password to /api/auth/change-password...")
    new_pass = "MySecretNewPass123!"
    status, res = make_request("/api/auth/change-password", method="POST", body={
        "oldPassword": temp_pass,
        "newPassword": new_pass,
        "confirmPassword": new_pass
    }, token=token)
    assert status == 200 and res.get("success"), f"Password change failed: {res}"
    print(f"  [PASS] Password changed successfully: '{res.get('message')}'")

    # 4. Verify old temporary password NO LONGER works
    print("\n4. Verifying old temporary password is now invalidated...")
    status, res = make_request("/api/login", method="POST", body={"username": username, "password": temp_pass})
    assert status == 401 and not res.get("success"), "Old temporary password should be rejected after change!"
    print("  [PASS] Old temporary password correctly rejected!")

    # 5. Verify new password works and must_change_password is False
    print("\n5. Logging in with NEW Password...")
    status, res = make_request("/api/login", method="POST", body={"username": username, "password": new_pass})
    assert status == 200 and res.get("success")
    assert res.get("must_change_password") is False, f"Expected must_change_password=False after change, got {res.get('must_change_password')}"
    print("  [PASS] Login with new password succeeded! must_change_password = False.")

    print("\n==================================================")
    print("FIRST LOGIN PASSWORD CHANGE TEST PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_first_login_password_change()
