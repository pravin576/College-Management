import re
import time
from config.database import get_db_connection
from auth.utils import hash_password
from router import register_route

def handle_get_setup_status(handler_instance, query_params, body):
    """
    Check if first-time Administrator setup is required.
    Returns setup_required = True if zero Administrator accounts exist in the system.
    """
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database connection error"}, 500)
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role IN ('Administrator', 'Admin')")
        row = cursor.fetchone()
        admin_count = row["count"] if row else 0

        setup_required = (admin_count == 0)
        return handler_instance._send_json({
            "success": True,
            "setup_required": setup_required,
            "admin_count": admin_count,
            "message": "First-time Administrator setup required." if setup_required else "System is configured."
        })
    except Exception as e:
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

def handle_post_setup_admin(handler_instance, query_params, body):
    """
    Create the first Administrator account during initial setup.
    Enforces that this endpoint only works when ZERO Administrator accounts exist.
    """
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database connection error"}, 500)
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        # 1. Strict backend security check: Allow creation ONLY when 0 Administrator accounts exist
        cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role IN ('Administrator', 'Admin')")
        row = cursor.fetchone()
        admin_count = row["count"] if row else 0

        if admin_count > 0:
            return handler_instance._send_json({
                "success": False,
                "message": "First-time setup is disabled. An Administrator account already exists. Please log in using existing Administrator credentials."
            }, 403)

        # 2. Extract and validate fields
        name = (body.get("name") or "").strip()
        email = (body.get("email") or "").strip()
        username = (body.get("username") or "").strip()
        mobile = (body.get("mobile") or body.get("phone") or "").strip()
        password = (body.get("password") or "").strip()
        confirm_password = (body.get("confirmPassword") or body.get("confirm_password") or "").strip()

        if not name:
            return handler_instance._send_json({"success": False, "message": "Administrator Full Name is required."}, 400)
        if not email:
            return handler_instance._send_json({"success": False, "message": "Official Email is required."}, 400)
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return handler_instance._send_json({"success": False, "message": "Please enter a valid email address format."}, 400)
        if not username:
            return handler_instance._send_json({"success": False, "message": "Username is required."}, 400)
        if len(username) < 3:
            return handler_instance._send_json({"success": False, "message": "Username must be at least 3 characters long."}, 400)
        if not password:
            return handler_instance._send_json({"success": False, "message": "Password is required."}, 400)
        if len(password) < 6:
            return handler_instance._send_json({"success": False, "message": "Password must be at least 6 characters long."}, 400)
        if password != confirm_password:
            return handler_instance._send_json({"success": False, "message": "Password and Confirm Password do not match."}, 400)

        # 3. Check for existing username or email conflict in users table
        cursor.execute("SELECT id, username, email FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)", (username, email))
        conflict = cursor.fetchone()
        if conflict:
            if conflict["username"].lower() == username.lower():
                return handler_instance._send_json({"success": False, "message": f"Username '{username}' is already in use."}, 400)
            if conflict["email"].lower() == email.lower():
                return handler_instance._send_json({"success": False, "message": f"Email '{email}' is already registered."}, 400)

        # 4. Hash password and insert first Administrator
        hashed_pass = hash_password(password)
        now_str = time.strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute(
            """INSERT INTO users (username, password, role, name, email, department, mobile, created_at, must_change_password, temp_password_created_at, status)
               VALUES (%s, %s, 'Administrator', %s, %s, 'Administration', %s, %s, 0, NULL, 'Active')""",
            (username, hashed_pass, name, email, mobile if mobile else None, now_str)
        )
        conn.commit()

        return handler_instance._send_json({
            "success": True,
            "message": "First-Time Administrator account created successfully! You can now sign in to your dashboard.",
            "user": {
                "username": username,
                "name": name,
                "role": "Administrator",
                "email": email
            }
        })
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        traceback.print_exc()
        return handler_instance._send_json({"success": False, "message": f"Setup error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

# Register Setup Routes
register_route("GET", "/api/setup/status", handle_get_setup_status)
register_route("POST", "/api/setup/admin", handle_post_setup_admin)
