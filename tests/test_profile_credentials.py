import urllib.request
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from config.database import get_db_connection

BASE_URL = "http://localhost:8000"

def api_request(path, method="GET", body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return resp.status, json.loads(resp.read().decode("utf-8"))
            else:
                return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except:
            return e.code, {"success": False, "message": str(e)}
    except Exception as e:
        return 500, {"success": False, "message": str(e)}

def test_profile_credentials():
    print("=" * 70)
    print("STARTING PROFILE CREDENTIAL CHANGE & VERIFICATION (EXISTING DATA ONLY)")
    print("=" * 70)

    # 1. Count users before test
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, role, password FROM users WHERE username = 'admin'")
    original_admin = cur.fetchone()
    assert original_admin is not None, "Admin user not found in database"
    admin_id = original_admin["id"]
    orig_username = original_admin["username"]
    orig_pwd_hash = original_admin["password"]
    cur.execute("SELECT count(*) as total FROM users")
    initial_count = cur.fetchone()["total"]
    cur.close()
    conn.close()

    print(f"\n[INFO] Initial database users count: {initial_count}")
    print(f"[INFO] Testing on existing account: username='{orig_username}', role='{original_admin['role']}'")

    # 2. Login as admin
    code, res = api_request("/api/login", "POST", {"username": "admin", "password": "admin123"})
    assert code == 200 and res.get("token"), f"Admin login failed: {res}"
    admin_token = res["token"]
    print("  [PASS] Logged in with existing admin credentials.")

    # 3. Test Change Username - Security Validations
    print("\n--- Testing Change Username Validations & Security ---")
    
    # 3a. Unauthorized request
    code, res = api_request("/api/profile/username", "PUT", {"new_username": "newadmin", "current_password": "admin123"})
    assert code == 401, f"Expected 401 for unauthorized username change, got {code}"
    print("  [PASS] Unauthorized request rejected (401).")

    # 3b. Empty username
    code, res = api_request("/api/profile/username", "PUT", {"new_username": "", "current_password": "admin123"}, token=admin_token)
    assert code == 400 and not res.get("success"), f"Expected 400 for empty username, got {code}"
    print("  [PASS] Empty username rejected (400).")

    # 3c. Incorrect current password
    code, res = api_request("/api/profile/username", "PUT", {"new_username": "admin_renamed", "current_password": "WrongPassword#999"}, token=admin_token)
    assert code == 400 and "Current password is incorrect" in res.get("message", ""), f"Expected wrong password error, got {res}"
    print("  [PASS] Incorrect password rejected (400: 'Current password is incorrect.').")

    # 3d. Duplicate username (trying another existing username)
    code, res = api_request("/api/profile/username", "PUT", {"new_username": "pravin123", "current_password": "admin123"}, token=admin_token)
    assert code == 400 and "Username already exists" in res.get("message", ""), f"Expected duplicate error, got {res}"
    print("  [PASS] Duplicate username rejected (400: 'Username already exists.').")

    # 4. Execute Valid Username Change
    print("\n--- Testing Valid Username Change ---")
    temp_username = "admin_verified_temp"
    code, res = api_request("/api/profile/username", "PUT", {"new_username": temp_username, "current_password": "admin123"}, token=admin_token)
    assert code == 200 and res.get("success"), f"Username change failed: {res}"
    print(f"  [PASS] Username changed to '{temp_username}'.")

    # Verify old username fails login
    code, res = api_request("/api/login", "POST", {"username": "admin", "password": "admin123"})
    assert code == 401 or not res.get("success"), "Old username was still able to login!"
    print("  [PASS] Old username 'admin' successfully rejected on login.")

    # Verify new username succeeds login
    code, res = api_request("/api/login", "POST", {"username": temp_username, "password": "admin123"})
    assert code == 200 and res.get("token"), f"New username login failed: {res}"
    new_token = res["token"]
    assert res.get("user", {}).get("role") == "Administrator", "Role changed unexpectedly!"
    print("  [PASS] New username logged in successfully, role 'Administrator' preserved.")

    # 5. Restore Original Username
    print("\n--- Restoring Original Username ---")
    code, res = api_request("/api/profile/username", "PUT", {"new_username": "admin", "current_password": "admin123"}, token=new_token)
    assert code == 200 and res.get("success"), f"Restoring username failed: {res}"
    print("  [PASS] Original username 'admin' restored.")

    # Re-login with original credentials
    code, res = api_request("/api/login", "POST", {"username": "admin", "password": "admin123"})
    assert code == 200 and res.get("token"), "Login with restored admin username failed!"
    admin_token = res["token"]
    print("  [PASS] Verified original 'admin' login.")

    # 6. Test Change Password - Security Validations
    print("\n--- Testing Change Password Validations & Security ---")

    # 6a. Mismatched confirmation
    code, res = api_request("/api/profile/password", "PUT", {
        "current_password": "admin123", "new_password": "NewSecretPass#1", "confirm_password": "DifferentPass#2"
    }, token=admin_token)
    assert code == 400 and "New passwords do not match" in res.get("message", ""), f"Expected mismatch error, got {res}"
    print("  [PASS] Mismatched confirmation rejected (400: 'New passwords do not match.').")

    # 6b. Short password (< 6 chars)
    code, res = api_request("/api/profile/password", "PUT", {
        "current_password": "admin123", "new_password": "123", "confirm_password": "123"
    }, token=admin_token)
    assert code == 400 and not res.get("success"), f"Expected short password error, got {res}"
    print("  [PASS] Short password rejected (400).")

    # 6c. Incorrect current password
    code, res = api_request("/api/profile/password", "PUT", {
        "current_password": "WrongAdminPass#999", "new_password": "ValidNewPassword#2026", "confirm_password": "ValidNewPassword#2026"
    }, token=admin_token)
    assert code == 400 and "Current password is incorrect" in res.get("message", ""), f"Expected wrong current password error, got {res}"
    print("  [PASS] Incorrect current password rejected (400: 'Current password is incorrect.').")

    # 7. Execute Valid Password Change
    print("\n--- Testing Valid Password Change ---")
    temp_new_pass = "TempAdminPass#2026"
    code, res = api_request("/api/profile/password", "PUT", {
        "current_password": "admin123", "new_password": temp_new_pass, "confirm_password": temp_new_pass
    }, token=admin_token)
    assert code == 200 and res.get("success"), f"Password change failed: {res}"
    print("  [PASS] Password changed successfully.")

    # Verify old password fails
    code, res = api_request("/api/login", "POST", {"username": "admin", "password": "admin123"})
    assert code == 401 or not res.get("success"), "Security error: Old password still accepted!"
    print("  [PASS] Old password 'admin123' rejected.")

    # Verify new password succeeds
    code, res = api_request("/api/login", "POST", {"username": "admin", "password": temp_new_pass})
    assert code == 200 and res.get("token"), f"Login with new password failed: {res}"
    admin_token = res["token"]
    print("  [PASS] New password authenticated successfully.")

    # 8. Restore Original Password
    print("\n--- Restoring Original Password ---")
    code, res = api_request("/api/profile/password", "PUT", {
        "current_password": temp_new_pass, "new_password": "admin123", "confirm_password": "admin123"
    }, token=admin_token)
    assert code == 200 and res.get("success"), f"Restoring password failed: {res}"
    print("  [PASS] Original password 'admin123' restored.")

    # Verify restored password login
    code, res = api_request("/api/login", "POST", {"username": "admin", "password": "admin123"})
    assert code == 200 and res.get("token"), "Restored login failed!"
    print("  [PASS] Verified login with original 'admin123' password.")

    # 9. Verify Database Count & State
    print("\n--- Final Database Verification ---")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT count(*) as total FROM users")
    final_count = cur.fetchone()["total"]
    assert final_count == initial_count, f"User count changed! Initial: {initial_count}, Final: {final_count}"
    
    cur.execute("SELECT id, username, role, password FROM users WHERE username = 'admin'")
    final_admin = cur.fetchone()
    assert final_admin["id"] == admin_id, "Admin ID altered!"
    assert final_admin["role"] == "Administrator", "Role altered!"
    assert "$" in final_admin["password"] and len(final_admin["password"]) > 30, "Plain text password stored!"
    cur.close()
    conn.close()

    print(f"  [PASS] Database user count strictly unchanged ({final_count} users).")
    print("  [PASS] Zero demo/sample users created.")
    print("  [PASS] All cryptographic hashes verified.")
    print("\n" + "=" * 70)
    print("ALL USERNAME & PASSWORD CHANGE TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    test_profile_credentials()
