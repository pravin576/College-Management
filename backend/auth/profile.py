from config.database import get_db_connection
from auth.permissions import get_current_user, SESSIONS, get_session_token
from router import register_route

def handle_profile(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Not authenticated"}, 401)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database error"}, 500)
        
    cursor = conn.cursor(dictionary=True)
    
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    mobile = (body.get("mobile", "") or body.get("phone", "") or body.get("contact", "")).strip()
    
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
        cursor.execute("UPDATE users SET name = %s, email = %s, mobile = %s WHERE id = %s", (name, email, mobile, user["id"]))
        
        # Update the role-specific table
        role = user.get("role")
        if role == "Student" and user.get("student_id"):
            cursor.execute("UPDATE students SET name = %s, email = %s, mobile = %s WHERE id = %s", (name, email, mobile, user["student_id"]))
        elif role == "Faculty" and user.get("faculty_id"):
            cursor.execute("UPDATE faculty SET name = %s, email = %s, mobile = %s WHERE id = %s", (name, email, mobile, user["faculty_id"]))
        elif role == "HOD":
            if user.get("faculty_id"):
                cursor.execute("UPDATE hods SET name = %s, email = %s, contact = %s WHERE faculty_id = %s", (name, email, mobile, user["faculty_id"]))
            elif user.get("department"):
                cursor.execute("UPDATE hods SET name = %s, email = %s, contact = %s WHERE department = %s", (name, email, mobile, user["department"]))
            
        conn.commit()
        
        # Update session cache
        token = get_session_token(handler_instance)
        if token and token in SESSIONS:
            SESSIONS[token]["name"] = name
            SESSIONS[token]["email"] = email
            
        return handler_instance._send_json({"success": True, "message": "Profile updated successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": f"Profile update failed: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route("POST", "/api/profile", handle_profile)
