import urllib.request
import urllib.parse
import json

BASE_URL = "http://localhost:8000"

class TestClient:
    def __init__(self):
        self.cookie_header = None

    def request(self, method, endpoint, data=None):
        url = f"{BASE_URL}{endpoint}"
        req_data = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=req_data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.cookie_header:
            req.add_header("Cookie", self.cookie_header)

        try:
            with urllib.request.urlopen(req) as resp:
                headers = resp.headers
                if "Set-Cookie" in headers:
                    self.cookie_header = headers["Set-Cookie"].split(";")[0]
                resp_bytes = resp.read()
                return resp.status, json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
        except urllib.error.HTTPError as e:
            resp_bytes = e.read()
            return e.code, json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}

def run_tests():
    client = TestClient()
    
    print("--- 1. Testing Admin Login ---")
    status, login_res = client.request("POST", "/api/login", {
        "username": "admin",
        "password": "admin123"
    })
    print("Admin Login Status:", status, login_res)
    assert status == 200 and login_res.get("success")

    # Initial cleanup of any previous test leftovers
    client.request("DELETE", "/api/students?id=STU_TEST_999")
    client.request("DELETE", "/api/students?id=STU_TEST_888")
    client.request("DELETE", "/api/students?id=STU_BULK_01")
    client.request("DELETE", "/api/students?id=STU_BULK_02")

    print("\n--- 2. Testing Department-wise HOD Dashboard Stats ---")
    status, stats_comp = client.request("GET", "/api/hod/dashboard-stats?department=Computer%20Engineering")
    print("Comp Eng Stats:", stats_comp)
    assert stats_comp.get("success") and stats_comp.get("department") == "Computer Engineering"

    status, stats_mech = client.request("GET", "/api/hod/dashboard-stats?department=Mechanical%20Engineering")
    print("Mech Eng Stats:", stats_mech)
    assert stats_mech.get("success") and stats_mech.get("department") == "Mechanical Engineering"

    print("\n--- 3. Testing Cascading Filters in GET /api/students ---")
    status, stu_res = client.request("GET", "/api/students?department=Computer%20Engineering&year=Second%20Year&semester=Semester%203&division=A")
    print(f"Cascading Filter returned {len(stu_res.get('students', []))} students.")
    assert stu_res.get("success")

    print("\n--- 4. Testing Single Student Registration & Duplicate Validations ---")
    test_stu = {
        "id": "STU_TEST_999",
        "rollNumber": "R999",
        "name": "Test Student 999",
        "email": "test999@college.edu",
        "mobile": "9876543999",
        "gender": "Male",
        "dob": "2004-05-15",
        "department": "Computer Engineering",
        "year": "Second Year",
        "semester": "Semester 3",
        "division": "A",
        "admissionYear": "2026",
        "address": "Awasari"
    }

    status, reg_res = client.request("POST", "/api/students", test_stu)
    print("Register New Student Result:", status, reg_res)
    assert status == 200 and reg_res.get("success")

    # Duplicate Student ID test
    status, dup_id_res = client.request("POST", "/api/students", test_stu)
    print("Duplicate Student ID Result:", status, dup_id_res)
    assert status == 400 and "Duplicate Error" in dup_id_res.get("message", "")

    # Duplicate Roll Number test
    test_stu_dup_roll = dict(test_stu)
    test_stu_dup_roll["id"] = "STU_TEST_888"
    status, dup_roll_res = client.request("POST", "/api/students", test_stu_dup_roll)
    print("Duplicate Roll Number Result:", status, dup_roll_res)
    assert status == 400 and "Duplicate Error" in dup_roll_res.get("message", "")

    print("\n--- 5. Testing Bulk Student Registration ---")
    bulk_data = {
        "department": "Computer Engineering",
        "year": "Second Year",
        "semester": "Semester 3",
        "division": "A",
        "students": [
            {"id": "STU_BULK_01", "rollNumber": "RB01", "name": "Bulk Student One", "email": "bulk1@college.edu", "mobile": "9876543001"},
            {"id": "STU_BULK_02", "rollNumber": "RB02", "name": "Bulk Student Two", "email": "bulk2@college.edu", "mobile": "9876543002"},
            {"id": "STU_TEST_999", "rollNumber": "R999", "name": "Existing Dup", "email": "dup@college.edu", "mobile": "9876543003"}
        ]
    }
    status, bulk_res = client.request("POST", "/api/students/bulk", bulk_data)
    print("Bulk Insert Result:", status, bulk_res)
    assert bulk_res.get("success") and bulk_res.get("inserted") == 2 and bulk_res.get("skipped") == 1

    print("\n--- 6. Testing Faculty-wise Student Assignment ---")
    status, fac_list = client.request("GET", "/api/faculty?department=Computer%20Engineering")
    assert fac_list.get("success") and len(fac_list.get("faculty", [])) > 0
    fac_id = fac_list["faculty"][0]["id"]
    print("Assigning students to Faculty ID:", fac_id)

    status, assign_res = client.request("POST", "/api/faculty-students/assign", {
        "faculty_id": fac_id,
        "student_ids": ["STU_BULK_01", "STU_BULK_02"]
    })
    print("Assignment Result:", status, assign_res)
    assert assign_res.get("success")

    # Fetch assigned students for faculty
    status, assigned_res = client.request("GET", f"/api/faculty-students?faculty_id={fac_id}")
    print(f"Faculty {fac_id} currently assigned {len(assigned_res.get('students', []))} students.")
    assert assigned_res.get("success") and len(assigned_res.get("students", [])) >= 2

    # Remove student assignment
    status, remove_res = client.request("POST", "/api/faculty-students/remove", {
        "faculty_id": fac_id,
        "student_id": "STU_BULK_01"
    })
    print("Remove Assignment Result:", status, remove_res)
    assert remove_res.get("success")

    print("\n--- 7. Testing Cleanup ---")
    client.request("DELETE", "/api/students?id=STU_TEST_999")
    client.request("DELETE", "/api/students?id=STU_TEST_888")
    client.request("DELETE", "/api/students?id=STU_BULK_01")
    client.request("DELETE", "/api/students?id=STU_BULK_02")
    print("Cleanup completed.")

    print("\n==================================================")
    print("ALL STUDENT MANAGEMENT INTEGRATION TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
