import uuid
from config.database import get_db_connection
from auth.permissions import SESSIONS, get_current_user
from auth.utils import verify_password
from router import register_route

def handle_login(handler_instance, query_params, body):
    username_or_email = body.get("username", "")
    password = body.get("password", "")
    
    if not username_or_email or not password:
        return handler_instance._send_json({"success": False, "message": "Username/Email and Password are required"}, 400)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database error"}, 500)
        
    cursor = conn.cursor(dictionary=True)
    
    if "@" in username_or_email:
        cursor.execute("SELECT * FROM users WHERE email = %s", (username_or_email,))
    else:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username_or_email,))
        
    user = cursor.fetchone()
    
    if not user:
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": "Invalid credentials"}, 401)
        
    if not verify_password(user['password'], password):
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": "Invalid credentials"}, 401)
        
    if user.get("status") == "Pending":
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": "Account pending authorization"}, 403)
        
    session_token = str(uuid.uuid4())
    user_data = {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "department": user["department"],
        "student_id": user["student_id"],
        "faculty_id": user["faculty_id"],
        "email": user["email"]
    }
    
    SESSIONS[session_token] = user_data
    
    cursor.close()
    conn.close()
    
    headers = {
        "Set-Cookie": f"session_token={session_token}; Path=/; HttpOnly; SameSite=Strict"
    }
    
    handler_instance._send_json({
        "success": True, 
        "token": session_token,
        "user": user_data,
        "message": "Login successful"
    }, headers=headers)

def handle_logout(handler_instance, query_params, body):
    from auth.permissions import get_session_token
    token = get_session_token(handler_instance)
    if token and token in SESSIONS:
        del SESSIONS[token]
        
    headers = {
        "Set-Cookie": "session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
    }
    handler_instance._send_json({"success": True, "message": "Logged out successfully"}, headers=headers)

def handle_me(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if user:
        handler_instance._send_json({"success": True, "user": user})
    else:
        handler_instance._send_json({"success": False, "message": "Not authenticated"}, 401)

register_route("POST", "/api/login", handle_login)
register_route("POST", "/api/logout", handle_logout)
register_route("GET", "/api/auth/me", handle_me)
