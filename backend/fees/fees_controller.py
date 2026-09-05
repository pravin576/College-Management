import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user, is_admin, is_hod, is_faculty, is_student

def handle_get_fees_receipt(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')
    student_id = user.get('student_id') or user.get('username')

    target_id = query_params.get("id", [None])[0]
    if role == "Student" or not target_id:
        target_id = student_id

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if str(target_id).isdigit():
            cursor.execute("SELECT * FROM fees WHERE id = %s OR student_id = %s LIMIT 1", (int(target_id), str(target_id)))
        else:
            cursor.execute("SELECT * FROM fees WHERE student_id = %s LIMIT 1", (str(target_id),))
        f_row = cursor.fetchone()
        if not f_row:
            return handler_instance._send_json({"success": False, "message": "Fee record not found"}, 404)

        f = dict(f_row)
        if role == "Student":
            if f.get("student_id") != student_id and f.get("student_id") != user.get("student_id") and f.get("student_id") != user.get("username"):
                return handler_instance._send_json({"success": False, "message": "Forbidden: Cannot access other student fee receipts"}, 403)
        elif is_hod(user):
            if f.get("department") != user_dept:
                return handler_instance._send_json({"success": False, "message": "Forbidden: Cannot access fee receipts outside your department"}, 403)

        if not f.get("receipt_number"):
            r_num = f"REC-2026-{1000 + f['id']}"
            cursor.execute("UPDATE fees SET receipt_number = %s WHERE id = %s", (r_num, f["id"]))
            conn.commit()
            f["receipt_number"] = r_num

        receipt = {
            "receiptNumber": f["receipt_number"],
            "collegeName": "Government Polytechnic, Awasari (Kh.)",
            "studentName": f["student_name"],
            "studentId": f["student_id"],
            "department": f["department"],
            "totalFees": float(f["total_fees"]),
            "paidFees": float(f["paid_fees"]),
            "pendingFees": float(f["pending_fees"]),
            "amountPaid": float(f["paid_fees"]),
            "paymentDate": str(f.get("payment_date") or time.strftime('%Y-%m-%d')),
            "paymentStatus": f["payment_status"]
        }
        return handler_instance._send_json({"success": True, "receipt": receipt})
    except Exception as e:
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/fees/receipt', handle_get_fees_receipt)

def handle_get_fees(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')
    student_id = user.get('student_id') or user.get('username')

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if role == "Student":
            cursor.execute("SELECT * FROM fees WHERE student_id = %s OR student_id = %s ORDER BY id DESC", (student_id, user.get('student_id') or student_id))
        elif role in ["HOD", "Faculty"]:
            cursor.execute("SELECT * FROM fees WHERE department = %s ORDER BY id DESC", (user_dept,))
        else: # Admin / Administrator / Principal
            dept_filter = query_params.get("department", [None])[0]
            if dept_filter and dept_filter != "All":
                cursor.execute("SELECT * FROM fees WHERE department = %s ORDER BY id DESC", (dept_filter,))
            else:
                cursor.execute("SELECT * FROM fees ORDER BY id DESC")
        recs = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "fees": recs})
    except Exception as e:
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/fees', handle_get_fees)

def handle_post_fees(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    if not body or not isinstance(body, dict):
        return handler_instance._send_json({"success": False, "message": "Invalid request payload"}, 400)

    role = user.get('role')
    user_dept = user.get('department')
    fee_id = body.get("id")

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if role == "Student":
            s_id = user.get("student_id") or user.get("username")
            pay_amount = float(body.get("payAmount", 0) or 0)
            if pay_amount <= 0:
                return handler_instance._send_json({"success": False, "message": "Payment amount must be greater than 0"}, 400)

            cursor.execute("SELECT * FROM fees WHERE student_id = %s OR student_id = %s LIMIT 1", (s_id, user.get("student_id") or s_id))
            fee_row = cursor.fetchone()
            if not fee_row:
                return handler_instance._send_json({"success": False, "message": "No fee record assigned for your student account. Please contact Administration."}, 404)

            curr_paid = float(fee_row["paid_fees"])
            total_f = float(fee_row["total_fees"])
            curr_pending = max(0.0, total_f - curr_paid)

            if curr_pending <= 0:
                return handler_instance._send_json({"success": False, "message": "All fees are already fully paid. No pending balance remaining."}, 400)

            actual_paid = min(pay_amount, curr_pending)
            new_paid = curr_paid + actual_paid
            new_pending = max(0.0, total_f - new_paid)
            pay_status = "Paid" if new_pending <= 0 else "Partial"
            p_date = time.strftime('%Y-%m-%d')
            
            cursor.execute(
                "UPDATE fees SET paid_fees=%s, pending_fees=%s, payment_date=%s, payment_status=%s WHERE id=%s",
                (new_paid, new_pending, p_date, pay_status, fee_row["id"])
            )
            conn.commit()
            return handler_instance._send_json({
                "success": True,
                "message": f"Payment of ₹{actual_paid:g} processed successfully! Remaining Pending Fees: ₹{new_pending:g}."
            })

        if not is_hod(user):
            return handler_instance._send_json({"success": False, "message": "Permission denied: Only HODs are authorized to manage student fee records"}, 403)

        s_id = (body.get("studentId") or body.get("student_id") or "").strip()
        if not s_id:
            return handler_instance._send_json({"success": False, "message": "Enrollment Number / Student ID is required"}, 400)

        s_name = (body.get("studentName") or "Student").strip()
        dept = user_dept
        
        try:
            total_fees = float(body.get("totalFees", 0) or 0)
            paid_fees = float(body.get("paidFees", 0) or 0)
        except (ValueError, TypeError):
            return handler_instance._send_json({"success": False, "message": "Invalid fee amounts"}, 400)

        if total_fees < 0 or paid_fees < 0:
            return handler_instance._send_json({"success": False, "message": "Fee amounts cannot be negative"}, 400)

        if paid_fees > total_fees:
            return handler_instance._send_json({"success": False, "message": "Paid amount cannot exceed total fees"}, 400)

        pending_fees = max(0.0, total_fees - paid_fees)
        pay_status = "Paid" if pending_fees <= 0 else ("Partial" if paid_fees > 0 else "Pending")
        p_date = body.get("paymentDate") or time.strftime('%Y-%m-%d')

        cursor.execute("SELECT id, name, department FROM students WHERE id = %s OR roll_number = %s LIMIT 1", (s_id, s_id))
        stu_row = cursor.fetchone()
        if stu_row:
            s_id = stu_row["id"]
            if not s_name or s_name == "Student":
                s_name = stu_row.get("name", "Student")
        else:
            cursor.execute("SELECT student_id, name, department FROM users WHERE (student_id = %s OR username = %s) AND role = 'Student' LIMIT 1", (s_id, s_id))
            u_row = cursor.fetchone()
            if u_row:
                s_id = u_row.get("student_id") or s_id
                if not s_name or s_name == "Student":
                    s_name = u_row.get("name", "Student")
            else:
                return handler_instance._send_json({
                    "success": False,
                    "message": f"Student with Enrollment Number '{s_id}' was not found. Please register the student first."
                }, 404)

        if (stu_row and stu_row.get("department") != user_dept) or (u_row and u_row.get("department") != user_dept):
            return handler_instance._send_json({"success": False, "message": "Cannot manage fees for students outside your department"}, 403)
        dept = user_dept

        if fee_id:
            cursor.execute("SELECT id FROM fees WHERE student_id = %s AND id != %s", (s_id, fee_id))
            if cursor.fetchone():
                return handler_instance._send_json({"success": False, "message": f"A fee record already exists for student ID '{s_id}'."}, 400)

            cursor.execute(
                "UPDATE fees SET student_id=%s, student_name=%s, department=%s, total_fees=%s, paid_fees=%s, pending_fees=%s, payment_date=%s, payment_status=%s WHERE id=%s",
                (s_id, s_name, dept, total_fees, paid_fees, pending_fees, p_date, pay_status, fee_id)
            )
        else:
            cursor.execute("SELECT id FROM fees WHERE student_id = %s", (s_id,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE fees SET total_fees=%s, paid_fees=%s, pending_fees=%s, payment_date=%s, payment_status=%s, student_name=%s, department=%s WHERE id=%s",
                    (total_fees, paid_fees, pending_fees, p_date, pay_status, s_name, dept, existing["id"])
                )
            else:
                cursor.execute(
                    "INSERT INTO fees (student_id, student_name, department, total_fees, paid_fees, pending_fees, payment_date, payment_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (s_id, s_name, dept, total_fees, paid_fees, pending_fees, p_date, pay_status)
                )
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Fee record saved successfully!"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('POST', '/api/fees', handle_post_fees)

def handle_delete_fees(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user or not is_hod(user):
        return handler_instance._send_json({"success": False, "message": "Permission denied: Only HODs are authorized to delete student fee records"}, 403)

    user_dept = user.get('department')
    item_id = query_params.get("id", [None])[0] or (body.get("id") if isinstance(body, dict) else None)

    if not item_id:
        return handler_instance._send_json({"success": False, "message": "Fee record ID required"}, 400)

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM fees WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row:
            return handler_instance._send_json({"success": False, "message": "Fee record not found"}, 404)

        if is_hod(user) and row.get("department") != user_dept:
            return handler_instance._send_json({"success": False, "message": "Cannot delete fee record outside your department"}, 403)

        cursor.execute("DELETE FROM fees WHERE id = %s", (item_id,))
        conn.commit()
        return handler_instance._send_json({"success": True, "message": "Fee record deleted successfully"})
    except Exception as e:
        conn.rollback()
        return handler_instance._send_json({"success": False, "message": str(e)}, 500)
    finally:
        cursor.close()
        conn.close()

register_route('DELETE', '/api/fees', handle_delete_fees)

