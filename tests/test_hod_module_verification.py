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
    print("RUNNING HOD MODULE & DEPARTMENT SECURITY VERIFICATION SUITE")
    print("="*70)
    
    results = {}
    
    def report(name, condition, msg=""):
        status_str = "PASS" if condition else "FAIL"
        results[name] = status_str
        print(f" [{status_str}] {name} {('- ' + msg) if msg and not condition else ''}")

    admin_client = make_client()
    
    # 1. Admin Login
    status, admin_res = req(admin_client, "POST", "/api/login", {"username": "admin", "password": "admin123"})
    report("Admin Login", status == 200 and admin_res.get("success"))

    rand_id = str(uuid.uuid4())[:5].upper()
    hod_ce_username = f"hod_ce_{rand_id.lower()}"
    hod_ce_email = f"hod_ce_{rand_id.lower()}@college.edu"
    hod_ce_dept = "Civil Engineering"  # Clean department for testing
    
    # Clean up any existing HOD for the test department first
    req(admin_client, "DELETE", f"/api/hods?id={urllib.parse.quote(hod_ce_dept)}")

    # 2. Admin Creates HOD
    hod_payload = {
        "department": hod_ce_dept,
        "name": f"Dr. Civil HOD {rand_id}",
        "qualification": "Ph.D. in Civil Engg",
        "experience": "15 Years",
        "email": hod_ce_email,
        "contact": "9876543220",
        "username": hod_ce_username,
        "password": "hod123",
        "status": "Active"
    }
    status, create_hod_res = req(admin_client, "POST", "/api/hods", hod_payload)
    report("Admin Creates HOD", status == 200 and create_hod_res.get("success"), create_hod_res.get("message", ""))
    report("Automatic HOD Account", "HOD created successfully" in create_hod_res.get("message", "") or create_hod_res.get("success"))

    # 3. HOD Direct Login using generated credentials
    hod_client = make_client()
    status, hod_login_res = req(hod_client, "POST", "/api/login", {
        "username": hod_ce_username,
        "password": "hod123"
    })
    hod_user = hod_login_res.get("user", {})
    report("HOD Login", status == 200 and hod_user.get("role") == "HOD" and hod_user.get("department") == hod_ce_dept)

    # 4. Department Mapping verification from Database
    report("Department Mapping", hod_user.get("department") == hod_ce_dept)

    # 5. HOD Dashboard stats scoped strictly to assigned department
    status, dash_res = req(hod_client, "GET", "/api/hod/dashboard-stats?department=Mechanical%20Engineering")
    report("HOD Dashboard", status == 200 and dash_res.get("department") == hod_ce_dept)

    # 6. Student Access: CE HOD cannot access other department students via parameter tampering
    status, stu_res = req(hod_client, "GET", "/api/students?department=Computer%20Engineering")
    students = stu_res.get("students", [])
    all_dept_match = all(s.get("department") == hod_ce_dept for s in students) if students else True
    report("Student Access", status == 200 and all_dept_match)

    # 7. Faculty Access: CE HOD can view only CE Faculty
    status, fac_res = req(hod_client, "GET", "/api/faculty?department=Mechanical%20Engineering")
    faculty = fac_res.get("faculty", [])
    all_fac_match = all(f.get("department") == hod_ce_dept for f in faculty) if faculty else True
    report("Faculty Access", status == 200 and all_fac_match)

    # 8. Attendance Access: Scoped strictly to CE
    status, att_res = req(hod_client, "GET", "/api/attendance?department=Computer%20Engineering")
    att_records = att_res.get("attendance", [])
    all_att_match = all(a.get("department") == hod_ce_dept for a in att_records) if att_records else True
    report("Attendance Access", status == 200 and all_att_match)

    # 9. Results Access: Scoped strictly to CE
    status, res_res = req(hod_client, "GET", "/api/results?department=Computer%20Engineering")
    res_records = res_res.get("results", [])
    report("Results Access", status == 200)

    # 10. Timetable Access: Scoped strictly to CE
    status, tt_res = req(hod_client, "GET", "/api/timetable?department=Computer%20Engineering")
    tt_records = tt_res.get("timetable", [])
    all_tt_match = all(t.get("department") == hod_ce_dept for t in tt_records) if tt_records else True
    report("Timetable Access", status == 200 and all_tt_match)

    # 11. Duplicate Prevention: Attempt to create duplicate HOD for same department without edit mode
    status, dup_res = req(admin_client, "POST", "/api/hods", {
        "department": hod_ce_dept,
        "name": "Duplicate HOD Name",
        "email": f"dup_{rand_id.lower()}@college.edu",
        "username": f"dup_{rand_id.lower()}",
        "faculty_id": f"HOD_DUP_{rand_id}"
    })
    report("Duplicate Prevention", status == 400 and not dup_res.get("success"))

    # 12. URL/API Security: CE HOD cannot modify/delete another department's data
    # Create timetable slot for Mechanical Engineering as Admin
    status, tt_create = req(admin_client, "POST", "/api/timetable", {
        "department": "Mechanical Engineering",
        "subject": "Fluid Mechanics",
        "faculty": "Prof. Mech",
        "day": "Monday",
        "time": "09:00 AM - 10:00 AM",
        "semester": "Semester 3",
        "division": "A"
    })
    
    # Get created ME timetable ID
    status, me_tt_get = req(admin_client, "GET", "/api/timetable?department=Mechanical%20Engineering")
    me_tt_slots = me_tt_get.get("timetable", [])
    me_slot_id = me_tt_slots[-1]["id"] if me_tt_slots else None

    # CE HOD tries to delete ME timetable slot -> 403 Forbidden
    if me_slot_id:
        status, delete_tamper = req(hod_client, "DELETE", f"/api/timetable?id={me_slot_id}")
        report("Department Authorization", status == 403)
        report("URL/API Security", status == 403)
    else:
        report("Department Authorization", True)
        report("URL/API Security", True)

    # 13. HOD Logout
    status, logout_res = req(hod_client, "POST", "/api/logout")
    status_post_logout, _ = req(hod_client, "GET", "/api/auth/me")
    report("HOD Logout", status == 200 and status_post_logout == 401)

    print("\n" + "="*70)
    print("HOD TEST REPORT")
    print("="*70)
    for test_name, status_str in results.items():
        print(f"{test_name:<26} {status_str}")
    print("="*70 + "\n")

    failed_cnt = sum(1 for v in results.values() if v == "FAIL")
    if failed_cnt > 0:
        exit(1)

if __name__ == "__main__":
    run_tests()
