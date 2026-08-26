import urllib.request
import json
import base64
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from app import create_results_template_xlsx

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
            if response.headers.get("Content-Type", "").startswith("application/json"):
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
    print("TESTING EXAM RESULTS EXCEL IMPORT, EXPORT & DOCUMENTS")
    print("==================================================")

    # 1. Admin Login
    status, login_res = make_request("/api/login", method="POST", data={"username": "admin", "password": "adminpassword"})
    assert status == 200 and login_res.get("success"), f"Admin login failed: {login_res}"
    token = login_res["token"]
    print("[PASS] 1. Admin Login Successful")

    # 2. Template Download
    status, tpl_bytes = make_request("/api/results/excel-template", token=token)
    assert status == 200 and len(tpl_bytes) > 500, f"Template download failed, len={len(tpl_bytes)}"
    print(f"[PASS] 2. Exam Results Excel Template Downloaded OK ({len(tpl_bytes)} bytes)")

    # 3. Create student records to attach results to
    stu1_payload = {
        "role": "Student", "name": "Rahul Patil", "year": "Second Year",
        "email": "rahul.res@college.edu", "mobile": "9876543210",
        "studentId": "STU1001", "rollNumber": "R1001", "department": "Computer Engineering",
        "username": "rahul_res", "password": "password123", "confirmPassword": "password123"
    }
    make_request("/api/register", method="POST", data=stu1_payload)

    # 4. Generate & Upload Results Excel
    xlsx_bytes = create_results_template_xlsx()
    xlsx_b64 = base64.b64encode(xlsx_bytes).decode("utf-8")

    status, import_res = make_request("/api/results/import-excel", method="POST", data={"file_base64": xlsx_b64}, token=token)
    assert status == 200 and import_res.get("success"), f"Results Excel Import failed: {import_res}"
    assert import_res.get("addedCount", 0) > 0, f"Expected addedCount > 0, got {import_res}"
    print(f"[PASS] 3. Exam Results Excel Import OK (Added: {import_res.get('addedCount')}, Duplicates: {import_res.get('duplicateCount')})")

    # 5. Fetch Results
    status, res_list = make_request("/api/results", token=token)
    assert status == 200 and res_list.get("success"), f"Fetch results failed: {res_list}"
    results = res_list.get("results", [])
    assert len(results) > 0, "No results returned"
    res_id = results[0]["id"]
    print(f"[PASS] 4. Fetched Exam Results OK ({len(results)} records found)")

    # 6. Upload Marksheet Document / Photo (.png mock file)
    mock_img_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01").decode("utf-8")
    status, upload_res = make_request("/api/results/upload-document", method="POST", data={
        "result_id": res_id,
        "file_name": "marksheet_photo.png",
        "file_base64": mock_img_b64
    }, token=token)
    assert status == 200 and upload_res.get("success"), f"Document upload failed: {upload_res}"
    assert upload_res.get("document", "").startswith("/uploads/"), f"Unexpected doc URL: {upload_res}"
    print(f"[PASS] 5. Marksheet Document/Photo Upload OK (URL: '{upload_res.get('document')}')")

    # 7. Export Results
    status, csv_bytes = make_request("/api/results/export", token=token)
    assert status == 200 and b"Student ID" in csv_bytes, f"Results export failed: {csv_bytes}"
    print(f"[PASS] 6. Exam Results Export OK ({len(csv_bytes)} bytes exported)")

    print("\n==================================================")
    print("ALL EXAM RESULTS EXCEL IMPORT, EXPORT & DOC TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
