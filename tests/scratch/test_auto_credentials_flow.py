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

def test_automatic_credentials_system():
    ts = int(time.time() * 1000) % 100000
    print("==================================================")
    print("TESTING AUTOMATIC CREDENTIALS SYSTEM FOR ALL 4 ROLES")
    print("==================================================")

    # 1. Student Registration with Auto-Credentials
    print("\n1. Testing Student Registration with Automatic Credentials...")
    mobile_stu = f"98765{ts:05d}"
    status, res = make_request("/api/register", method="POST", body={
        "role": "Student",
        "name": f"Student Auto {ts}",
        "year": "First Year",
        "email": f"stu_auto_{ts}@college.edu",
        "mobile": mobile_stu,
        "studentId": f"STU_AUTO_{ts}",
        "rollNumber": f"R_AUTO_{ts}",
        "department": "Computer Engineering"
    })
    assert status == 200 and res.get("success"), f"Student auto-reg failed: {res}"
    stu_user = res["username"]
    assert stu_user.startswith("STU"), f"Expected Student username to start with STU, got {stu_user}"
    assert res.get("sms_sent"), "Expected SMS status to be true (Mock/Gateway)"
    print(f"  [PASS] Student created! Username: '{stu_user}', Mobile: '{mobile_stu}'")

    # 2. Faculty Registration with Auto-Credentials
    print("\n2. Testing Faculty Registration with Automatic Credentials...")
    mobile_fac = f"98764{ts:05d}"
    status, res = make_request("/api/register", method="POST", body={
        "role": "Faculty",
        "name": f"Prof. Faculty Auto {ts}",
        "department": "Information Technology",
        "email": f"fac_auto_{ts}@college.edu",
        "mobile": mobile_fac
    })
    assert status == 200 and res.get("success"), f"Faculty auto-reg failed: {res}"
    fac_user = res["username"]
    assert fac_user.startswith("FAC"), f"Expected Faculty username to start with FAC, got {fac_user}"
    print(f"  [PASS] Faculty created! Username: '{fac_user}', Mobile: '{mobile_fac}'")

    # 3. HOD Registration with Auto-Credentials
    print("\n3. Testing HOD Registration with Automatic Credentials...")
    mobile_hod = f"98763{ts:05d}"
    status, res = make_request("/api/register", method="POST", body={
        "role": "HOD",
        "name": f"Dr. HOD Auto {ts}",
        "department": "Mechanical Engineering",
        "qualification": "Ph.D. Mechanical",
        "experience": "15 Years",
        "email": f"hod_auto_{ts}@college.edu",
        "mobile": mobile_hod
    })
    assert status == 200 and res.get("success"), f"HOD auto-reg failed: {res}"
    hod_user = res["username"]
    assert hod_user.startswith("HOD"), f"Expected HOD username to start with HOD, got {hod_user}"
    print(f"  [PASS] HOD created! Username: '{hod_user}', Mobile: '{mobile_hod}'")

    # 4. Administrator Registration with Auto-Credentials
    print("\n4. Testing Administrator Registration with Automatic Credentials...")
    mobile_adm = f"98762{ts:05d}"
    status, res = make_request("/api/register", method="POST", body={
        "role": "Administrator",
        "name": f"Admin Auto {ts}",
        "email": f"admin_auto_{ts}@college.edu",
        "mobile": mobile_adm
    })
    assert status == 200 and res.get("success"), f"Admin auto-reg failed: {res}"
    adm_user = res["username"]
    assert adm_user.startswith("ADM"), f"Expected Admin username to start with ADM, got {adm_user}"
    print(f"  [PASS] Administrator created! Username: '{adm_user}', Mobile: '{mobile_adm}'")

    # 5. Duplicate Account Protection Test
    print("\n5. Testing Duplicate Mobile Protection...")
    status, res = make_request("/api/register", method="POST", body={
        "role": "Student",
        "name": "Duplicate Student",
        "email": f"dup_{ts}@college.edu",
        "mobile": mobile_stu,  # Duplicate mobile
        "studentId": f"STU_DUP_{ts}",
        "rollNumber": f"R_DUP_{ts}",
        "department": "Computer Engineering"
    })
    assert status == 400 and not res.get("success"), "Expected duplicate mobile rejection"
    print(f"  [PASS] Duplicate mobile correctly blocked: '{res.get('message')}'")

    print("\n==================================================")
    print("ALL 4 ROLES AUTO CREDENTIALS & SMS TEST PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_automatic_credentials_system()
