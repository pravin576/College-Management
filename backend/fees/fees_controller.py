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
    student_id = user.get('student_id')

    target_id = query_params.get("id", [None])[0]
    if role == "Student" or not target_id:
        target_id = student_id

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM fees WHERE id = %s OR student_id = %s", (target_id, target_id))
        f_row = cursor.fetchone()
        if not f_row:
            return handler_instance._send_json({"success": False, "message": "Fee record not found"}, 404)

        f = dict(f_row)
        if role == "Student" and f.get("student_id") != student_id:
            return handler_instance._send_json({"success": False, "message": "Forbidden: Cannot access other student fee receipts"}, 403)

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
    student_id = user.get('student_id')

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if role == "Student":
            cursor.execute("SELECT * FROM fees WHERE student_id = %s", (student_id,))
        elif role in ["HOD", "Faculty"]:
            cursor.execute("SELECT * FROM fees WHERE department = %s", (user_dept,))
        else: # Admin
            dept_filter = query_params.get("department", [None])[0]
            if dept_filter and dept_filter != "All":
                cursor.execute("SELECT * FROM fees WHERE department = %s", (dept_filter,))
            else:
                cursor.execute("SELECT * FROM fees")
        recs = [dict(r) for r in cursor.fetchall()]
        return handler_instance._send_json({"success": True, "fees": recs})
    finally:
        cursor.close()
        conn.close()

register_route('GET', '/api/fees', handle_get_fees)

def handle_post_fees(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    if not user:
        return handler_instance._send_json({"success": False, "message": "Unauthorized"}, 401)

    role = user.get('role')
    user_dept = user.get('department')
    fee_id = body.get("id")

    conn = get_db_connection()
    if not conn:
        return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    try:
        if role == "Student":
            s_id = user.get("student_id")
            pay_amount = float(body.get("payAmount", 0))
            if pay_amount <= 0:
                return handler_instance._send_json({"success": False, "message": "Payment amount must be greater than 0"}, 400)

            cursor.execute("SELECT * FROM fees WHERE student_id = %s", (s_id,))
            fee_row = cursor.fetchone()
            if fee_row:
                curr_paid = float(fee_row["paid_fees"])
                total_f = float(fee_row["total_fees"])
                curr_pending = max(0.0, total_f - curr_paid)

                if curr_pending <= 0:
                    return handler_instance._send_json({"success": False, "message": "All fees are already fully paid. No pending balance remaining."}, 400)

                actual_paid = min(pay_amount, curr_pending)
                new_paid = curr_paid + actual_paid
                new_pending = max(0.0, total_f - new_paid)
                pay_status = "Paid" if new_pending <= 0 else "Partial"
                cursor.execute(
                    "UPDATE fees SET paid_fees=%s, pending_fees=%s, payment_date=%s, payment_status=%s WHERE student_id=%s",
                    (new_paid, new_pending, time.strftime('%Y-%m-%d'), pay_status, s_id)
                )
                conn.commit()
                return handler_instance._send_json({"success": True, "message": f"Payment of ₹{actual_paid:g} processed successfully! Remaining Pending Fees: ₹{new_pending:g}."})
            else:
                return handler_instance._send_json({"success": False, "message": "No fee record assigned for student"}, 404)

        if not (is_admin(user) or is_hod(user)):
            return handler_instance._send_json({"success": False, "message": "Permission denied: Faculty and unauthorized users cannot manage fees"}, 403)

        s_id = (body.get("studentId") or body.get("student_id") or "").strip()
        s_name = (body.get("studentName") or "Student").strip()
        dept = user_dept if is_hod(user) else (body.get("department") or "Computer Engineering").strip()
        total_fees = float(body.get("totalFees", 0))
        paid_fees = float(body.get("paidFees", 0))
        pending_fees = max(0.0, total_fees - paid_fees)
        pay_status = "Paid" if pending_fees <= 0 else ("Partial" if paid_fees > 0 else "Pending")
        p_date = body.get("paymentDate", time.strftime('%Y-%m-%d'))

        cursor.execute("SELECT id, name, department FROM students WHERE id = %s OR roll_number = %s LIMIT 1", (s_id, s_id))
        stu_row = cursor.fetchone()
        if stu_row:
            s_id = stu_row["id"]
            if not s_name or s_name == "Student":
                s_name = stu_row.get("name", "Student")
            if not is_hod(user) and not body.get("department"):
                dept = stu_row.get("department", dept)

        if is_hod(user):
            if not stu_row or stu_row["department"] != user_dept:
                return handler_instance._send_json({"success": False, "message": "Cannot manage fees for students outside your department"}, 403)

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
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE fees SET total_fees=%s, paid_fees=%s, pending_fees=%s, payment_date=%s, payment_status=%s WHERE student_id=%s",
                    (total_fees, paid_fees, pending_fees, p_date, pay_status, s_id)
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
    if not user or is_student(user) or is_faculty(user):
        return handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)

    role = user.get('role')
    user_dept = user.get('department')
    item_id = query_params.get("id", [None])[0] or body.get("id")

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
