import uuid
from config.database import get_db_connection
from auth.permissions import SESSIONS, get_current_user, get_session_token
from auth.utils import verify_password
from router import register_route

def handle_login(handler_instance, query_params, body):
    username_or_email = (body.get("username", "") or body.get("email", "")).strip()
    password = body.get("password", "").strip()
    requested_role = (body.get("role", "") or "All").strip()
    
    if not username_or_email or not password:
        return handler_instance._send_json({"success": False, "message": "Username/Email and Password are required"}, 400)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database connection error"}, 500)
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Find user by username, email, enrollment number (student_id), or faculty_id
        cursor.execute(
            """SELECT * FROM users 
               WHERE username = %s OR email = %s OR student_id = %s OR faculty_id = %s""",
            (username_or_email, username_or_email, username_or_email, username_or_email)
        )
        user = cursor.fetchone()
        
        if not user:
            return handler_instance._send_json({"success": False, "message": "Invalid credentials"}, 401)
            
        # Role validation if specified in the login request (e.g. from role dropdown)
        if requested_role and requested_role not in ["All", "All Roles"]:
            req_role_norm = "Administrator" if requested_role.lower() in ["admin", "administrator"] else requested_role.capitalize()
            user_role_norm = "Administrator" if user["role"].lower() in ["admin", "administrator"] else user["role"].capitalize()
            if req_role_norm != user_role_norm:
                return handler_instance._send_json({"success": False, "message": f"Selected role '{requested_role}' does not match this user account"}, 401)

        if not verify_password(user['password'], password):
            return handler_instance._send_json({"success": False, "message": "Invalid credentials"}, 401)
            
        # Verify user status
        status = (user.get("status") or "Active").strip().capitalize()
        if status == "Pending":
            return handler_instance._send_json({
                "success": False, 
                "message": "Account pending authorization. Please wait for Administrator approval before logging in."
            }, 403)
        elif status == "Rejected":
            return handler_instance._send_json({
                "success": False, 
                "message": "Account registration has been rejected by the Administrator."
            }, 403)
        elif status == "Inactive":
            return handler_instance._send_json({
                "success": False, 
                "message": "Account is deactivated. Please contact the Administrator."
            }, 403)
        elif status != "Active":
            return handler_instance._send_json({
                "success": False, 
                "message": "Account is not active."
            }, 403)
            
        session_token = str(uuid.uuid4())
        must_change_pwd = bool(user.get("must_change_password"))
        user_data = {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "department": user.get("department", ""),
            "student_id": user.get("student_id", "") or (user["username"] if user["role"] == "Student" else ""),
            "faculty_id": user.get("faculty_id", "") or (user["username"] if user["role"] in ["Faculty", "HOD"] else ""),
            "email": user["email"],
            "status": user.get("status", "Active"),
            "must_change_password": must_change_pwd
        }
        
        SESSIONS[session_token] = user_data
        
        headers = {
            "Set-Cookie": f"session_token={session_token}; Path=/; HttpOnly; SameSite=Strict"
        }
        
        return handler_instance._send_json({
            "success": True, 
            "token": session_token,
            "user": user_data,
            "must_change_password": must_change_pwd,
            "message": "Login successful"
        }, headers=headers)
        
    except Exception as e:
        print("LOGIN ERROR:", e)
        return handler_instance._send_json({"success": False, "message": f"Server error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

def handle_logout(handler_instance, query_params, body):
    token = get_session_token(handler_instance)
    if token and token in SESSIONS:
        del SESSIONS[token]
        
    headers = {
        "Set-Cookie": "session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Strict"
    }
    handler_instance._send_json({"success": True, "message": "Logged out successfully"}, headers=headers)

def handle_me(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if user:
        handler_instance._send_json({"success": True, "user": user, "must_change_password": bool(user.get("must_change_password"))})
    else:
        handler_instance._send_json({"success": False, "message": "Not authenticated"}, 401)

register_route("POST", "/api/login", handle_login)
register_route("POST", "/api/logout", handle_logout)
register_route("GET", "/api/auth/me", handle_me)
