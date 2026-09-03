from config.database import get_db_connection
from auth.permissions import get_current_user, SESSIONS, get_session_token
from auth.utils import hash_password, verify_password
from router import register_route

def handle_change_password(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Authentication required"}, 401)

    curr_pass = (body.get("currentPassword") or body.get("current_password") or body.get("tempPassword") or "").strip()
    new_pass = (body.get("newPassword") or body.get("new_password") or "").strip()
    confirm_pass = (body.get("confirmPassword") or body.get("confirm_password") or "").strip()

    if not curr_pass or not new_pass or not confirm_pass:
        return handler_instance._send_json({"success": False, "message": "Current password, new password, and confirmation are required"}, 400)

    if new_pass != confirm_pass:
        return handler_instance._send_json({"success": False, "message": "New password and confirm password do not match"}, 400)

    if curr_pass == new_pass:
        return handler_instance._send_json({"success": False, "message": "New password must be different from your current/temporary password"}, 400)

    if len(new_pass) < 6:
        return handler_instance._send_json({"success": False, "message": "Password must be at least 6 characters long"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'Database connection error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, password, username, name, role, department, student_id, faculty_id, email, status FROM users WHERE id = %s", (user["id"],))
        db_user = cursor.fetchone()
        if not db_user:
            return handler_instance._send_json({"success": False, "message": "User account not found"}, 404)

        if not verify_password(db_user["password"], curr_pass):
            return handler_instance._send_json({"success": False, "message": "The current/temporary password you entered is incorrect"}, 400)

        hashed = hash_password(new_pass)
        cursor.execute(
            "UPDATE users SET password = %s, must_change_password = 0, temp_password_created_at = NULL WHERE id = %s",
            (hashed, user["id"])
        )
        conn.commit()

        # Update in-memory session
        token = get_session_token(handler_instance)
        if token and token in SESSIONS:
            SESSIONS[token]["must_change_password"] = False

        user_data = {
            "id": db_user["id"],
            "username": db_user["username"],
            "name": db_user["name"],
            "role": db_user["role"],
            "department": db_user.get("department", ""),
            "student_id": db_user.get("student_id", "") or (db_user["username"] if db_user["role"] == "Student" else ""),
            "faculty_id": db_user.get("faculty_id", "") or (db_user["username"] if db_user["role"] in ["Faculty", "HOD"] else ""),
            "email": db_user["email"],
            "status": db_user.get("status", "Active"),
            "must_change_password": False
        }

        return handler_instance._send_json({
            "success": True,
            "message": "Password updated successfully! You can now proceed to your dashboard.",
            "user": user_data,
            "must_change_password": False
        })
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/auth/first-login-change-password', handle_change_password)
register_route('POST', '/api/auth/change-password', handle_change_password)
register_route('POST', '/api/user/change-password', handle_change_password)
