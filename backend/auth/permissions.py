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

def require_role(allowed_roles):
    def decorator(func):
        def wrapper(handler_instance, query_params, body):
            user = get_current_user(handler_instance)
            if not user:
                return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)
            if user["role"] not in allowed_roles and "Administrator" not in allowed_roles:
                return handler_instance._send_json({"success": False, "message": "Forbidden"}, 403)
            return func(handler_instance, query_params, body)
        return wrapper
    return decorator
