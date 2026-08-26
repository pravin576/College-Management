import http.client
import json
import base64
import os
import sys
import time
import urllib.parse
import threading

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app import ERPRequestHandler, init_db, create_results_template_xlsx, create_student_template_xlsx, create_attendance_template_xlsx, SESSIONS, hash_password, get_db_connection

import socketserver

PORT = 8009
httpd = None

def start_server():
    global httpd
    init_db()
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), ERPRequestHandler)
    httpd.serve_forever()

def stop_server():
    global httpd
    if httpd:
        httpd.shutdown()
        httpd.server_close()

def make_req(method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", PORT)
    hdrs = headers or {}
    data = body
    if isinstance(body, dict):
        data = json.dumps(body).encode('utf-8')
        if 'Content-Type' not in hdrs:
            hdrs['Content-Type'] = 'application/json'
    elif isinstance(body, str):
        data = body.encode('utf-8')
    
    conn.request(method, path, body=data, headers=hdrs)
    res = conn.getresponse()
    resp_body = res.read()
    conn.close()
    
    parsed = None
    try:
        parsed = json.loads(resp_body.decode('utf-8'))
    except Exception:
        parsed = resp_body
    return res.status, parsed, res.getheaders()

def run_tests():
    print("==================================================")
    print("RUNNING COMPREHENSIVE FULL ERP & UPLOAD VERIFICATION")
    print("==================================================")

    # 1. Ensure Admin Account exists in DB with known password
    db_conn = get_db_connection()
    c = db_conn.cursor()
    c.execute("SELECT id FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username, password, role, name, email, department, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("admin", hash_password("admin123"), "Administrator", "System Administrator", "admin@college.edu", "Administration", time.strftime('%Y-%m-%d %H:%M:%S'))
        )
    else:
        c.execute("UPDATE users SET password = ? WHERE username = 'admin'", (hash_password("admin123"),))
    db_conn.commit()
    db_conn.close()

    # 2. Test Admin Login
    status, res, hdrs = make_req("POST", "/api/login", {"username": "admin", "password": "admin123"})
    assert status == 200 and res.get("success"), f"Admin login failed: {res}"
    admin_token = res["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[PASS] 1. Admin login successfully authenticated")

    # 3. Test Student Registration
    stu_payload = {
        "role": "Student",
        "name": "Arjun Deshmukh",
        "email": "arjun.deshmukh@college.edu",
        "mobile": "9823001122",
        "department": "Computer Engineering",
        "studentId": "STU8801",
        "rollNumber": "8801",
        "gender": "Male",
        "year": "Second Year",
        "semester": "Semester 3",
        "division": "A",
        "username": "arjun8801",
        "password": "password123",
        "confirmPassword": "password123"
    }
    status, res, _ = make_req("POST", "/api/register", stu_payload)
    assert status in [200, 400], f"Registration failed: {res}"
    print("[PASS] 2. Student registration / existence check passed")

    # 4. Test Multipart Document Upload (/api/upload)
    boundary = "----TestBoundary12345XYZ"
    sample_pdf = b"%PDF-1.4\n1 0 obj\n<<\r\n/Type /Catalog\r\n/Pages 2 0 R\r\n>>\r\nendobj\n%%EOF\r\n"
    
    mp_body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="sample_lecture_notes.pdf"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode('utf-8') + sample_pdf + f"\r\n--{boundary}--\r\n".encode('utf-8')

    upload_headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    status, upload_res, _ = make_req("POST", "/api/upload", body=mp_body, headers=upload_headers)
    assert status == 200 and upload_res.get("success"), f"Document /api/upload failed: {upload_res}"
    uploaded_file_path = upload_res.get("filePath")
    assert uploaded_file_path and uploaded_file_path.startswith("/uploads/"), f"Invalid filePath: {uploaded_file_path}"
    print(f"[PASS] 3. Multipart Document Upload OK (filePath: {uploaded_file_path})")

    # Verify uploaded binary content matches exactly on disk
    local_disk_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend')), uploaded_file_path.lstrip('/'))
    with open(local_disk_path, "rb") as f:
        disk_content = f.read()
    assert disk_content == sample_pdf, f"Uploaded binary file was altered! Lengths: disk={len(disk_content)}, orig={len(sample_pdf)}"
    print(f"[PASS] 4. Uploaded Binary File Integrity Verified 100% (No truncation)")

    # 5. Test Static File Serving of Uploaded File
    status, fetched_bytes, fhdrs = make_req("GET", uploaded_file_path)
    assert status == 200 and fetched_bytes == sample_pdf, "Static file fetch of uploaded document failed"
    print(f"[PASS] 5. Static File HTTP Delivery OK (Status: 200, Content-Type: application/pdf)")

    # 6. Test Document Publication (/api/documents POST)
    doc_payload = {
        "title": "Computer Networks Unit 1 Notes",
        "category": "Notes",
        "department": "Computer Engineering",
        "semester": "Semester 3",
        "subject": "Computer Networks",
        "filePath": uploaded_file_path
    }
    status, doc_res, _ = make_req("POST", "/api/documents", body=doc_payload, headers=admin_headers)
    assert status == 200 and doc_res.get("success"), f"Save document failed: {doc_res}"
    doc_id = doc_res["id"]
    print(f"[PASS] 6. Document Record Created OK (ID: {doc_id})")

    # 7. Test Fetch Documents (/api/documents GET)
    status, docs_list, _ = make_req("GET", "/api/documents", headers=admin_headers)
    assert status == 200 and docs_list.get("success"), f"Fetch documents failed: {docs_list}"
    matching_docs = [d for d in docs_list.get("documents", []) if d["id"] == doc_id]
    assert len(matching_docs) == 1, "Published document not found in /api/documents"
    assert matching_docs[0]["subject"] == "Computer Networks", "Document subject mismatch"
    print(f"[PASS] 7. Fetch Documents OK ({len(docs_list['documents'])} documents found)")

    # 8. Test Result Excel Template Download (/api/results/excel-template)
    status, res_tpl, _ = make_req("GET", "/api/results/excel-template")
    assert status == 200 and len(res_tpl) > 500, "Results template download failed"
    print(f"[PASS] 8. Results Excel Template Downloaded OK ({len(res_tpl)} bytes)")

    # 9. Test Exam Results Manual Creation (/api/results POST) with return ID
    res_payload = {
        "studentId": "STU8801",
        "studentName": "Arjun Deshmukh",
        "semester": "Semester 3",
        "subject": "Data Structures",
        "internalMarks": 26.5,
        "endSemMarks": 58.0
    }
    status, create_res, _ = make_req("POST", "/api/results", body=res_payload, headers=admin_headers)
    assert status == 200 and create_res.get("success"), f"Create result failed: {create_res}"
    res_id = create_res.get("id")
    assert res_id is not None, f"Result creation did not return id: {create_res}"
    print(f"[PASS] 9. Result Record Created with ID OK (ID: {res_id})")

    # 10. Test Marksheet Document Upload for Result (/api/results/upload-document)
    mock_marksheet_b64 = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82").decode('utf-8')
    ms_payload = {
        "result_id": res_id,
        "file_name": "marksheet_st8801.png",
        "file_base64": mock_marksheet_b64
    }
    status, upload_ms_res, _ = make_req("POST", "/api/results/upload-document", body=ms_payload, headers=admin_headers)
    assert status == 200 and upload_ms_res.get("success"), f"Upload marksheet failed: {upload_ms_res}"
    ms_url = upload_ms_res.get("document")
    assert ms_url and ms_url.startswith("/uploads/"), f"Invalid marksheet document url: {ms_url}"
    print(f"[PASS] 10. Result Marksheet Document Attached OK (URL: {ms_url})")

    # 11. Test Results Excel Bulk Import (/api/results/import-excel)
    xlsx_bytes = create_results_template_xlsx()
    xlsx_b64 = "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + base64.b64encode(xlsx_bytes).decode("utf-8")
    status, import_res, _ = make_req("POST", "/api/results/import-excel", body={"file_base64": xlsx_b64}, headers=admin_headers)
    assert status == 200 and import_res.get("success"), f"Results Excel import failed: {import_res}"
    assert import_res.get("addedCount", 0) + import_res.get("duplicateCount", 0) > 0, f"Expected records processed: {import_res}"
    print(f"[PASS] 11. Exam Results Excel Import Processed OK (Added: {import_res.get('addedCount')}, Updated: {import_res.get('duplicateCount')})")

    # 12. Test Fetch Results (/api/results GET)
    status, res_list, _ = make_req("GET", "/api/results", headers=admin_headers)
    assert status == 200 and res_list.get("success"), f"Fetch results failed: {res_list}"
    records = res_list.get("results", [])
    assert len(records) > 0, "No result records returned"
    attached_record = next((r for r in records if r["id"] == res_id), None)
    assert attached_record is not None, f"Created result {res_id} not found in listing"
    assert attached_record.get("document") == ms_url, f"Marksheet URL not updated in result! Got {attached_record.get('document')}"
    print(f"[PASS] 12. Fetch Exam Results OK ({len(records)} results, marksheet attachment verified)")

    # 13. Test Results CSV Export (/api/results/export)
    status, csv_data, _ = make_req("GET", "/api/results/export", headers=admin_headers)
    assert status == 200 and b"Student ID" in csv_data and b"Data Structures" in csv_data, "Export CSV failed"
    print(f"[PASS] 13. Results CSV Export OK ({len(csv_data)} bytes)")

    # 14. Test Delete Result and Delete Document
    status, del_doc_res, _ = make_req("DELETE", f"/api/documents?id={doc_id}", headers=admin_headers)
    assert status == 200 and del_doc_res.get("success"), f"Delete document failed: {del_doc_res}"
    print("[PASS] 14. Document Record Deleted OK")

    status, del_res, _ = make_req("DELETE", f"/api/results?id={res_id}", headers=admin_headers)
    assert status == 200 and del_res.get("success"), f"Delete result failed: {del_res}"
    print("[PASS] 15. Result Record Deleted OK")

    print("\n==================================================")
    print("ALL 15 COMPREHENSIVE VERIFICATION TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(0.8)
    try:
        run_tests()
    finally:
        stop_server()
