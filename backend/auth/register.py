import time
from config.database import get_db_connection
from auth.utils import hash_password
from auth.permissions import get_current_user, is_admin
from router import register_route

def check_duplicate(cursor, mobile, email, username, student_id=None, faculty_id=None, roll_number=None, department=None):
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
    if roll_number and department:
        cursor.execute("SELECT id FROM students WHERE roll_number = %s AND department = %s", (roll_number, department))
        if cursor.fetchone():
            return True, f"Roll Number '{roll_number}' already exists in department '{department}'!"
    if faculty_id:
        cursor.execute("SELECT id FROM faculty WHERE id = %s", (faculty_id,))
        if cursor.fetchone():
            return True, f"Faculty ID '{faculty_id}' is already registered!"
    return False, ""

def handle_register(handler_instance, query_params, body):
    role = body.get("role", "Student").strip()
    if role in ["Admin", "Administrator"]:
        role = "Administrator"
    elif role not in ["Student", "Faculty", "HOD"]:
        return handler_instance._send_json({"success": False, "message": f"Invalid role '{role}' specified."}, 400)
        
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    mobile = (body.get("mobile", "") or body.get("phone", "") or body.get("contact", "")).strip()
    department = body.get("department", "Computer Engineering").strip()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    confirm_password = body.get("confirmPassword", "").strip()

    if not name or not email or not username or not password:
        return handler_instance._send_json({"success": False, "message": "All required fields (Name, Email, Username, Password) must be provided!"}, 400)
    
    if password != confirm_password:
        return handler_instance._send_json({"success": False, "message": "Password and Confirm Password do not match!"}, 400)
        
    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database connection error"}, 500)
        
    cursor = conn.cursor(dictionary=True)
    
    student_id = body.get("studentId", "").strip() if role == "Student" else None
    faculty_id = (body.get("facultyId", "") or body.get("faculty_id", "")).strip() if role in ["Faculty", "HOD"] else None
    roll_number = body.get("rollNumber", "").strip() if role == "Student" else None

    # Check for first admin setup vs existing admin permission
    if role == "Administrator":
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role IN ('Administrator', 'Admin')")
        admin_count = cursor.fetchone()['count']
        if admin_count > 0:
            user = get_current_user(handler_instance)
            if not user or not is_admin(user):
                cursor.close()
                conn.close()
                return handler_instance._send_json({
                    "success": False, 
                    "message": "Only authenticated Administrators can create new Administrator accounts."
                }, 403)
        status = "Active"
    elif role in ["Faculty", "HOD"]:
        status = "Pending"
    else: # Student
        status = "Active"

    # For HOD, ensure department doesn't already have an assigned HOD
    if role == "HOD":
        cursor.execute("SELECT id, name FROM hods WHERE department = %s", (department,))
        existing_hod = cursor.fetchone()
        if existing_hod:
            cursor.close()
            conn.close()
            return handler_instance._send_json({
                "success": False, 
                "message": f"Department '{department}' already has an assigned HOD ({existing_hod['name']})."
            }, 400)

    is_dup, dup_msg = check_duplicate(cursor, mobile, email, username, student_id, faculty_id, roll_number, department)
    if is_dup:
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": dup_msg}, 400)

    hashed_pass = hash_password(password)
    
    try:
        if role == "Student":
            if not student_id:
                student_id = f"STU_{int(time.time() * 1000) % 100000}"
            if not roll_number:
                roll_number = f"R{int(time.time()) % 10000}"
            gender = body.get("gender", "Male").strip()
            dob = body.get("dob", "2005-01-01").strip()
            year = body.get("year", "First Year").strip()
            semester = body.get("semester", "Semester 1").strip()
            division = body.get("division", "A").strip()
            admission_year = body.get("admissionYear", "2026").strip()
            address = body.get("address", "College Campus").strip()

            cursor.execute(
                """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (student_id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
            )

        elif role == "Faculty":
            if not faculty_id:
                faculty_id = f"FAC_{int(time.time() * 1000) % 100000}"
            designation = body.get("designation", "Assistant Professor").strip()
            experience = body.get("experience", "1 Year").strip()
            cursor.execute(
                """INSERT INTO faculty (id, name, department, designation, email, mobile, experience, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (faculty_id, name, department, designation, email, mobile, experience, status)
            )

        elif role == "HOD":
            if not faculty_id:
                faculty_id = f"HOD_{int(time.time() * 1000) % 100000}"
            qualification = body.get("qualification", "Ph.D.").strip()
            experience = body.get("experience", "10 Years").strip()
            cursor.execute(
                """INSERT INTO hods (department, name, qualification, experience, email, contact, faculty_id, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (department, name, qualification, experience, email, mobile, faculty_id, status)
            )
            
        cursor.execute(
            """INSERT INTO users (username, password, role, name, email, department, student_id, faculty_id, mobile, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (username, hashed_pass, role, name, email, department, student_id, faculty_id, mobile, status)
        )
        
        conn.commit()
    except Exception as e:
        print("REGISTER DB ERROR:", str(e))
        conn.rollback()
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": f"Database error: {str(e)}"}, 500)
        
    cursor.close()
    conn.close()
    
    if status == "Pending":
        msg = f"{role} registration submitted successfully! Your account is pending Administrator authorization before you can log in."
    else:
        msg = "Account created successfully! You can now log in."
        
    user_data = {
        "username": username,
        "name": name,
        "role": role,
        "email": email,
        "status": status
    }
        
    return handler_instance._send_json({"success": True, "message": msg, "user": user_data})

register_route("POST", "/api/register", handle_register)
