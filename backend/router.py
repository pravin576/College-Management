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
    
    # Read body for POST/PUT
    body = {}
    if method in ["POST", "PUT"]:
        content_length = int(handler_instance.headers.get("Content-Length", 0))
        if content_length > 0:
            post_data = handler_instance.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode("utf-8"))
            except Exception:
                body = {}

    # Exact match first
    if path in ROUTES[method]:
        return ROUTES[method][path](handler_instance, query_params, body)
        
    # Check for parameterized routes (like /api/students/:id)
    # Simple prefix matching for now since the original app used `startswith` or query params mostly
    for route_path, func in ROUTES[method].items():
        if route_path.endswith("*"):
            base_path = route_path[:-1]
            if path.startswith(base_path):
                return func(handler_instance, query_params, body)
    
    handler_instance._send_json({"success": False, "message": "Endpoint not found"}, 404)

# Import routes to register them
import auth.login
import auth.register
import auth.forgot_password
import auth.profile

# Generated modules
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


