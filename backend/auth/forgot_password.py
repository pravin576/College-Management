from config.database import get_db_connection
from auth.utils import hash_password
from router import register_route
import re

def _clean_phone(phone_str):
    if not phone_str:
        return ""
    return re.sub(r"[^\d]", "", str(phone_str))

def _mask_email(email):
    if not email or "@" not in email:
        return "****"
    parts = email.split("@", 1)
    uname = parts[0]
    domain = parts[1]
    if len(uname) <= 2:
        masked_uname = uname[0] + "****"
    else:
        masked_uname = uname[:2] + "****"
    return f"{masked_uname}@{domain}"

def _mask_mobile(mobile):
    cleaned = _clean_phone(mobile)
    if len(cleaned) >= 4:
        return "******" + cleaned[-4:]
    elif mobile:
        return "****"
    return ""

def handle_forgot_password(handler_instance, query_params, body):
    action = body.get("action", "verify").strip()
    role = body.get("role", "").strip()
    if role == "Admin":
        role = "Administrator"

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database connection error"}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if action == "verify":
            identifier = body.get("identifier", "").strip()
            if not identifier:
                return handler_instance._send_json({"success": False, "message": "Username, Email, Phone, or ID is required for verification!"}, 400)

            # 1. First search in users table directly
            query = """
                SELECT * FROM users 
                WHERE (LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) OR mobile = %s OR student_id = %s OR faculty_id = %s OR LOWER(name) = LOWER(%s))
            """
            params = [identifier, identifier, identifier, identifier, identifier, identifier]

            if role and role != "All":
                query += " AND role = %s"
                params.append(role)

            cursor.execute(query, tuple(params))
            user = cursor.fetchone()

            # 2. Fallback: Search students table if looking for Student or role is not specified
            if not user and (not role or role == "Student" or role == "All"):
                cursor.execute("SELECT id, email, mobile FROM students WHERE roll_number = %s OR id = %s OR LOWER(email) = LOWER(%s) OR mobile = %s OR LOWER(name) = LOWER(%s)",
                               (identifier, identifier, identifier, identifier, identifier))
                st = cursor.fetchone()
                if st:
                    cursor.execute("SELECT * FROM users WHERE student_id = %s OR LOWER(email) = LOWER(%s) OR mobile = %s",
                                   (st["id"], st["email"], st["mobile"]))
                    user = cursor.fetchone()

            # 3. Fallback: Search faculty table
            if not user and (not role or role in ["Faculty", "All"]):
                cursor.execute("SELECT id, email, mobile FROM faculty WHERE id = %s OR LOWER(email) = LOWER(%s) OR mobile = %s OR LOWER(name) = LOWER(%s)",
                               (identifier, identifier, identifier, identifier))
                fac = cursor.fetchone()
                if fac:
                    cursor.execute("SELECT * FROM users WHERE faculty_id = %s OR LOWER(email) = LOWER(%s) OR mobile = %s",
                                   (fac["id"], fac["email"], fac["mobile"]))
                    user = cursor.fetchone()

            # 4. Fallback: Search hods table
            if not user and (not role or role in ["HOD", "All"]):
                cursor.execute("SELECT faculty_id, email, contact FROM hods WHERE faculty_id = %s OR LOWER(email) = LOWER(%s) OR contact = %s OR LOWER(name) = LOWER(%s)",
                               (identifier, identifier, identifier, identifier))
                hod = cursor.fetchone()
                if hod:
                    cursor.execute("SELECT * FROM users WHERE faculty_id = %s OR LOWER(email) = LOWER(%s) OR mobile = %s",
                                   (hod.get("faculty_id"), hod.get("email"), hod.get("contact")))
                    user = cursor.fetchone()

            if not user:
                return handler_instance._send_json({
                    "success": False, 
                    "message": f"No account found matching '{identifier}' for role '{role if role else 'Any'}'. Please check your details and selected role."
                }, 404)

            # Check if linked student/faculty has email/mobile if missing in users record
            email = user.get("email") or ""
            mobile = user.get("mobile") or ""

            if not email or not mobile:
                if user.get("role") == "Student" and user.get("student_id"):
                    cursor.execute("SELECT email, mobile FROM students WHERE id = %s", (user["student_id"],))
                    st_record = cursor.fetchone()
                    if st_record:
                        email = email or st_record.get("email") or ""
                        mobile = mobile or st_record.get("mobile") or ""
                elif user.get("role") in ["Faculty", "HOD"] and user.get("faculty_id"):
                    cursor.execute("SELECT email, mobile FROM faculty WHERE id = %s", (user["faculty_id"],))
                    fac_record = cursor.fetchone()
                    if fac_record:
                        email = email or fac_record.get("email") or ""
                        mobile = mobile or fac_record.get("mobile") or ""

            return handler_instance._send_json({
                "success": True,
                "message": "Account verified successfully!",
                "user": {
                    "username": user.get("username"),
                    "name": user.get("name"),
                    "role": user.get("role"),
                    "department": user.get("department", ""),
                    "maskedEmail": _mask_email(email),
                    "maskedMobile": _mask_mobile(mobile)
                }
            })

        elif action == "reset":
            username = body.get("username", "").strip()
            new_password = (body.get("newPassword") or body.get("new_password") or "").strip()
            confirm_password = (body.get("confirmPassword") or body.get("confirm_password") or "").strip()
            verification_value = (body.get("verificationInput") or body.get("verificationValue") or body.get("verification_value") or "").strip()

            if not username:
                return handler_instance._send_json({"success": False, "message": "Username is required for password reset."}, 400)
            if not new_password:
                return handler_instance._send_json({"success": False, "message": "New password is required."}, 400)
            if not verification_value:
                return handler_instance._send_json({"success": False, "message": "Verification value (Email, Mobile, or Date of Birth) is required."}, 400)
            if new_password != confirm_password:
                return handler_instance._send_json({"success": False, "message": "Passwords do not match."}, 400)
            if len(new_password) < 6:
                return handler_instance._send_json({"success": False, "message": "Password must be at least 6 characters long."}, 400)

            # Retrieve user across username, email, student_id, faculty_id, mobile, or name
            cursor.execute("""
                SELECT * FROM users 
                WHERE LOWER(username) = LOWER(%s) 
                   OR LOWER(email) = LOWER(%s) 
                   OR student_id = %s 
                   OR faculty_id = %s 
                   OR mobile = %s 
                   OR LOWER(name) = LOWER(%s)
            """, (username, username, username, username, username, username))
            user = cursor.fetchone()

            # Fallback if username was roll_number or student/faculty ID
            if not user:
                cursor.execute("SELECT id, email, mobile FROM students WHERE roll_number = %s OR id = %s OR LOWER(name) = LOWER(%s)", (username, username, username))
                st = cursor.fetchone()
                if st:
                    cursor.execute("SELECT * FROM users WHERE student_id = %s OR LOWER(email) = LOWER(%s) OR mobile = %s", (st["id"], st["email"], st["mobile"]))
                    user = cursor.fetchone()
            if not user:
                cursor.execute("SELECT id, email, mobile FROM faculty WHERE id = %s OR LOWER(name) = LOWER(%s)", (username, username))
                fac = cursor.fetchone()
                if fac:
                    cursor.execute("SELECT * FROM users WHERE faculty_id = %s OR LOWER(email) = LOWER(%s) OR mobile = %s", (fac["id"], fac["email"], fac["mobile"]))
                    user = cursor.fetchone()
            if not user:
                cursor.execute("SELECT faculty_id, email, contact FROM hods WHERE faculty_id = %s OR LOWER(name) = LOWER(%s)", (username, username))
                hod = cursor.fetchone()
                if hod:
                    cursor.execute("SELECT * FROM users WHERE faculty_id = %s OR LOWER(email) = LOWER(%s) OR mobile = %s", (hod.get("faculty_id"), hod.get("email"), hod.get("contact")))
                    user = cursor.fetchone()

            if not user:
                return handler_instance._send_json({"success": False, "message": "User account not found."}, 404)

            # Multi-attribute security verification
            is_verified = False
            ver_clean = verification_value.strip().lower()
            ver_phone = _clean_phone(verification_value)

            # Check direct user attributes
            if user.get("email") and user["email"].strip().lower() == ver_clean:
                is_verified = True
            if user.get("mobile") and ver_phone and _clean_phone(user["mobile"]) == ver_phone:
                is_verified = True
            if user.get("student_id") and user["student_id"].strip().lower() == ver_clean:
                is_verified = True
            if user.get("faculty_id") and user["faculty_id"].strip().lower() == ver_clean:
                is_verified = True

            # Check linked student table
            if not is_verified and user.get("role") == "Student":
                student_id = user.get("student_id")
                if student_id:
                    cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
                else:
                    cursor.execute("SELECT * FROM students WHERE LOWER(email) = LOWER(%s) OR roll_number = %s", (user.get("email", ""), username))
                student = cursor.fetchone()
                if student:
                    if student.get("email") and student["email"].strip().lower() == ver_clean:
                        is_verified = True
                    elif student.get("mobile") and ver_phone and _clean_phone(student["mobile"]) == ver_phone:
                        is_verified = True
                    elif student.get("roll_number") and student["roll_number"].strip().lower() == ver_clean:
                        is_verified = True
                    elif student.get("dob"):
                        dob_str = str(student["dob"])
                        # Support YYYY-MM-DD or DD-MM-YYYY or DD/MM/YYYY
                        if dob_str == verification_value:
                            is_verified = True
                        elif "-" in dob_str:
                            parts = dob_str.split("-") # [YYYY, MM, DD]
                            if len(parts) == 3:
                                dmy_dash = f"{parts[2]}-{parts[1]}-{parts[0]}"
                                dmy_slash = f"{parts[2]}/{parts[1]}/{parts[0]}"
                                if verification_value in [dmy_dash, dmy_slash]:
                                    is_verified = True

            # Check linked faculty table
            if not is_verified and user.get("role") in ["Faculty", "HOD"]:
                faculty_id = user.get("faculty_id")
                if faculty_id:
                    cursor.execute("SELECT * FROM faculty WHERE id = %s", (faculty_id,))
                    fac = cursor.fetchone()
                    if fac:
                        if fac.get("email") and fac["email"].strip().lower() == ver_clean:
                            is_verified = True
                        elif fac.get("mobile") and ver_phone and _clean_phone(fac["mobile"]) == ver_phone:
                            is_verified = True

            # Check linked hods table
            if not is_verified and user.get("role") == "HOD":
                faculty_id = user.get("faculty_id")
                if faculty_id:
                    cursor.execute("SELECT * FROM hods WHERE faculty_id = %s", (faculty_id,))
                    hod = cursor.fetchone()
                    if hod:
                        if hod.get("email") and hod["email"].strip().lower() == ver_clean:
                            is_verified = True
                        elif hod.get("contact") and ver_phone and _clean_phone(hod["contact"]) == ver_phone:
                            is_verified = True

            if not is_verified:
                return handler_instance._send_json({
                    "success": False, 
                    "message": "Verification failed. The entered details (Email, Mobile, or Date of Birth) do not match our registered records for this account."
                }, 403)

            # Update password
            hashed_pass = hash_password(new_password)
            cursor.execute(
                "UPDATE users SET password = %s, must_change_password = 0, temp_password_created_at = NULL WHERE id = %s",
                (hashed_pass, user["id"])
            )
            conn.commit()

            return handler_instance._send_json({
                "success": True, 
                "message": "Password reset successfully! You can now log in with your new password."
            })

        else:
            return handler_instance._send_json({"success": False, "message": "Invalid action specified."}, 400)

    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        print("[FORGOT_PASSWORD EXCEPTION]:")
        traceback.print_exc()
        return handler_instance._send_json({"success": False, "message": f"Server error: {str(e)}"}, 500)
    finally:
        cursor.close()
        conn.close()

register_route("POST", "/api/forgot-password", handle_forgot_password)
