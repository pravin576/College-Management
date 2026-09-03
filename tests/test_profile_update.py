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
from auth.utils import hash_password

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

class TestProfileUpdate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def _req(self, method, path, body=None, token=None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        handler = MockResponseHandler(path=path, headers=headers, body=body)
        handle_request(method, handler)
        return handler.status_code, handler.response_data

    def test_admin_profile_update_and_login(self):
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True, buffered=True)
        uname = f"admin_prof_{uuid.uuid4().hex[:6]}"
        email = f"{uname}@college.edu"
        cur.execute("INSERT INTO users (username, password, role, name, email, department, status) VALUES (%s, %s, 'Administrator', 'Admin Name', %s, 'Administration', 'Active')",
                    (uname, hash_password("OldPass@123"), email))
        user_id = cur.lastrowid
        conn.commit()

        token = f"token_{uname}"
        SESSIONS[token] = {
            "id": user_id,
            "username": uname,
            "role": "Administrator",
            "department": "Administration",
            "name": "Admin Name",
            "email": email
        }

        # Update profile with new name, new email, and new password
        new_name = "Pravin Updated"
        new_email = f"new_{uname}@college.edu"
        new_pass = "BrandNewPass@999"

        status, res = self._req("POST", "/api/profile", {
            "name": new_name,
            "email": new_email,
            "password": new_pass
        }, token=token)

        self.assertEqual(status, 200, f"Profile update failed: {res}")
        self.assertTrue(res.get("success"))
        self.assertEqual(res["user"]["name"], new_name)
        self.assertEqual(res["user"]["email"], new_email)

        # Verify login succeeds with the NEW password
        status, login_res = self._req("POST", "/api/login", {
            "username": uname,
            "password": new_pass
        })
        self.assertEqual(status, 200, f"Login with updated password failed: {login_res}")

        # Clean up
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
