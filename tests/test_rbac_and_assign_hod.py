import os
import sys
import json
import time

# Add backend directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from config.database import get_db_connection
from auth.permissions import SESSIONS
from auth.utils import hash_password

def run_tests():
    print("=" * 60)
    print("RUNNING RBAC & ASSIGN NEW HOD VERIFICATION TEST SUITE")
    print("=" * 60)

    conn = get_db_connection()
    if not conn:
        print("[-] Database connection failed!")
        return False
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        # 1. Setup Mock Admin Session & HOD Session
        admin_token = "TEST_ADMIN_TOKEN_9999"
        hod_token = "TEST_HOD_TOKEN_8888"

        SESSIONS[admin_token] = {
            "id": 1,
            "username": "admin_test",
            "role": "Administrator",
            "department": "Administration"
        }

        SESSIONS[hod_token] = {
            "id": 2,
            "username": "hod_comp_test",
            "role": "HOD",
            "department": "Computer Engineering"
        }

        # 2. Test Admin Dashboard Stats Structure
        print("\n[TEST 1] Verifying Admin Global Dashboard Stats...")
        import admin.admin_controller as admin_ctrl

        class MockHandler:
            def __init__(self, token):
                self.headers = {"Authorization": f"Bearer {token}"}
                self.response_json = None
                self.status_code = 200

            def _send_json(self, data, status=200):
                self.response_json = data
                self.status_code = status

        admin_handler = MockHandler(admin_token)
        admin_ctrl.handle_post_dashboard_stats(admin_handler, {}, {})

        assert admin_handler.response_json["success"] is True, "Admin stats failed!"
        stats = admin_handler.response_json["stats"]
        assert "totalStudents" in stats, "totalStudents missing from global stats"
        assert "totalFaculty" in stats, "totalFaculty missing from global stats"
        assert "departmentStats" in stats, "departmentStats matrix missing for Admin"
        assert len(stats["departmentStats"]) > 0, "departmentStats array is empty"
        print(f"[+] Admin Global Stats returned {len(stats['departmentStats'])} department entries:")
        for d in stats["departmentStats"][:3]:
            print(f"    - {d['department']}: {d['students']} students, {d['faculty']} faculty, HOD: {d['hod']}")

        # 3. Test HOD Dashboard Stats Isolation
        print("\n[TEST 2] Verifying HOD Strict Department Isolation...")
        hod_handler = MockHandler(hod_token)
        admin_ctrl.handle_post_dashboard_stats(hod_handler, {}, {})

        assert hod_handler.response_json["success"] is True, "HOD stats failed!"
        h_stats = hod_handler.response_json["stats"]
        assert h_stats.get("isDepartmentView") is True, "isDepartmentView should be True for HOD"
        assert h_stats.get("department") == "Computer Engineering", "Department should be strictly Computer Engineering"
        assert "firstYearStudents" in h_stats, "firstYearStudents missing"
        assert "secondYearStudents" in h_stats, "secondYearStudents missing"
        assert "departmentFaculty" in h_stats, "departmentFaculty missing"
        assert "recentStudents" in h_stats, "recentStudents missing"
        print(f"[+] HOD Stats successfully isolated to '{h_stats['department']}':")
        print(f"    - Total Students: {h_stats['totalStudents']}")
        print(f"    - 1st/2nd/3rd Year: {h_stats.get('firstYearStudents')}/{h_stats.get('secondYearStudents')}/{h_stats.get('thirdYearStudents')}")
        print(f"    - Attendance Rate: {h_stats.get('attendancePercentage')}%")

        # 4. Test "Assign New HOD" Flow
        print("\n[TEST 3] Verifying Assign New HOD & Reassignment Workflow...")
        import hod.hod_controller as hod_ctrl

        test_dept = "Civil Engineering"
        # Clear any preexisting test artifacts for this department before testing
        cursor.execute("DELETE FROM hods WHERE department = %s", (test_dept,))
        cursor.execute("DELETE FROM users WHERE department = %s AND role = 'HOD'", (test_dept,))
        conn.commit()
        
        # A) Assign new HOD
        assign_body = {
            "department": test_dept,
            "name": "Dr. Test HOD Assignment",
            "qualification": "Ph.D. in Civil Structures",
            "experience": "15 Years",
            "email": "hod_civil_test@college.edu",
            "contact": "9876500001",
            "password": "TempHODPassword123!"
        }
        assign_handler = MockHandler(admin_token)
        hod_ctrl.handle_post_hods(assign_handler, {}, assign_body)

        assert assign_handler.response_json["success"] is True, f"Assign HOD failed: {assign_handler.response_json.get('message')}"
        print(f"[+] Initial Assign HOD succeeded: {assign_handler.response_json['message']}")

        # Verify database record in hods and users
        conn.commit()
        cursor.execute("SELECT * FROM hods WHERE department = %s", (test_dept,))
        hod_row = cursor.fetchone()
        assert hod_row is not None, "HOD record not found in hods table"
        assert hod_row["name"] == "Dr. Test HOD Assignment", f"HOD name mismatch: got {hod_row['name']}"

        cursor.execute("SELECT * FROM users WHERE email = %s AND role = 'HOD'", ("hod_civil_test@college.edu",))
        user_row = cursor.fetchone()
        assert user_row is not None, "HOD user account not found in users table"
        assert user_row["role"] == "HOD", "User role must be HOD"
        print(f"[+] Verified HOD user account created with username: {user_row['username']}")

        # B) Reassign / Replace HOD for the same department without errors
        print("\n[TEST 4] Verifying Seamless HOD Reassignment (Replacing Existing HOD)...")
        reassign_body = {
            "department": test_dept,
            "name": "Prof. Newly Reassigned HOD",
            "qualification": "M.Tech in Structural Engineering",
            "experience": "12 Years",
            "email": "hod_civil_new@college.edu",
            "contact": "9876500002",
            "is_edit": False
        }
        reassign_handler = MockHandler(admin_token)
        hod_ctrl.handle_post_hods(reassign_handler, {}, reassign_body)

        assert reassign_handler.response_json["success"] is True, f"Reassign HOD failed: {reassign_handler.response_json.get('message')}"
        print(f"[+] Seamless HOD Reassignment succeeded: {reassign_handler.response_json['message']}")

        conn.commit()
        cursor.execute("SELECT * FROM hods WHERE department = %s", (test_dept,))
        updated_hod_row = cursor.fetchone()
        assert updated_hod_row["name"] == "Prof. Newly Reassigned HOD", f"Updated HOD name mismatch: got {updated_hod_row['name']}"

        # C) Non-Admin trying to assign HOD must be 403 Forbidden
        print("\n[TEST 5] Verifying Non-Admin Access Control on HOD Management...")
        unauth_handler = MockHandler(hod_token)
        hod_ctrl.handle_post_hods(unauth_handler, {}, assign_body)
        assert unauth_handler.status_code == 403, f"Expected 403, got {unauth_handler.status_code}"
        print("[+] Non-Admin blocked with 403 Forbidden as expected.")

        # Cleanup test records
        cursor.execute("DELETE FROM hods WHERE department = %s", (test_dept,))
        cursor.execute("DELETE FROM users WHERE email IN ('hod_civil_test@college.edu', 'hod_civil_new@college.edu')")
        conn.commit()

        print("\n" + "=" * 60)
        print("ALL RBAC & ASSIGN HOD TESTS PASSED SUCCESSFULLY! (5/5)")
        print("=" * 60)
        return True

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
