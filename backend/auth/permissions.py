import urllib.parse
from config.database import get_db_connection

SESSIONS = {}

def get_session_token(handler_instance):
    auth_header = handler_instance.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    
    x_token = handler_instance.headers.get("X-Session-Token")
    if x_token:
        return x_token.strip()

    cookie_header = handler_instance.headers.get("Cookie")
    if cookie_header:
        cookies = urllib.parse.parse_qs(cookie_header.replace("; ", "&"))
        if "session_token" in cookies:
            return cookies["session_token"][0].strip()
    
    return None

def get_current_user(handler_instance):
    token = get_session_token(handler_instance)
    if token and token in SESSIONS:
        return SESSIONS[token]
    return None

def is_admin(user):
    if not user:
        return False
    return user.get("role") in ["Administrator", "Admin"]

def is_hod(user):
    if not user:
        return False
    return user.get("role") == "HOD"

def is_faculty(user):
    if not user:
        return False
    return user.get("role") == "Faculty"

def is_student(user):
    if not user:
        return False
    return user.get("role") == "Student"

def require_role(allowed_roles):
    """
    Decorator to enforce backend role-based access control.
    Fixed: current_user.role MUST exist in allowed_roles.
    """
    def decorator(func):
        def wrapper(handler_instance, query_params, body):
            user = get_current_user(handler_instance)
            if not user:
                return handler_instance._send_json({"success": False, "message": "Unauthorized: Authentication required"}, 401)
            
            user_role = user.get("role", "")
            user_roles = [user_role]
            if user_role == "Admin":
                user_roles.append("Administrator")
            elif user_role == "Administrator":
                user_roles.append("Admin")
            
            has_permission = any(r in allowed_roles for r in user_roles)
            if not has_permission:
                return handler_instance._send_json({"success": False, "message": "Forbidden: Insufficient permissions"}, 403)
            
            return func(handler_instance, query_params, body)
        return wrapper
    return decorator
