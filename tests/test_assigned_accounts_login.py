import os
import sys
import unittest
import json
import io
import uuid

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
        self.wfile = io.BytesIO()
        self.status_code = None
        self.response_data = None
        self._response_headers = {}

    def send_response(self, code):
        self.status_code = code

    def send_header(self, keyword, value):
        self._response_headers[keyword] = value

    def end_headers(self):
        pass

    def _send_json(self, data, status_code=200, headers=None):
        self.status_code = status_code
        self.response_data = data
        return data

class TestAssignedAccountsLogin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.admin_token = "admin-session-token-test-assign"
        SESSIONS[cls.admin_token] = {
            "id": 1,
            "username": "super_admin",
            "role": "Administrator",
            "department": "Administration"
        }

    def _req(self, method, path, body=None, token=None):
        headers = {}
        t = token or self.admin_token
        if t:
            headers["Authorization"] = f"Bearer {t}"
        handler = MockResponseHandler(path=path, headers=headers, body=body)
        handle_request(method, handler)
        return handler.status_code, handler.response_data

    def test_01_admin_assigns_student_and_student_logs_in(self):
        stu_id = f"STU_AUTO_{uuid.uuid4().hex[:6]}"
        roll_no = f"R_{uuid.uuid4().hex[:4]}"
        stu_email = f"{stu_id.lower()}@college.edu"
        stu_pass = "StudentPass@123"

        # Admin creates student with custom password
        status, res = self._req("POST", "/api/students", {
            "id": stu_id,
            "rollNumber": roll_no,
            "name": "Auto Created Student",
            "email": stu_email,
            "mobile": "9876543210",
            "gender": "Male",
            "dob": "2002-05-10",
            "department": "Computer Engineering",
            "year": "First Year",
            "semester": "Semester 1",
            "division": "A",
            "password": stu_pass
        })
        self.assertEqual(status, 200, f"Student creation failed: {res}")

        # 1. Login with Enrollment Number
        status, login_res = self._req("POST", "/api/login", {
            "username": stu_id,
            "password": stu_pass
        }, token="")
        self.assertEqual(status, 200, f"Login with Enrollment Number failed: {login_res}")
        self.assertEqual(login_res["user"]["role"], "Student")

        # 2. Login with Email
        status, login_res2 = self._req("POST", "/api/login", {
            "username": stu_email,
            "password": stu_pass
        }, token="")
        self.assertEqual(status, 200, f"Login with Email failed: {login_res2}")

        # 3. Login with Roll Number
        status, login_res3 = self._req("POST", "/api/login", {
            "username": roll_no,
            "password": stu_pass
        }, token="")
        self.assertEqual(status, 200, f"Login with Roll Number failed: {login_res3}")

        # 4. Admin edits student with a NEW password
        new_pass = "NewStudentPass@456"
        status, edit_res = self._req("POST", "/api/students", {
            "id": stu_id,
            "rollNumber": roll_no,
            "name": "Auto Created Student (Updated)",
            "email": stu_email,
            "mobile": "9876543210",
            "department": "Computer Engineering",
            "password": new_pass,
            "is_edit": True
        })
        self.assertEqual(status, 200)

        # Login with NEW password
        status, login_res4 = self._req("POST", "/api/login", {
            "username": stu_id,
            "password": new_pass
        }, token="")
        self.assertEqual(status, 200, f"Login with updated password failed: {login_res4}")

        # Clean up
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM students WHERE id = %s", (stu_id,))
        cur.execute("DELETE FROM users WHERE student_id = %s OR username = %s", (stu_id, stu_id))
        conn.commit()
        cur.close()
        conn.close()

    def test_02_admin_assigns_faculty_and_faculty_logs_in(self):
        fac_id = f"FAC_AUTO_{uuid.uuid4().hex[:6]}"
        fac_email = f"{fac_id.lower()}@college.edu"
        fac_pass = "FacultyPass@123"

        # Admin creates faculty
        status, res = self._req("POST", "/api/faculty", {
            "id": fac_id,
            "name": "Dr. Assigned Faculty",
            "department": "Information Technology",
            "designation": "Associate Professor",
            "email": fac_email,
            "mobile": "9876500000",
            "experience": "8 Years",
            "status": "Active",
            "password": fac_pass
        })
        self.assertEqual(status, 200, f"Faculty creation failed: {res}")

        # 1. Login with Faculty ID
        status, login_res = self._req("POST", "/api/login", {
            "username": fac_id,
            "password": fac_pass
        }, token="")
        self.assertEqual(status, 200, f"Login with Faculty ID failed: {login_res}")
        self.assertEqual(login_res["user"]["role"], "Faculty")

        # 2. Login with Email
        status, login_res2 = self._req("POST", "/api/login", {
            "username": fac_email,
            "password": fac_pass
        }, token="")
        self.assertEqual(status, 200, f"Login with Faculty Email failed: {login_res2}")

        # Clean up
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM faculty WHERE id = %s", (fac_id,))
        cur.execute("DELETE FROM users WHERE faculty_id = %s OR username = %s", (fac_id, fac_id))
        conn.commit()
        cur.close()
        conn.close()

    def test_03_admin_assigns_hod_and_hod_logs_in(self):
        dept = "Automobile Engineering"
        hod_email = f"hod_auto_{uuid.uuid4().hex[:4]}@college.edu"
        hod_pass = "HodPass@123"

        # Admin assigns HOD
        status, res = self._req("POST", "/api/hods", {
            "department": dept,
            "name": "Dr. Auto Assigned HOD",
            "qualification": "Ph.D. Automobile",
            "experience": "14 Years",
            "email": hod_email,
            "contact": "9876599999",
            "password": hod_pass
        })
        self.assertEqual(status, 200, f"HOD assignment failed: {res}")

        # 1. Login with HOD Email
        status, login_res = self._req("POST", "/api/login", {
            "username": hod_email,
            "password": hod_pass
        }, token="")
        self.assertEqual(status, 200, f"Login with HOD Email failed: {login_res}")
        self.assertEqual(login_res["user"]["role"], "HOD")
        self.assertEqual(login_res["user"]["department"], dept)

        # 2. Admin edits HOD with new password
        new_hod_pass = "NewHodPass@456"
        status, edit_res = self._req("POST", "/api/hods", {
            "department": dept,
            "name": "Dr. Auto Assigned HOD (Updated)",
            "qualification": "Ph.D. Automobile",
            "experience": "15 Years",
            "email": hod_email,
            "contact": "9876599999",
            "password": new_hod_pass,
            "is_edit": True
        })
        self.assertEqual(status, 200)

        # Login with NEW HOD password
        status, login_res2 = self._req("POST", "/api/login", {
            "username": hod_email,
            "password": new_hod_pass
        }, token="")
        self.assertEqual(status, 200, f"Login with new HOD password failed: {login_res2}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
