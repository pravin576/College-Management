from config.database import get_db_connection
from auth.permissions import get_current_user, SESSIONS, get_session_token
from auth.utils import hash_password
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
    new_password = (body.get("password", "") or "").strip()
    
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

register_route("POST", "/api/profile", handle_profile)
