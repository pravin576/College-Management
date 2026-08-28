import time
from config.database import get_db_connection
from auth.utils import hash_password
from router import register_route

def check_duplicate(cursor, mobile, email, username, student_id=None, faculty_id=None):
    if username:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return True, f"Username '{username}' is already registered!"
    if email:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return True, f"Email '{email}' is already registered!"
    if mobile:
        cursor.execute("SELECT id FROM users WHERE mobile = %s", (mobile,))
        if cursor.fetchone():
            return True, f"Mobile '{mobile}' is already registered!"
    if student_id:
        cursor.execute("SELECT id FROM students WHERE id = %s", (student_id,))
        if cursor.fetchone():
            return True, f"Student ID '{student_id}' is already registered!"
    if faculty_id:
        cursor.execute("SELECT id FROM faculty WHERE id = %s", (faculty_id,))
        if cursor.fetchone():
            return True, f"Faculty ID '{faculty_id}' is already registered!"
    return False, ""

def handle_register(handler_instance, query_params, body):
    role = body.get("role", "Student").strip()
    if role == "Admin":
        role = "Administrator"
        
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    mobile = body.get("mobile", "").strip() or body.get("phone", "").strip() or body.get("contact", "").strip()
    department = body.get("department", "Computer Science").strip()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    confirm_password = body.get("confirmPassword", "").strip()

    if not name or not email or not username or not password:
        return handler_instance._send_json({"success": False, "message": "All required fields (Name, Email, Username, Password) must be provided!"}, 400)
    
    if password != confirm_password:
        return handler_instance._send_json({"success": False, "message": "Password and Confirm Password do not match!"}, 400)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database error"}, 500)
        
    cursor = conn.cursor(dictionary=True)
    
    student_id = body.get("studentId", "").strip() if role == "Student" else None
    faculty_id = body.get("facultyId", "").strip() if role in ["Faculty", "HOD"] else None
    
    is_dup, dup_msg = check_duplicate(cursor, mobile, email, username, student_id, faculty_id)
    if is_dup:
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": dup_msg}, 400)

    hashed_pass = hash_password(password)
    
    status = "Active" if role == "Student" else "Pending"
    if role == "Administrator":
        # Only existing admin can create admin, or first user setup
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'Administrator'")
        count = cursor.fetchone()['count']
        if count > 0:
            # Need to be logged in as Admin to create another Admin
            from auth.permissions import get_current_user
            user = get_current_user(handler_instance)
            if not user or user["role"] not in ["Administrator", "Admin"]:
                cursor.close()
                conn.close()
                return handler_instance._send_json({"success": False, "message": "Only Administrators can create Admin accounts."}, 403)
        status = "Active"

    try:
        if role == "Student":
            if not student_id:
                student_id = f"STU_{int(time.time() * 1000) % 100000}"
            roll_number = body.get("rollNumber", "").strip() or f"R{int(time.time()) % 10000}"
            gender = body.get("gender", "Male").strip()
            dob = body.get("dob", "2000-01-01").strip()
            year = body.get("year", "First Year").strip()
            semester = body.get("semester", "Semester 1").strip()
            division = body.get("division", "A").strip()
            admission_year = body.get("admissionYear", "2026").strip()
            address = body.get("address", "").strip()

            cursor.execute(
                """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Active')""",
                (student_id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address)
            )

        elif role == "Faculty":
            if not faculty_id:
                faculty_id = f"FAC_{int(time.time() * 1000) % 100000}"
            designation = body.get("designation", "Assistant Professor").strip()
            experience = body.get("experience", "0 Years").strip()
            cursor.execute(
                """INSERT INTO faculty (id, name, department, designation, email, mobile, experience, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')""",
                (faculty_id, name, department, designation, email, mobile, experience)
            )

        elif role == "HOD":
            if not faculty_id:
                faculty_id = f"HOD_{int(time.time() * 1000) % 100000}"
            qualification = body.get("qualification", "Ph.D.").strip()
            experience = body.get("experience", "10 Years").strip()
            cursor.execute(
                """INSERT INTO hods (department, name, qualification, experience, email, contact, faculty_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (department, name, qualification, experience, email, mobile, faculty_id)
            )
            
        cursor.execute(
            """INSERT INTO users (username, password, role, name, email, department, student_id, faculty_id, mobile, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (username, hashed_pass, role, name, email, department, student_id, faculty_id, mobile, status)
        )
        
        conn.commit()
    except Exception as e:
        print("REGISTER DB ERROR:", str(e))
        import traceback
        traceback.print_exc()
        conn.rollback()
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": f"Database error: {str(e)}"}, 500)
        
    cursor.close()
    conn.close()
    
    msg = "Account created successfully!"
    if status == "Pending":
        msg += " Please wait for authorization."
        
    user_data = {
        "id": cursor.lastrowid if hasattr(cursor, 'lastrowid') else None,
        "username": username,
        "name": name,
        "role": role,
        "email": email
    }
        
    handler_instance._send_json({"success": True, "message": msg, "user": user_data})

register_route("POST", "/api/register", handle_register)
