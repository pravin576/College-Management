import urllib.request
import urllib.parse
import json
import http.cookiejar

BASE_URL = "http://127.0.0.1:8000"

def make_client():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    return opener

def req(opener, method, endpoint, data=None):
    url = BASE_URL + endpoint
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(request) as resp:
            content = resp.read().decode("utf-8")
            status = resp.status
            try:
                js = json.loads(content)
            except Exception:
                js = {"raw": content}
            return status, js
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            js = json.loads(content)
        except Exception:
            js = {"raw": content}
        return e.code, js
    except Exception as e:
        return 0, {"error": str(e)}

def run_tests():
    print("\n" + "="*70)
    print("RUNNING HOD REGISTRATION SPECIFIC TEST CASES (USER SPECIFIED 1 TO 6)")
    print("="*70)

    admin_client = make_client()
    st, admin_res = req(admin_client, "POST", "/api/login", {"username": "admin", "password": "admin123"})
    assert st == 200, "Admin login failed"

    # Clean up test department and user if they existed
    test_dept = "Electronics & Telecommunication"
    req(admin_client, "DELETE", f"/api/hods?id={urllib.parse.quote(test_dept)}")
    
    client = make_client()

    # ----------------------------------------------------
    # TEST 1 — New HOD Registration (User values)
    # ----------------------------------------------------
    test_hod_payload = {
        "role": "HOD",
        "name": "Ankita",
        "department": test_dept,
        "qualification": "PhD in Information Technology",
        "mobile": "1425365236",
        "experience": "6",
        "email": "ankita123@gmail.com",
        "username": "ankita123",
        "password": "ankita@123",
        "confirmPassword": "ankita@123"
    }

    st1, res1 = req(client, "POST", "/api/register", test_hod_payload)
    print(f"\n[TEST 1] New HOD Registration -> Status: {st1}, Success: {res1.get('success')}")
    print(f"         Message: {res1.get('message')}")
    assert st1 == 200 and res1.get("success"), f"Test 1 failed with {st1}: {res1}"

    # ----------------------------------------------------
    # TEST 2 — Same username again
    # ----------------------------------------------------
    dup_user_payload = {
        "role": "HOD",
        "name": "Ankita Duplicate User",
        "department": "Mechanical Engineering",
        "qualification": "PhD",
        "mobile": "9998887771",
        "experience": "5",
        "email": "ankita_unique@gmail.com",
        "username": "ankita123", # Duplicate username
        "password": "ankita@123",
        "confirmPassword": "ankita@123"
    }
    st2, res2 = req(client, "POST", "/api/register", dup_user_payload)
    print(f"\n[TEST 2] Duplicate Username -> Status: {st2}, Success: {res2.get('success')}")
    print(f"         Message: {res2.get('message')}")
    assert st2 == 400 and not res2.get("success") and "username" in res2.get("message", "").lower(), f"Test 2 failed: {res2}"

    # ----------------------------------------------------
    # TEST 3 — Same email again
    # ----------------------------------------------------
    dup_email_payload = {
        "role": "HOD",
        "name": "Ankita Duplicate Email",
        "department": "Mechanical Engineering",
        "qualification": "PhD",
        "mobile": "9998887772",
        "experience": "5",
        "email": "ankita123@gmail.com", # Duplicate email
        "username": "ankita_unique_user",
        "password": "ankita@123",
        "confirmPassword": "ankita@123"
    }
    st3, res3 = req(client, "POST", "/api/register", dup_email_payload)
    print(f"\n[TEST 3] Duplicate Email -> Status: {st3}, Success: {res3.get('success')}")
    print(f"         Message: {res3.get('message')}")
    assert st3 == 400 and not res3.get("success") and "email" in res3.get("message", "").lower(), f"Test 3 failed: {res3}"

    # ----------------------------------------------------
    # TEST 4 — Same department HOD
    # ----------------------------------------------------
    dup_dept_payload = {
        "role": "HOD",
        "name": "Another HOD",
        "department": test_dept, # Already has Ankita
        "qualification": "PhD",
        "mobile": "9998887773",
        "experience": "5",
        "email": "another_hod@gmail.com",
        "username": "another_hod",
        "password": "password123",
        "confirmPassword": "password123"
    }
    st4, res4 = req(client, "POST", "/api/register", dup_dept_payload)
    print(f"\n[TEST 4] Duplicate Department HOD -> Status: {st4}, Success: {res4.get('success')}")
    print(f"         Message: {res4.get('message')}")
    assert st4 == 400 and not res4.get("success") and "already has an hod" in res4.get("message", "").lower(), f"Test 4 failed: {res4}"

    # ----------------------------------------------------
    # TEST 5 — Password mismatch
    # ----------------------------------------------------
    mismatch_payload = {
        "role": "HOD",
        "name": "Mismatch HOD",
        "department": "Civil Engineering",
        "qualification": "PhD",
        "mobile": "9998887774",
        "experience": "5",
        "email": "mismatch@gmail.com",
        "username": "mismatch_hod",
        "password": "password123",
        "confirmPassword": "different_password"
    }
    st5, res5 = req(client, "POST", "/api/register", mismatch_payload)
    print(f"\n[TEST 5] Password Mismatch -> Status: {st5}, Success: {res5.get('success')}")
    print(f"         Message: {res5.get('message')}")
    assert st5 == 400 and not res5.get("success") and "match" in res5.get("message", "").lower(), f"Test 5 failed: {res5}"

    # ----------------------------------------------------
    # TEST 6 — Database Reachability & Connection Check
    # ----------------------------------------------------
    st6, res6 = req(client, "GET", "/api/health")
    print(f"\n[TEST 6] Health & DB Connectivity Check -> Status: {st6}, Response: {res6}")
    assert st6 == 200, f"Test 6 failed: {res6}"

    print("\n" + "="*70)
    print("ALL 6 SPECIFIC TEST CASES PASSED 100% WITHOUT HTTP 500 ERRORS!")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_tests()
