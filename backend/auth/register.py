import time
import os
import re
from config.database import get_db_connection
from auth.utils import hash_password
from auth.permissions import get_current_user, is_admin
from router import register_route

def check_duplicate(cursor, mobile, email, username, student_id=None, faculty_id=None, roll_number=None, department=None, role="Student"):
    if username:
        cursor.execute("SELECT id FROM users WHERE LOWER(TRIM(username)) = LOWER(TRIM(%s))", (username,))
        if cursor.fetchall():
            return True, f"Username '{username}' is already registered! If your account was created by Admin/HOD, please log in directly."
            
    if email:
        cursor.execute("SELECT id FROM users WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s))", (email,))
        if cursor.fetchall():
            return True, f"Email '{email}' is already registered! Please log in directly."
        if role == "HOD":
            cursor.execute("SELECT id FROM hods WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s))", (email,))
            if cursor.fetchall():
                return True, f"Email '{email}' is already registered!"
                
    if mobile:
        cursor.execute("SELECT id FROM users WHERE TRIM(mobile) = TRIM(%s)", (mobile,))
        if cursor.fetchall():
            return True, f"Mobile number '{mobile}' is already registered!"
        if role == "HOD":
            cursor.execute("SELECT id FROM hods WHERE TRIM(contact) = TRIM(%s)", (mobile,))
            if cursor.fetchall():
                return True, f"Mobile number '{mobile}' is already registered!"
                
    if student_id:
        cursor.execute("SELECT id FROM students WHERE id = %s", (student_id,))
        if cursor.fetchall():
            return True, f"This Enrollment Number '{student_id}' is already registered and an account has been created by the Administration. Please log in directly."
        cursor.execute("SELECT id FROM users WHERE student_id = %s OR username = %s", (student_id, student_id))
        if cursor.fetchall():
            return True, f"This Enrollment Number '{student_id}' is already registered. Please log in directly."
            
    if roll_number and department:
        cursor.execute("SELECT id FROM students WHERE roll_number = %s AND LOWER(TRIM(department)) = LOWER(TRIM(%s))", (roll_number, department))
        if cursor.fetchall():
            return True, f"Roll Number '{roll_number}' already exists in department '{department}'!"
            
    if faculty_id:
        cursor.execute("SELECT id FROM faculty WHERE id = %s", (faculty_id,))
        if cursor.fetchall():
            return True, f"Faculty ID '{faculty_id}' is already registered and an account has been created by the Administration. Please log in directly."
        cursor.execute("SELECT id FROM users WHERE faculty_id = %s OR username = %s", (faculty_id, faculty_id))
        if cursor.fetchall():
            return True, f"Faculty ID '{faculty_id}' is already registered. Please log in directly."
        cursor.execute("SELECT id FROM hods WHERE faculty_id = %s", (faculty_id,))
        if cursor.fetchall():
            return True, f"HOD/Faculty ID '{faculty_id}' is already registered!"
            
    return False, ""

def handle_register(handler_instance, query_params, body):
    role = body.get("role", "Student").strip()
    if role in ["Admin", "Administrator"]:
        role = "Administrator"
    elif role not in ["Student", "Faculty", "HOD"]:
        return handler_instance._send_json({"success": False, "message": f"Invalid role '{role}' specified."}, 400)
        
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    mobile = ((body.get("mobile") or body.get("phone") or body.get("contact") or "")).strip()
    department = " ".join(((body.get("department") or "Computer Engineering")).strip().split())
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    confirm_password = (body.get("confirmPassword") or "").strip()

    # Field validations
    if not name:
        return handler_instance._send_json({"success": False, "message": "Full Name is required!"}, 400)
    if not email:
        return handler_instance._send_json({"success": False, "message": "Email address is required!"}, 400)
    if "@" not in email or "." not in email:
        return handler_instance._send_json({"success": False, "message": "Please enter a valid email address!"}, 400)
    if not username:
        return handler_instance._send_json({"success": False, "message": "Username is required!"}, 400)
    if not password:
        return handler_instance._send_json({"success": False, "message": "Password is required!"}, 400)
    if len(password) < 6:
        return handler_instance._send_json({"success": False, "message": "Password must be at least 6 characters long!"}, 400)
    if password != confirm_password:
        return handler_instance._send_json({"success": False, "message": "Password and Confirm Password do not match!"}, 400)
    if not department:
        return handler_instance._send_json({"success": False, "message": "Department is required!"}, 400)

    # Role specific validations
    qualification = (body.get("qualification") or "Ph.D.").strip()
    experience = (body.get("experience") or "5 Years").strip()
    if not mobile:
        mobile = "9876543210"

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({
            "success": False, 
            "message": "Database connection error. MySQL server is not reachable. Please check MySQL service."
        }, 503)
        
    cursor = conn.cursor(dictionary=True, buffered=True)
    
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

    is_dup, dup_msg = check_duplicate(cursor, mobile, email, username, student_id, faculty_id, roll_number, department, role)
    if is_dup:
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": dup_msg}, 400)

    # Strictly enforce 1 HOD per department across BOTH users and hods tables
    if role == "HOD":
        cursor.execute("SELECT id, name FROM hods WHERE LOWER(TRIM(department)) = LOWER(TRIM(%s))", (department,))
        existing_hod_tbl = cursor.fetchone()
        
        cursor.execute("SELECT id, name FROM users WHERE role = 'HOD' AND LOWER(TRIM(department)) = LOWER(TRIM(%s))", (department,))
        existing_hod_usr = cursor.fetchone()

        if existing_hod_tbl or existing_hod_usr:
            cursor.close()
            conn.close()
            return handler_instance._send_json({
                "success": False, 
                "message": f"This department ({department}) already has an HOD."
            }, 400)

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
            
            # Atomic insert into hods
            cursor.execute(
                """INSERT INTO hods (department, name, qualification, experience, email, contact, faculty_id, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (department, name, qualification, experience, email, mobile, faculty_id, status)
            )
            
        # Atomic insert into users (must_change_password = 0 for self-registration)
        cursor.execute(
            """INSERT INTO users (username, password, role, name, email, department, student_id, faculty_id, mobile, created_at, must_change_password, temp_password_created_at, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, NULL, %s)""",
            (username, hashed_pass, role, name, email, department, student_id, faculty_id, mobile, time.strftime('%Y-%m-%d %H:%M:%S'), status)
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        err_str = str(e)
        print(f"[REGISTER ERROR] Database exception during {role} registration: {err_str}")
        if "Duplicate entry" in err_str:
            if "username" in err_str:
                msg = f"Username '{username}' is already registered!"
            elif "email" in err_str:
                msg = f"Email '{email}' is already registered!"
            elif "department" in err_str:
                msg = f"This department ({department}) already has an HOD."
            elif "contact" in err_str or "mobile" in err_str:
                msg = f"Mobile number '{mobile}' is already registered!"
            else:
                msg = "A record with these details already exists."
            return handler_instance._send_json({"success": False, "message": msg}, 400)
            
        return handler_instance._send_json({"success": False, "message": f"Registration failed due to a database error: {err_str}"}, 400)
        
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
        "department": department,
        "status": status
    }
        
    return handler_instance._send_json({"success": True, "message": msg, "user": user_data})

register_route("POST", "/api/register", handle_register)

