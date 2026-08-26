import urllib.request
import json
import time
import sqlite3
import re

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

def test_otp_verification_flow():
    ts = int(time.time() * 1000) % 100000
    mobile = f"96765{ts:05d}"
    print("==================================================")
    print("TESTING OPTIONAL MOBILE OTP VERIFICATION SYSTEM")
    print("==================================================")

    # 1. Send OTP
    print(f"\n1. Sending OTP to mobile number {mobile}...")
    status, res = make_request("/api/auth/send-otp", method="POST", body={"mobile": mobile})
    assert status == 200 and res.get("success"), f"Send OTP failed: {res}"
    print(f"  [PASS] OTP sent successfully: '{res.get('message')}'")

    # Fetch 6-digit OTP code from sms_logs
    conn = sqlite3.connect("college_erp.db")
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM sms_logs WHERE recipient_mobile = ? ORDER BY id DESC LIMIT 1", (mobile,))
    sms_msg = cursor.fetchone()[0]
    conn.close()

    match = re.search(r"OTP is (\d{6})", sms_msg)
    assert match, f"Could not parse 6-digit OTP from message: {sms_msg}"
    otp = match.group(1)
    print(f"  [PASS] Extracted OTP code from SMS log: '{otp}'")

    # 2. Verify with wrong OTP
    print("\n2. Verifying with incorrect OTP...")
    status, res = make_request("/api/auth/verify-otp", method="POST", body={"mobile": mobile, "otp": "000000"})
    assert status == 400 and not res.get("success")
    print(f"  [PASS] Incorrect OTP rejected: '{res.get('message')}'")

    # 3. Verify with correct OTP
    print("\n3. Verifying with correct OTP...")
    status, res = make_request("/api/auth/verify-otp", method="POST", body={"mobile": mobile, "otp": otp})
    assert status == 200 and res.get("success")
    print(f"  [PASS] OTP verified successfully: '{res.get('message')}'")

    print("\n==================================================")
    print("OPTIONAL MOBILE OTP VERIFICATION TEST PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_otp_verification_flow()
