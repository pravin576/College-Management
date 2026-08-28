from config.database import get_db_connection
from auth.permissions import get_current_user, SESSIONS
from router import register_route

def handle_profile(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Not authenticated"}, 401)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database error"}, 500)
        
    cursor = conn.cursor(dictionary=True)
    
    # Profile update
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    phone = body.get("phone", "").strip()
    
    if not name or not email:
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": "Name and Email are required"}, 400)
        
    # Update the users table
    cursor.execute("UPDATE users SET name = %s, email = %s, phone = %s WHERE id = %s", (name, email, phone, user["id"]))
    conn.commit()
    
    # Update the specific role table (students, faculty, hods, admins)
    role = user["role"]
    if role == "Student":
        cursor.execute("UPDATE students SET name = %s, email = %s, mobile = %s WHERE id = %s", (name, email, phone, user["student_id"]))
        conn.commit()
    elif role == "Faculty":
        cursor.execute("UPDATE faculty SET name = %s, email = %s, mobile = %s WHERE id = %s", (name, email, phone, user["faculty_id"]))
        conn.commit()
    elif role == "HOD":
        cursor.execute("UPDATE hods SET name = %s, email = %s, contact = %s WHERE faculty_id = %s", (name, email, phone, user["faculty_id"]))
        conn.commit()
        
    cursor.close()
    conn.close()
    
    # Update session cache
    from auth.permissions import get_session_token
    token = get_session_token(handler_instance)
    if token and token in SESSIONS:
        SESSIONS[token]["name"] = name
        SESSIONS[token]["email"] = email
        
    handler_instance._send_json({"success": True, "message": "Profile updated successfully"})

register_route("POST", "/api/profile", handle_profile)
