import os
import sys
import unittest
import json
import time

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config.database import get_db_connection, init_db
from router import handle_request
from auth.permissions import SESSIONS
from auth.utils import verify_password, hash_password

import io

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
        if headers:
            self.response_headers = headers
        return data

class TestFirstTimeAdminSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Clean test users created during testing
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("DELETE FROM users WHERE username IN ('test_setup_admin', 'second_admin_attempt', 'admin_verify_test')")
        conn.commit()
        cursor.close()
        conn.close()

    def test_01_init_db_does_not_seed_admin(self):
        """Verify that init_db does not recreate the hardcoded admin/admin123 seed"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        # Delete any user named 'admin' if present from previous tests
        cursor.execute("DELETE FROM users WHERE username = 'admin'")
        conn.commit()
        
        # Run init_db
        init_db()
        
        # Verify 'admin' does not exist
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_row = cursor.fetchone()
        self.assertIsNone(admin_row, "Hard-coded 'admin' user should NOT be seeded by init_db")
        cursor.close()
        conn.close()

    def test_02_setup_status_endpoint(self):
        """Test GET /api/setup/status correctly reports whether setup is required"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role IN ('Administrator', 'Admin')")
        admin_count = cursor.fetchone()["count"]
        cursor.close()
        conn.close()

        handler = MockResponseHandler(path="/api/setup/status")
        handle_request("GET", handler)
        
        self.assertEqual(handler.status_code, 200)
        self.assertTrue(handler.response_data["success"])
        expected_setup_required = (admin_count == 0)
        self.assertEqual(handler.response_data["setup_required"], expected_setup_required)

    def test_03_first_time_admin_creation_and_rejection_of_subsequent_attempts(self):
        """Test creating first admin, checking password hashing, and enforcing 1-admin restriction"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        # Temporarily back up any existing administrators
        cursor.execute("SELECT id, username, password, role, name, email, department FROM users WHERE role IN ('Administrator', 'Admin')")
        existing_admins = cursor.fetchall()
        
        # Delete all administrators to simulate zero-admin first-time state
        cursor.execute("DELETE FROM users WHERE role IN ('Administrator', 'Admin')")
        conn.commit()
        
        try:
            # 1. Verify setup status is now required (0 admins)
            h_status = MockResponseHandler(path="/api/setup/status")
            handle_request("GET", h_status)
            self.assertEqual(h_status.status_code, 200)
            self.assertTrue(h_status.response_data["setup_required"])

            # 2. Test validation failures
            # Mismatched password
            h_bad_pass = MockResponseHandler(path="/api/setup/admin", body={
                "name": "Super Admin",
                "email": "superadmin@college.edu",
                "username": "test_setup_admin",
                "password": "Password123",
                "confirmPassword": "DifferentPassword"
            })
            handle_request("POST", h_bad_pass)
            self.assertEqual(h_bad_pass.status_code, 400)
            self.assertFalse(h_bad_pass.response_data["success"])

            # Invalid email format
            h_bad_email = MockResponseHandler(path="/api/setup/admin", body={
                "name": "Super Admin",
                "email": "not-an-email",
                "username": "test_setup_admin",
                "password": "Password123",
                "confirmPassword": "Password123"
            })
            handle_request("POST", h_bad_email)
            self.assertEqual(h_bad_email.status_code, 400)
            self.assertFalse(h_bad_email.response_data["success"])

            # 3. Create the first administrator
            plain_password = "SecureAdminPassword!123"
            h_create = MockResponseHandler(path="/api/setup/admin", body={
                "name": "Main System Administrator",
                "email": "mainadmin@college.edu",
                "phone": "9876543210",
                "username": "test_setup_admin",
                "password": plain_password,
                "confirmPassword": plain_password
            })
            handle_request("POST", h_create)
            self.assertEqual(h_create.status_code, 200)
            self.assertTrue(h_create.response_data["success"])

            # 4. Verify user in database
            cursor.execute("SELECT * FROM users WHERE username = 'test_setup_admin'")
            admin_user = cursor.fetchone()
            self.assertIsNotNone(admin_user)
            self.assertEqual(admin_user["role"], "Administrator")
            self.assertEqual(admin_user["name"], "Main System Administrator")
            self.assertEqual(admin_user["email"], "mainadmin@college.edu")
            self.assertEqual(admin_user["status"], "Active")
            
            # Verify password is not in plain text and verifies with verify_password
            self.assertNotEqual(admin_user["password"], plain_password)
            self.assertTrue(verify_password(admin_user["password"], plain_password))

            # 5. Verify setup status is now False (admin exists)
            h_status2 = MockResponseHandler(path="/api/setup/status")
            handle_request("GET", h_status2)
            self.assertEqual(h_status2.status_code, 200)
            self.assertFalse(h_status2.response_data["setup_required"])

            # 6. Verify subsequent attempt to POST /api/setup/admin is strictly rejected with 403
            h_subsequent = MockResponseHandler(path="/api/setup/admin", body={
                "name": "Second Rogue Admin",
                "email": "rogue@college.edu",
                "username": "second_admin_attempt",
                "password": "Password123",
                "confirmPassword": "Password123"
            })
            handle_request("POST", h_subsequent)
            self.assertEqual(h_subsequent.status_code, 403)
            self.assertFalse(h_subsequent.response_data["success"])

            # 7. Test Admin Login with the newly created account
            h_login = MockResponseHandler(path="/api/login", body={
                "username": "test_setup_admin",
                "password": plain_password,
                "role": "Administrator"
            })
            handle_request("POST", h_login)
            self.assertEqual(h_login.status_code, 200)
            self.assertTrue(h_login.response_data["success"])
            token = h_login.response_data["token"]
            self.assertIsNotNone(token)

            # 8. Test accessing Admin-protected API with new token
            h_admin_protected = MockResponseHandler(path="/api/admin/pending-users", headers={"Authorization": f"Bearer {token}"})
            handle_request("GET", h_admin_protected)
            self.assertEqual(h_admin_protected.status_code, 200)
            self.assertTrue(h_admin_protected.response_data["success"])

        finally:
            cursor.execute("DELETE FROM users WHERE username IN ('test_setup_admin', 'second_admin_attempt')")
            # Restore previous administrators if any
            for ea in existing_admins:
                cursor.execute(
                    "INSERT IGNORE INTO users (id, username, password, role, name, email, department, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')",
                    (ea["id"], ea["username"], ea["password"], ea["role"], ea["name"], ea["email"], ea["department"])
                )
            conn.commit()
            cursor.close()
            conn.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
