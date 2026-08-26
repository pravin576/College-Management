import urllib.request
import json

BASE_URL = "http://localhost:8000"

def run_tests():
    print("==================================================")
    print("Comprehensive College ERP Verification Test Suite")
    print("==================================================")

    # 1. Test Static HTML Pages
    pages = [
        "/index.html", "/login.html", "/home.html", "/dashboard.html",
        "/students.html", "/faculty.html", "/hod.html", "/attendance.html",
        "/results.html", "/fees.html", "/timetable.html", "/notices.html",
        "/documents.html", "/reports.html", "/contact.html", "/profile.html",
        "/settings.html"
    ]
    print("\n--- 1. Static HTML Pages Test ---")
    for p in pages:
        req = urllib.request.Request(f"{BASE_URL}{p}")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200, f"Page {p} returned {resp.status}"
            print(f"[OK] 200 OK: {p}")

    # 2. Public API Endpoints
    print("\n--- 2. Public API Endpoints Test ---")
    with urllib.request.urlopen(f"{BASE_URL}/api/departments") as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get("success") is True
        print(f"[OK] /api/departments: {len(data['departments'])} departments loaded")

    # 3. Admin Login & System Metrics
    print("\n--- 3. Admin Authentication & Session Setup ---")
    login_payload = json.dumps({"username": "admin", "password": "admin123", "role": "Administrator"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/login", data=login_payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        assert res.get("success") is True
        token = res.get("token")
        print(f"[OK] Admin Login successful! Token: {token[:10]}...")

    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Fetch active student ID dynamically
    req_stu = urllib.request.Request(f"{BASE_URL}/api/students", headers=auth_headers)
    with urllib.request.urlopen(req_stu) as resp:
        stu_list = json.loads(resp.read().decode('utf-8')).get("students", [])
        sample_stu_id = stu_list[0]["id"] if stu_list else "24210270254"

    # Fetch active fee record ID dynamically
    req_fee = urllib.request.Request(f"{BASE_URL}/api/fees", headers=auth_headers)
    with urllib.request.urlopen(req_fee) as resp:
        fee_list = json.loads(resp.read().decode('utf-8')).get("fees", [])
        sample_fee_stu_id = fee_list[0]["student_id"] if fee_list else sample_stu_id

    # 4. HOD Dashboard Stats
    print("\n--- 4. HOD Dashboard Stats Endpoint Test ---")
    req = urllib.request.Request(f"{BASE_URL}/api/hod/dashboard-stats?department=Computer%20Engineering", headers=auth_headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        assert res.get("success") is True
        stats = res.get("stats", {})
        print(f"[OK] HOD Dashboard Stats: Total Students={stats.get('totalStudents')}, Faculty={stats.get('totalFaculty')}, Attendance={stats.get('attendancePercentage')}%, Pass={stats.get('resultPassPercentage')}%")

    # 5. Student ID Card Payload
    print("\n--- 5. Student ID Card Payload Test ---")
    req = urllib.request.Request(f"{BASE_URL}/api/students/id-card?id={sample_stu_id}", headers=auth_headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        assert res.get("success") is True
        card = res.get("card", {})
        print(f"[OK] Student ID Card Generated for: {card.get('studentName')} ({card.get('studentId')})")

    # 6. Fee Receipt Payload
    print("\n--- 6. Fee Receipt Payload Test ---")
    req = urllib.request.Request(f"{BASE_URL}/api/fees/receipt?id={sample_fee_stu_id}", headers=auth_headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        assert res.get("success") is True
        rec = res.get("receipt", {})
        print(f"[OK] Fee Receipt Generated: Receipt No={rec.get('receiptNumber')}, Amount Paid=Rs.{rec.get('amountPaid')}")

    # 7. Reports Data & CSV Export
    print("\n--- 7. Reports Data & CSV Export Test ---")
    req = urllib.request.Request(f"{BASE_URL}/api/reports/data?type=student&department=All&year=All", headers=auth_headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        assert res.get("success") is True
        print(f"[OK] Student Report Loaded: {len(res.get('data', []))} records")

    req = urllib.request.Request(f"{BASE_URL}/api/reports/export?type=student", headers=auth_headers)
    with urllib.request.urlopen(req) as resp:
        csv_text = resp.read().decode('utf-8')
        assert "Student ID,Roll Number" in csv_text
        print("[OK] Reports CSV Export Stream Generated Successfully!")

    # 8. Document Management Vault
    print("\n--- 8. Document Management Vault Test ---")
    req = urllib.request.Request(f"{BASE_URL}/api/documents", headers=auth_headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        assert res.get("success") is True
        print(f"[OK] Document Vault: {len(res.get('documents', []))} documents loaded")

    print("\n==================================================")
    print("ALL 20 ERP REQUIREMENT TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
