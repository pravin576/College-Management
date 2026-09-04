from config.database import get_db_connection
from auth.permissions import get_current_user, SESSIONS, get_session_token
from auth.utils import hash_password, verify_password
from router import register_route

def handle_profile(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Not authenticated"}, 401)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database error"}, 500)
        
    cursor = conn.cursor(dictionary=True)
    
    # If GET request or empty update payload, return current profile
    name = (body.get("name") or "").strip() if body else ""
    email = (body.get("email") or "").strip() if body else ""
    mobile = (body.get("mobile", "") or body.get("phone", "") or body.get("contact", "")).strip() if body else ""
    new_password = (body.get("password", "") or "").strip() if body else ""

    if not name and not email:
        try:
            cursor.execute("SELECT id, username, name, role, department, student_id, faculty_id, email, mobile, status FROM users WHERE id = %s", (user["id"],))
            current_user = cursor.fetchone()
            return handler_instance._send_json({
                "success": True,
                "user": current_user or user,
                "profile": current_user or user
            })
        finally:
            cursor.close()
            conn.close()

    if not name or not email:
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": "Name and Email are required"}, 400)
        
    try:
        # Check if email is being changed and if it already belongs to another user
        cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user["id"]))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return handler_instance._send_json({"success": False, "message": f"Email '{email}' is already in use by another account."}, 400)

        # Update the users table
        if new_password:
            hashed = hash_password(new_password)
            if mobile:
                cursor.execute("UPDATE users SET name = %s, email = %s, mobile = %s, password = %s, must_change_password = 0 WHERE id = %s", (name, email, mobile, hashed, user["id"]))
            else:
                cursor.execute("UPDATE users SET name = %s, email = %s, password = %s, must_change_password = 0 WHERE id = %s", (name, email, hashed, user["id"]))
        else:
            if mobile:
                cursor.execute("UPDATE users SET name = %s, email = %s, mobile = %s WHERE id = %s", (name, email, mobile, user["id"]))
            else:
                cursor.execute("UPDATE users SET name = %s, email = %s WHERE id = %s", (name, email, user["id"]))
        
        # Update the role-specific table
        role = user.get("role")
        if role == "Student" and user.get("student_id"):
            if mobile:
                cursor.execute("UPDATE students SET name = %s, email = %s, mobile = %s WHERE id = %s", (name, email, mobile, user["student_id"]))
            else:
                cursor.execute("UPDATE students SET name = %s, email = %s WHERE id = %s", (name, email, user["student_id"]))
        elif role == "Faculty" and user.get("faculty_id"):
            if mobile:
                cursor.execute("UPDATE faculty SET name = %s, email = %s, mobile = %s WHERE id = %s", (name, email, mobile, user["faculty_id"]))
            else:
                cursor.execute("UPDATE faculty SET name = %s, email = %s WHERE id = %s", (name, email, user["faculty_id"]))
        elif role == "HOD":
            if user.get("faculty_id"):
                if mobile:
                    cursor.execute("UPDATE hods SET name = %s, email = %s, contact = %s WHERE faculty_id = %s", (name, email, mobile, user["faculty_id"]))
                else:
                    cursor.execute("UPDATE hods SET name = %s, email = %s WHERE faculty_id = %s", (name, email, user["faculty_id"]))
            elif user.get("department"):
                if mobile:
                    cursor.execute("UPDATE hods SET name = %s, email = %s, contact = %s WHERE department = %s", (name, email, mobile, user["department"]))
                else:
                    cursor.execute("UPDATE hods SET name = %s, email = %s WHERE department = %s", (name, email, user["department"]))
            
        conn.commit()

        cursor.execute("SELECT id, username, name, role, department, student_id, faculty_id, email, mobile, status FROM users WHERE id = %s", (user["id"],))
        updated_user = cursor.fetchone()
        
        # Update session cache
        token = get_session_token(handler_instance)
        if token and token in SESSIONS and updated_user:
            SESSIONS[token].update(updated_user)
            
        return handler_instance._send_json({
            "success": True, 
            "message": "Profile updated successfully!",
            "user": updated_user or user
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Profile update failed: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

def handle_change_username(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Authentication required"}, 401)

    new_username = (body.get("new_username") or body.get("newUsername") or body.get("username") or "").strip()
    current_password = (body.get("current_password") or body.get("currentPassword") or body.get("password") or "").strip()

    if not new_username:
        return handler_instance._send_json({"success": False, "message": "New username cannot be empty."}, 400)

    if len(new_username) < 3 or len(new_username) > 50:
        return handler_instance._send_json({"success": False, "message": "Username must be between 3 and 50 characters."}, 400)

    if not current_password:
        return handler_instance._send_json({"success": False, "message": "Current password is required to change username."}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database connection error."}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, username, password, role FROM users WHERE id = %s", (user["id"],))
        db_user = cursor.fetchone()
        if not db_user:
            return handler_instance._send_json({"success": False, "message": "User account not found."}, 404)

        if not verify_password(db_user["password"], current_password):
            return handler_instance._send_json({"success": False, "message": "Current password is incorrect."}, 400)

        if new_username == db_user["username"]:
            return handler_instance._send_json({"success": False, "message": "New username must be different from your current username."}, 400)

        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (new_username, user["id"]))
        if cursor.fetchone():
            return handler_instance._send_json({"success": False, "message": "Username already exists."}, 400)

        cursor.execute("UPDATE users SET username = %s WHERE id = %s", (new_username, user["id"]))
        conn.commit()

        token = get_session_token(handler_instance)
        if token and token in SESSIONS:
            SESSIONS[token]["username"] = new_username

        return handler_instance._send_json({
            "success": True,
            "message": "Username changed successfully.",
            "username": new_username
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Failed to change username: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

def handle_change_password(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Authentication required"}, 401)

    current_password = (body.get("current_password") or body.get("currentPassword") or "").strip()
    new_password = (body.get("new_password") or body.get("newPassword") or "").strip()
    confirm_password = (body.get("confirm_password") or body.get("confirmPassword") or "").strip()

    if not current_password or not new_password or not confirm_password:
        return handler_instance._send_json({"success": False, "message": "Current password, new password, and confirmation are required."}, 400)

    if new_password != confirm_password:
        return handler_instance._send_json({"success": False, "message": "New passwords do not match."}, 400)

    if len(new_password) < 6:
        return handler_instance._send_json({"success": False, "message": "Password must be at least 6 characters long."}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database connection error."}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, username, password, role FROM users WHERE id = %s", (user["id"],))
        db_user = cursor.fetchone()
        if not db_user:
            return handler_instance._send_json({"success": False, "message": "User account not found."}, 404)

        if not verify_password(db_user["password"], current_password):
            return handler_instance._send_json({"success": False, "message": "Current password is incorrect."}, 400)

        hashed = hash_password(new_password)
        cursor.execute(
            "UPDATE users SET password = %s, must_change_password = 0, temp_password_created_at = NULL WHERE id = %s",
            (hashed, user["id"])
        )
        conn.commit()

        token = get_session_token(handler_instance)
        if token and token in SESSIONS:
            SESSIONS[token]["must_change_password"] = 0

        return handler_instance._send_json({
            "success": True,
            "message": "Password changed successfully."
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Failed to change password: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route("GET", "/api/profile", handle_profile)
register_route("POST", "/api/profile", handle_profile)
register_route("PUT", "/api/profile", handle_profile)
register_route("PUT", "/api/profile/username", handle_change_username)
register_route("POST", "/api/profile/username", handle_change_username)
register_route("POST", "/api/profile/change-username", handle_change_username)

register_route("PUT", "/api/profile/password", handle_change_password)
register_route("POST", "/api/profile/password", handle_change_password)
register_route("POST", "/api/profile/change-password", handle_change_password)
