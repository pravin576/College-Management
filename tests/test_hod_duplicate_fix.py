import os
import sys
import unittest
import json
import io

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config.database import get_db_connection, init_db
from router import handle_request
from auth.permissions import SESSIONS

class MockResponseHandler:
    def __init__(self, path="/", headers=None, body=None):
        self.path = path
        self.headers = headers or {}
        self._raw_body = json.dumps(body).encode("utf-8") if body is not None else b""
        if self._raw_body:
            self.headers["Content-Length"] = str(len(self._raw_body))
        self.rfile = io.BytesIO(self._raw_body)
        self.status_code = None
        self.response_data = None

    def _send_json(self, data, status_code=200, headers=None):
        self.status_code = status_code
        self.response_data = data
        return data

class TestHodDuplicateFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.token = "admin-test-token-dup"
        SESSIONS[cls.token] = {
            "id": 1,
            "username": "admin_tester",
            "role": "Administrator",
            "department": "Administration"
        }

    def test_01_all_departments_unique_hod_directory(self):
        """Verify that GET /api/hods returns exactly 1 row per active department HOD without duplicates"""
        handler = MockResponseHandler(path="/api/hods", headers={"Authorization": f"Bearer {self.token}"})
        handle_request("GET", handler)
        
        self.assertEqual(handler.status_code, 200)
        self.assertTrue(handler.response_data["success"])
        hods = handler.response_data.get("hods", [])
        
        departments_seen = set()
        for h in hods:
            dept = h["department"]
            self.assertNotIn(dept, departments_seen, f"Duplicate HOD entry found for department: {dept}")
            departments_seen.add(dept)

    def test_02_department_wise_lifecycle_and_duplicate_prevention(self):
        """Test add, duplicate rejection, update, and delete across multiple departments"""
        test_depts = [
            ("Automobile Engineering", "Dr. Ramesh Auto", "ramesh_auto@college.edu", "9811001101"),
            ("Computer Engineering", "Dr. Shankar Comp", "shankar_comp@college.edu", "9811001102"),
            ("Information Technology", "Dr. Anita IT", "anita_it@college.edu", "9811001103"),
            ("Civil Engineering", "Dr. Suresh Civil", "suresh_civil@college.edu", "9811001104"),
            ("Electrical Engineering", "Dr. Priya EE", "priya_ee@college.edu", "9811001105"),
            ("Mechanical Engineering", "Dr. Rajesh Mech", "rajesh_mech@college.edu", "9811001106")
        ]

        for dept, name, email, phone in test_depts:
            with self.subTest(department=dept):
                # 1. Clean previous test record for this department
                h_del = MockResponseHandler(path=f"/api/hods?department={dept}", headers={"Authorization": f"Bearer {self.token}"})
                handle_request("DELETE", h_del)

                # 2. Add HOD once -> 200 OK
                h_add = MockResponseHandler(path="/api/hods", headers={"Authorization": f"Bearer {self.token}"}, body={
                    "department": dept,
                    "name": name,
                    "qualification": "Ph.D.",
                    "experience": "12 Years",
                    "email": email,
                    "contact": phone
                })
                handle_request("POST", h_add)
                self.assertEqual(h_add.status_code, 200)
                self.assertTrue(h_add.response_data["success"])

                # 3. Verify exactly 1 record for this department in GET /api/hods
                h_list = MockResponseHandler(path=f"/api/hods?department={dept}", headers={"Authorization": f"Bearer {self.token}"})
                handle_request("GET", h_list)
                self.assertEqual(h_list.status_code, 200)
                matching = [h for h in h_list.response_data.get("hods", []) if h["department"] == dept]
                self.assertEqual(len(matching), 1, f"Expected exactly 1 HOD for {dept}, found {len(matching)}")
                self.assertEqual(matching[0]["name"], name)

                # 4. Attempt to add a duplicate HOD with different ID to the same department without edit mode -> must return 400
                h_dup = MockResponseHandler(path="/api/hods", headers={"Authorization": f"Bearer {self.token}"}, body={
                    "department": dept,
                    "name": "Another Person",
                    "qualification": "M.Tech",
                    "experience": "5 Years",
                    "email": f"diff_{email}",
                    "contact": "9900990099",
                    "faculty_id": f"HOD_DIFF_{dept[:2]}"
                })
                handle_request("POST", h_dup)
                self.assertEqual(h_dup.status_code, 400)
                self.assertFalse(h_dup.response_data["success"])

                # 5. Verify still exactly 1 record for this department
                h_list2 = MockResponseHandler(path=f"/api/hods?department={dept}", headers={"Authorization": f"Bearer {self.token}"})
                handle_request("GET", h_list2)
                matching2 = [h for h in h_list2.response_data.get("hods", []) if h["department"] == dept]
                self.assertEqual(len(matching2), 1)

                # 6. Edit existing HOD -> 200 OK and still 1 record
                updated_name = f"{name} (Updated)"
                h_edit = MockResponseHandler(path="/api/hods", headers={"Authorization": f"Bearer {self.token}"}, body={
                    "department": dept,
                    "name": updated_name,
                    "qualification": "Ph.D. Senior",
                    "experience": "15 Years",
                    "email": email,
                    "contact": phone,
                    "is_edit": True
                })
                handle_request("POST", h_edit)
                self.assertEqual(h_edit.status_code, 200)
                self.assertTrue(h_edit.response_data["success"])

                # 7. Verify updated name and count is still 1
                h_list3 = MockResponseHandler(path=f"/api/hods?department={dept}", headers={"Authorization": f"Bearer {self.token}"})
                handle_request("GET", h_list3)
                matching3 = [h for h in h_list3.response_data.get("hods", []) if h["department"] == dept]
                self.assertEqual(len(matching3), 1)
                self.assertEqual(matching3[0]["name"], updated_name)

if __name__ == "__main__":
    unittest.main(verbosity=2)
