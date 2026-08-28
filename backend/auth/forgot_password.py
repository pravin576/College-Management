from config.database import get_db_connection
from auth.utils import hash_password
from router import register_route

def handle_forgot_password(handler_instance, query_params, body):
    action = body.get("action", "verify").strip()
    role = body.get("role", "").strip()
    if role == "Admin":
        role = "Administrator"

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({"success": False, "message": "Database error"}, 500)
    cursor = conn.cursor(dictionary=True)

    if action == "verify":
        identifier = body.get("identifier", "").strip()
        if not identifier:
            cursor.close()
            conn.close()
            return handler_instance._send_json({"success": False, "message": "Username, Email, Phone, or ID is required for verification!"}, 400)

        query = "SELECT * FROM users WHERE (username = %s OR email = %s OR mobile = %s OR student_id = %s OR faculty_id = %s)"
        params = [identifier, identifier, identifier, identifier, identifier]

        if role and role != "All":
            query += " AND role = %s"
            params.append(role)

        cursor.execute(query, tuple(params))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            return handler_instance._send_json({"success": False, "message": f"No account found matching '{identifier}' for role '{role if role else 'Any'}'. Please check your details and selected role."}, 404)

        email = user.get("email") or ""
        mobile = user.get("mobile") or ""

        masked_email = ""
        if "@" in email:
            parts = email.split("@", 1)
            masked_email = (parts[0][:2] + "****" if len(parts[0]) > 2 else parts[0] + "****") + "@" + parts[1]
        elif email:
            masked_email = "****"

        masked_mobile = ""
        if len(mobile) >= 4:
            masked_mobile = "******" + mobile[-4:]
        elif mobile:
            masked_mobile = "****"

        cursor.close()
        conn.close()
        return handler_instance._send_json({
            "success": True,
            "message": "Account verified successfully!",
            "user": {
                "username": user.get("username"),
                "name": user.get("name"),
                "role": user.get("role"),
                "department": user.get("department", ""),
                "maskedEmail": masked_email,
                "maskedMobile": masked_mobile
            }
        })

    elif action == "reset":
        username = body.get("username", "").strip()
        new_password = body.get("newPassword", "").strip()
        confirm_password = body.get("confirmPassword", "").strip()
        
        # Verify via DOB for students or Mobile for Faculty/HOD/Admin based on frontend form?
        # The frontend sends: verificationValue (which is DOB or Mobile/Email depending on role)
        # We'll just verify the new passwords match and reset it for the username. 
        # (In a real app, we'd verify the OTP or DOB/Mobile, but let's implement the basic reset)
        verification_value = body.get("verificationValue", "").strip()

        if not username or not new_password:
            cursor.close()
            conn.close()
            return handler_instance._send_json({"success": False, "message": "Missing username or new password"}, 400)

        if new_password != confirm_password:
            cursor.close()
            conn.close()
            return handler_instance._send_json({"success": False, "message": "Passwords do not match"}, 400)

        # Validate verification value
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return handler_instance._send_json({"success": False, "message": "User not found"}, 404)

        is_verified = False
        if user["role"] == "Student":
            # Check DOB from students table
            if user["student_id"]:
                cursor.execute("SELECT dob FROM students WHERE id = %s", (user["student_id"],))
                student = cursor.fetchone()
                if student and str(student["dob"]) == verification_value:
                    is_verified = True
        else:
            # Check mobile or email
            if user["mobile"] == verification_value or user["email"] == verification_value:
                is_verified = True

        if not is_verified:
            cursor.close()
            conn.close()
            return handler_instance._send_json({"success": False, "message": "Verification failed. The provided details (DOB/Mobile/Email) do not match our records."}, 403)

        hashed_pass = hash_password(new_password)
        cursor.execute("UPDATE users SET password = %s WHERE username = %s", (hashed_pass, username))
        conn.commit()
        
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": True, "message": "Password reset successfully! You can now log in."})

    else:
        cursor.close()
        conn.close()
        return handler_instance._send_json({"success": False, "message": "Invalid action"}, 400)

register_route("POST", "/api/forgot-password", handle_forgot_password)
