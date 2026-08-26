import urllib.request
import json
import base64
import io
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from app import build_xlsx_bytes, parse_xlsx_bytes

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
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return response.status, json.loads(res_body.decode("utf-8"))
            return response.status, res_body
    except urllib.error.HTTPError as e:
        res_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(res_body)
        except Exception:
            return e.code, res_body

def run_tests():
    print("==================================================")
    print("STARTING BULK EXCEL IMPORT INTEGRATION TEST SUITE")
    print("==================================================")

    # 1. Admin Login
    status, login_res = make_request("/api/login", method="POST", data={"username": "admin", "password": "adminpassword"})
    assert status == 200 and login_res.get("success"), f"Admin login failed: {login_res}"
    admin_token = login_res["token"]
    print("[PASS] 1. Admin Login Successful")

    # 2. Template Downloads
    status, stu_tmpl = make_request("/api/students/excel-template")
    assert status == 200 and isinstance(stu_tmpl, bytes) and len(stu_tmpl) > 100, "Student template download failed"
    print(f"[PASS] 2a. Student Excel Template Download OK ({len(stu_tmpl)} bytes)")

    status, att_tmpl = make_request("/api/attendance/excel-template")
    assert status == 200 and isinstance(att_tmpl, bytes) and len(att_tmpl) > 100, "Attendance template download failed"
    print(f"[PASS] 2b. Attendance Excel Template Download OK ({len(att_tmpl)} bytes)")

    # 3. Test Student Excel Import with 1,000 records + 2 duplicates + 1 invalid
    headers_stu = [
        "Student ID", "Roll Number", "Student Name", "Email", "Mobile Number",
        "Gender", "DOB", "Department", "Year", "Semester", "Division",
        "Admission Year", "Address", "Status"
    ]
    rows_stu = []
    # 1,000 valid rows
    for i in range(1, 1001):
        s_id = f"STU_EXCEL_{i:04d}"
        roll = f"R{i:04d}"
        name = f"Excel Student {i}"
        email = f"excel_stu_{i}@college.edu"
        rows_stu.append([s_id, roll, name, email, "9876543210", "Male", "2005-01-01", "Computer Engineering", "Second Year", "Semester 3", "A", "2026", "Awasari", "Active"])

    # 2 duplicate rows
    rows_stu.append(["STU_EXCEL_0001", "R0001", "Duplicate 1", "dup1@college.edu", "9876543210", "Male", "2005-01-01", "Computer Engineering", "Second Year", "Semester 3", "A", "2026", "Awasari", "Active"])
    rows_stu.append(["STU_EXCEL_9999", "R0002", "Duplicate Roll", "dup2@college.edu", "9876543210", "Male", "2005-01-01", "Computer Engineering", "Second Year", "Semester 3", "A", "2026", "Awasari", "Active"])

    # 1 invalid row (missing name)
    rows_stu.append(["STU_EXCEL_8888", "R8888", "", "invalid@college.edu", "9876543210", "Male", "2005-01-01", "Computer Engineering", "Second Year", "Semester 3", "A", "2026", "Awasari", "Active"])

    xlsx_stu_bytes = build_xlsx_bytes(headers_stu, rows_stu)
    b64_stu = base64.b64encode(xlsx_stu_bytes).decode("utf-8")

    status, import_res = make_request("/api/students/import-excel", method="POST", data={"file_base64": b64_stu}, token=admin_token)
    assert status == 200 and import_res.get("success"), f"Student Excel import failed: {import_res}"
    assert import_res["totalRecords"] == 1003, f"Expected 1003 total, got {import_res['totalRecords']}"
    assert import_res["addedCount"] == 1000, f"Expected 1000 added, got {import_res['addedCount']}"
    assert import_res["duplicateCount"] == 2, f"Expected 2 duplicates, got {import_res['duplicateCount']}"
    assert import_res["failedCount"] == 1, f"Expected 1 failed, got {import_res['failedCount']}"
    print(f"[PASS] 3. Student Excel Import OK (1,000 Added, 2 Duplicates, 1 Failed)")

    # 4. Test Attendance Excel Import with 100 rows + 2 duplicates + 1 invalid
    headers_att = [
        "Student ID", "Student Name", "Department", "Year", "Semester",
        "Division", "Subject", "Subject Code", "Date", "Attendance Status"
    ]
    rows_att = []
    for i in range(1, 101):
        s_id = f"STU_EXCEL_{i:04d}"
        name = f"Excel Student {i}"
        rows_att.append([s_id, name, "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Present" if i % 2 == 0 else "Absent"])

    # 2 duplicate rows
    rows_att.append(["STU_EXCEL_0001", "Excel Student 1", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Present"])
    rows_att.append(["STU_EXCEL_0002", "Excel Student 2", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Absent"])

    # 1 invalid row (invalid student ID)
    rows_att.append(["STU_NON_EXISTENT", "Ghost Student", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Present"])

    xlsx_att_bytes = build_xlsx_bytes(headers_att, rows_att)
    b64_att = base64.b64encode(xlsx_att_bytes).decode("utf-8")

    status, att_import_res = make_request("/api/attendance/import-excel", method="POST", data={"file_base64": b64_att}, token=admin_token)
    assert status == 200 and att_import_res.get("success"), f"Attendance Excel import failed: {att_import_res}"
    assert att_import_res["totalRecords"] == 103, f"Expected 103 total, got {att_import_res['totalRecords']}"
    assert att_import_res["addedCount"] == 100, f"Expected 100 added, got {att_import_res['addedCount']}"
    assert att_import_res["duplicateCount"] == 2, f"Expected 2 duplicates, got {att_import_res['duplicateCount']}"
    assert att_import_res["failedCount"] == 1, f"Expected 1 failed, got {att_import_res['failedCount']}"
    print(f"[PASS] 4. Attendance Excel Import OK (100 Imported, 2 Duplicates, 1 Failed)")

    # 5. Test Attendance Filtering
    status, att_list = make_request("/api/attendance?department=Computer%20Engineering&year=Second%20Year&semester=Semester%203&division=A", token=admin_token)
    assert status == 200 and len(att_list.get("attendance", [])) >= 100, f"Attendance filtering failed: {att_list}"
    print(f"[PASS] 5. Attendance Multi-Filter OK ({len(att_list['attendance'])} records returned)")

    # 6. Test Error Report Export Endpoint
    status, err_report = make_request("/api/excel/export-errors", method="POST", data={"errors": att_import_res["errors"]}, token=admin_token)
    assert status == 200 and isinstance(err_report, bytes) and b"Excel Row Number" in err_report, "Error report export failed"
    print(f"[PASS] 6. Downloadable Error Report Export OK ({len(err_report)} bytes)")

    # 7. Cleanup Test Students and Attendance
    status, del_res = make_request("/api/students?id=STU_EXCEL_0001", method="DELETE", token=admin_token)
    print(f"[PASS] 7. Test Cleanup Initiated")

    print("\n==================================================")
    print("ALL BULK EXCEL IMPORT INTEGRATION TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
