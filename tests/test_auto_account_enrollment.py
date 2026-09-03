import urllib.request
import urllib.parse
import json
import uuid
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
    print("RUNNING COMPLETE AUTHENTICATION & ENROLLMENT NUMBER VERIFICATION SUITE")
    print("="*70)
    
    passed = 0
    failed = 0
    
    def record_result(test_name, success, details=""):
        nonlocal passed, failed
        if success:
            passed += 1
            print(f" [PASS] {test_name}")
        else:
            failed += 1
            print(f" [FAIL] {test_name}: {details}")

    admin_client = make_client()
    
    # 1. Login as Admin
    status, res = req(admin_client, "POST", "/api/login", {"username": "admin", "password": "admin123"})
    if status == 200 and res.get("success"):
        record_result("1. Admin Login", True)
    else:
        record_result("1. Admin Login", False, f"Status: {status}, Res: {res}")
        return

    # Generate unique test Enrollment Number and Roll Number
    rand_suffix = str(uuid.uuid4())[:6].upper()
    test_enrollment_no = f"EN2026_{rand_suffix}"
    test_roll_no = f"R_{rand_suffix}"
    test_email = f"student_{rand_suffix.lower()}@college.edu"

    # 2. Admin creates new Student -> Verify automatic active login account creation
    student_payload = {
        "id": test_enrollment_no,
        "rollNumber": test_roll_no,
        "name": f"Automated Student {rand_suffix}",
        "email": test_email,
        "mobile": "9876543210",
        "gender": "Male",
        "dob": "2005-05-15",
        "department": "Computer Engineering",
        "year": "First Year",
        "semester": "Semester 1",
        "division": "A",
        "admissionYear": "2026",
        "address": "Campus Hostel"
    }

    status, create_stu_res = req(admin_client, "POST", "/api/students", student_payload)
    if status == 200 and create_stu_res.get("success"):
        record_result("2. Admin Creates Student with Enrollment Number", True)
    else:
        record_result("2. Admin Creates Student with Enrollment Number", False, f"Status: {status}, Res: {create_stu_res}")

    # 3. Direct Student Login using Enrollment Number + Generated Temporary Password
    stu_temp_pass = create_stu_res.get("credentials", {}).get("temporaryPassword") or "student123"
    stu_client = make_client()
    status, stu_login_res = req(stu_client, "POST", "/api/login", {
        "username": test_enrollment_no,
        "password": stu_temp_pass
    })
    
    if status == 200 and stu_login_res.get("success"):
        user_info = stu_login_res.get("user", {})
        if user_info.get("role") == "Student" and (user_info.get("student_id") == test_enrollment_no or user_info.get("username") == test_enrollment_no):
            record_result("3. Student Direct Login via Enrollment Number", True)
        else:
            record_result("3. Student Direct Login via Enrollment Number", False, f"User info: {user_info}")
    else:
        record_result("3. Student Direct Login via Enrollment Number", False, f"Status: {status}, Res: {stu_login_res}")

    # 4. Student Isolation: Student logged in sees only their own data
    status, own_profile_res = req(stu_client, "GET", f"/api/students?id={test_enrollment_no}")
    if status == 200 and own_profile_res.get("success"):
        record_result("4. Student Data Isolation - Access Own Profile", True)
    else:
        record_result("4. Student Data Isolation - Access Own Profile", False, f"Status: {status}, Res: {own_profile_res}")

    # 5. Duplicate Enrollment Number Check
    status, dup_stu_res = req(admin_client, "POST", "/api/students", student_payload)
    if status == 400 and not dup_stu_res.get("success"):
        record_result("5. Duplicate Enrollment Number Rejection Check", True)
    else:
        record_result("5. Duplicate Enrollment Number Rejection Check", False, f"Status: {status}, Res: {dup_stu_res}")

    # 6. Admin creates new Faculty with Faculty ID
    test_fac_id = f"FAC_{rand_suffix}"
    faculty_payload = {
        "id": test_fac_id,
        "name": f"Automated Faculty {rand_suffix}",
        "department": "Computer Engineering",
        "designation": "Assistant Professor",
        "email": f"faculty_{rand_suffix.lower()}@college.edu",
        "mobile": "9876543211",
        "experience": "5 Years",
        "status": "Active"
    }

    status, create_fac_res = req(admin_client, "POST", "/api/faculty", faculty_payload)
    if status == 200 and create_fac_res.get("success"):
        record_result("6. Admin Creates Faculty with Faculty ID", True)
    else:
        record_result("6. Admin Creates Faculty with Faculty ID", False, f"Status: {status}, Res: {create_fac_res}")

    # 7. Direct Faculty Login using Faculty ID + Generated Temporary Password
    fac_temp_pass = create_fac_res.get("credentials", {}).get("temporaryPassword") or "faculty123"
    fac_client = make_client()
    status, fac_login_res = req(fac_client, "POST", "/api/login", {
        "username": test_fac_id,
        "password": fac_temp_pass
    })
    
    if status == 200 and fac_login_res.get("success"):
        fac_user_info = fac_login_res.get("user", {})
        if fac_user_info.get("role") == "Faculty" and (fac_user_info.get("faculty_id") == test_fac_id or fac_user_info.get("username") == test_fac_id):
            record_result("7. Faculty Direct Login via Faculty ID", True)
        else:
            record_result("7. Faculty Direct Login via Faculty ID", False, f"User info: {fac_user_info}")
    else:
        record_result("7. Faculty Direct Login via Faculty ID", False, f"Status: {status}, Res: {fac_login_res}")

    # 8. Duplicate Self-Registration Rejection for existing Enrollment Number / Faculty ID
    status, dup_reg_res = req(make_client(), "POST", "/api/register", {
        "role": "Student",
        "name": "Another Name",
        "email": f"another_{rand_suffix.lower()}@college.edu",
        "username": f"user_{rand_suffix.lower()}",
        "password": "password123",
        "confirmPassword": "password123",
        "studentId": test_enrollment_no,
        "department": "Computer Engineering"
    })
    if status == 400 and not dup_reg_res.get("success"):
        record_result("8. Prevent Duplicate Registration on Existing Enrollment Number", True)
    else:
        record_result("8. Prevent Duplicate Registration on Existing Enrollment Number", False, f"Status: {status}, Res: {dup_reg_res}")

    print("\n" + "="*70)
    print(f"VERIFICATION RESULTS: {passed} PASSED, {failed} FAILED (TOTAL: {passed+failed})")
    print("="*70 + "\n")

    if failed > 0:
        exit(1)

if __name__ == "__main__":
    run_tests()
