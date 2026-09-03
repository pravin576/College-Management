import urllib.parse
import json
from auth.permissions import get_current_user

ROUTES = {
    "GET": {},
    "POST": {},
    "PUT": {},
    "DELETE": {}
}

def register_route(method, path, handler):
    ROUTES[method][path] = handler

def handle_request(method, handler_instance):
    parsed_url = urllib.parse.urlparse(handler_instance.path)
    path = parsed_url.path
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    # Read raw body once for POST/PUT/DELETE
    raw_body = b""
    body = {}
    content_length = int(handler_instance.headers.get("Content-Length", 0))
    if content_length > 0:
        raw_body = handler_instance.rfile.read(content_length)
        handler_instance._raw_body = raw_body
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            body = {}
    else:
        handler_instance._raw_body = b""

    # Exact match first
    if method in ROUTES and path in ROUTES[method]:
        return ROUTES[method][path](handler_instance, query_params, body)
        
    # Parameterized / prefix wildcard routes
    if method in ROUTES:
        for route_path, func in ROUTES[method].items():
            if route_path.endswith("*"):
                base_path = route_path[:-1]
                if path.startswith(base_path):
                    return func(handler_instance, query_params, body)
    
    handler_instance._send_json({"success": False, "message": f"Endpoint '{path}' not found for method {method}"}, 404)

# Import routes to register them
import auth.login
import auth.register
import auth.forgot_password
import auth.password_controller
import auth.profile

# Modules
import admin.admin_controller
import attendance.attendance_controller
import contact.contact_controller
import core.core_controller
import departments.departments_controller
import documents.documents_controller
import faculty.faculty_controller
import fees.fees_controller
import hod.hod_controller
import notices.notices_controller
import results.results_controller
import students.students_controller
import timetable.timetable_controller
