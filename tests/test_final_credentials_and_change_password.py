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
    print("\n" + "="*75)
    print("RUNNING FINAL CREDENTIAL DELIVERY & FIRST-LOGIN PASSWORD CHANGE SUITE")
    print("="*75)
    
    results = {}
    
    def report(name, condition, msg=""):
        status_str = "PASS" if condition else "FAIL"
        results[name] = status_str
        print(f" [{status_str}] {name} {('- ' + msg) if msg and not condition else ''}")

    admin_client = make_client()
    
    # 1. Admin Login
    status, admin_res = req(admin_client, "POST", "/api/login", {"username": "admin", "password": "admin123"})
    report("1.1 Admin Login", status == 200 and admin_res.get("success"))

    rand_tag = str(uuid.uuid4())[:5].upper()
    
    # ----------------------------------------------------
    # SECTION 2: HOD Dynamic Credentials & First Login
    # ----------------------------------------------------
    hod_dept = "Civil Engineering"
    req(admin_client, "DELETE", f"/api/hods?id={urllib.parse.quote(hod_dept)}")

    hod_payload = {
        "department": hod_dept,
        "name": f"Dr. HOD Dynamic {rand_tag}",
        "qualification": "Ph.D. in Civil",
        "experience": "12 Years",
        "email": f"hod_dyn_{rand_tag.lower()}@college.edu",
        "contact": "9876543301",
        "username": f"hod_dyn_{rand_tag.lower()}"
    }
    status, hod_create_res = req(admin_client, "POST", "/api/hods", hod_payload)
    hod_cred = hod_create_res.get("credentials", {})
    hod_temp_pass = hod_cred.get("temporaryPassword", "")

    report("2.1 HOD Dynamic Credentials Generated", 
           status == 200 and bool(hod_temp_pass) and hod_temp_pass != "hod123" and len(hod_temp_pass) >= 8,
           f"Generated Password: {hod_temp_pass}")

    # HOD First Login
    hod_client = make_client()
    status, hod_login_res = req(hod_client, "POST", "/api/login", {
        "username": hod_payload["username"],
        "password": hod_temp_pass
    })
    report("2.2 HOD First Login with Temporary Password", 
           status == 200 and hod_login_res.get("must_change_password") is True)

    # HOD Mandatory Password Change Validation - Rejects same password
    status, same_pwd_res = req(hod_client, "POST", "/api/auth/first-login-change-password", {
        "currentPassword": hod_temp_pass,
        "newPassword": hod_temp_pass,
        "confirmPassword": hod_temp_pass
    })
    report("2.3 Password Change Rejects Same Password", status == 400)

    # HOD Mandatory Password Change Validation - Rejects mismatch
    status, mismatch_res = req(hod_client, "POST", "/api/auth/first-login-change-password", {
        "currentPassword": hod_temp_pass,
        "newPassword": "Hod#NewPassword2026",
        "confirmPassword": "DifferentPassword123"
    })
    report("2.4 Password Change Rejects Mismatched Confirmation", status == 400)

    # HOD Completes First-Login Password Change
    hod_new_pass = "Hod#SecurePass2026!"
    status, change_res = req(hod_client, "POST", "/api/auth/first-login-change-password", {
        "currentPassword": hod_temp_pass,
        "newPassword": hod_new_pass,
        "confirmPassword": hod_new_pass
    })
    report("2.5 HOD Password Change Succeeded", 
           status == 200 and change_res.get("must_change_password") is False)

    # HOD Login with New Password
    hod_new_client = make_client()
    status, new_login_res = req(hod_new_client, "POST", "/api/login", {
        "username": hod_payload["username"],
        "password": hod_new_pass
    })
    report("2.6 HOD Login with New Password (must_change_password = False)", 
           status == 200 and new_login_res.get("must_change_password") is False)

    # Verify old temporary password is dead
    status, old_login_fail = req(make_client(), "POST", "/api/login", {
        "username": hod_payload["username"],
        "password": hod_temp_pass
    })
    report("2.7 Old Temporary Password Dead", status == 401)

    # ----------------------------------------------------
    # SECTION 3: Faculty Dynamic Credentials & First Login
    # ----------------------------------------------------
    fac_id = f"FAC_DYN_{rand_tag}"
    fac_payload = {
        "id": fac_id,
        "name": f"Prof. Faculty {rand_tag}",
        "department": "Computer Engineering",
        "designation": "Assistant Professor",
        "email": f"fac_{rand_tag.lower()}@college.edu",
        "mobile": "9876543302",
        "experience": "5 Years",
        "status": "Active"
    }
    status, fac_create_res = req(admin_client, "POST", "/api/faculty", fac_payload)
    fac_cred = fac_create_res.get("credentials", {})
    fac_temp_pass = fac_cred.get("temporaryPassword", "")

    report("3.1 Faculty Dynamic Credentials Generated", 
           status == 200 and bool(fac_temp_pass) and fac_temp_pass != "faculty123",
           f"Generated Password: {fac_temp_pass}")

    fac_client = make_client()
    status, fac_login_res = req(fac_client, "POST", "/api/login", {
        "username": fac_id,
        "password": fac_temp_pass
    })
    report("3.2 Faculty First Login with Temporary Password", 
           status == 200 and fac_login_res.get("must_change_password") is True)

    fac_new_pass = "Faculty#New2026!"
    status, fac_change_res = req(fac_client, "POST", "/api/auth/first-login-change-password", {
        "currentPassword": fac_temp_pass,
        "newPassword": fac_new_pass,
        "confirmPassword": fac_new_pass
    })
    report("3.3 Faculty Password Change Succeeded", 
           status == 200 and fac_change_res.get("must_change_password") is False)

    # ----------------------------------------------------
    # SECTION 4: Student Dynamic Credentials & First Login
    # ----------------------------------------------------
    stu_enrollment = f"EN2026_DYN_{rand_tag}"
    stu_payload = {
        "id": stu_enrollment,
        "rollNumber": f"R_DYN_{rand_tag}",
        "name": f"Student Dynamic {rand_tag}",
        "department": "Computer Engineering",
        "year": "First Year",
        "semester": "Semester 1",
        "division": "A",
        "email": f"stu_{rand_tag.lower()}@college.edu",
        "mobile": "9876543303"
    }
    status, stu_create_res = req(admin_client, "POST", "/api/students", stu_payload)
    stu_cred = stu_create_res.get("credentials", {})
    stu_temp_pass = stu_cred.get("temporaryPassword", "")

    report("4.1 Student Dynamic Credentials Generated", 
           status == 200 and bool(stu_temp_pass) and stu_temp_pass != "student123",
           f"Generated Password: {stu_temp_pass}")

    stu_client = make_client()
    status, stu_login_res = req(stu_client, "POST", "/api/login", {
        "username": stu_enrollment,
        "password": stu_temp_pass
    })
    report("4.2 Student First Login via Enrollment Number", 
           status == 200 and stu_login_res.get("must_change_password") is True)

    stu_new_pass = "Student#New2026!"
    status, stu_change_res = req(stu_client, "POST", "/api/auth/first-login-change-password", {
        "currentPassword": stu_temp_pass,
        "newPassword": stu_new_pass,
        "confirmPassword": stu_new_pass
    })
    report("4.3 Student Password Change Succeeded", 
           status == 200 and stu_change_res.get("must_change_password") is False)

    # ----------------------------------------------------
    # SECTION 5: Administrator Password Reset
    # ----------------------------------------------------
    status, reset_res = req(admin_client, "POST", "/api/admin/reset-password", {
        "username": stu_enrollment
    })
    reset_cred = reset_res.get("credentials", {})
    reset_temp_pass = reset_cred.get("temporaryPassword", "")

    report("5.1 Admin Resets User Password & Receives New Temporary Credentials",
           status == 200 and bool(reset_temp_pass) and reset_temp_pass != stu_new_pass,
           f"Reset Temporary Password: {reset_temp_pass}")

    # Student logs in with reset temp password
    status, reset_login_res = req(make_client(), "POST", "/api/login", {
        "username": stu_enrollment,
        "password": reset_temp_pass
    })
    report("5.2 User Logs In with Reset Password & Flagged for Change",
           status == 200 and reset_login_res.get("must_change_password") is True)

    # ----------------------------------------------------
    # SECTION 6: Department & Assignment Isolation
    # ----------------------------------------------------
    # Assign student to faculty
    req(admin_client, "POST", "/api/faculty-students/assign", {
        "faculty_id": fac_id,
        "student_ids": [stu_enrollment]
    })

    # Faculty queries assigned students -> sees student
    status, fac_stu_res = req(fac_client, "GET", "/api/students")
    fac_students = fac_stu_res.get("students", [])
    report("6.1 Faculty Accesses Assigned Student", 
           status == 200 and any(s["id"] == stu_enrollment for s in fac_students))

    # HOD queries CE faculty -> denied/filtered for Civil HOD
    status, hod_fac_res = req(hod_new_client, "GET", "/api/faculty")
    hod_fac_list = hod_fac_res.get("faculty", [])
    report("6.2 HOD Department Isolation Maintained",
           status == 200 and all(f.get("department") == hod_dept for f in hod_fac_list) if hod_fac_list else True)

    print("\n" + "="*75)
    print("FINAL CREDENTIAL DELIVERY TEST REPORT")
    print("="*75)
    for test_name, status_str in results.items():
        print(f"{test_name:<60} {status_str}")
    print("="*75 + "\n")

    failed_cnt = sum(1 for v in results.values() if v == "FAIL")
    if failed_cnt > 0:
        exit(1)

if __name__ == "__main__":
    run_tests()
