import base64
import urllib.parse
import datetime
import json
import time
import os
from config.database import get_db_connection
from router import register_route
from auth.permissions import get_current_user

def handle_get_fees_receipt(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    target_id = query_params.get("id", [None])[0]
    if not target_id:
        target_id = student_id
    cursor.execute("SELECT * FROM fees WHERE id = %s OR student_id = %s", (target_id, target_id))
    f_row = cursor.fetchone()
    if not f_row:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Fee record not found"}, 404)
        return
    f = dict(f_row)
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
        "totalFees": f["total_fees"],
        "paidFees": f["paid_fees"],
        "pendingFees": f["pending_fees"],
        "amountPaid": f["paid_fees"],
        "paymentDate": f.get("payment_date") or time.strftime('%Y-%m-%d'),
        "paymentStatus": f["payment_status"]
    }
    conn.close()
    handler_instance._send_json({"success": True, "receipt": receipt})
    return

#     tendance Export CSV Endpoint

register_route('GET', '/api/fees/receipt', handle_get_fees_receipt)

def handle_get_fees(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

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
    conn.close()
    handler_instance._send_json({"success": True, "fees": recs})
    return

#      Timetable Endpoint

register_route('GET', '/api/fees', handle_get_fees)

def handle_post_fees(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)

    fee_id = body.get("id")

    if role == "Student":
        s_id = user.get("student_id")
        pay_amount = float(body.get("payAmount", 0))
        # conn.row_factory = 
        pass
        cursor.execute("SELECT * FROM fees WHERE student_id = %s", (s_id,))
        fee_row = cursor.fetchone()
        if fee_row:
            fee_dict = dict(fee_row)
            curr_paid = float(fee_dict["paid_fees"])
            total_f = float(fee_dict["total_fees"])
            new_paid = min(total_f, curr_paid + pay_amount)
            new_pending = max(0.0, total_f - new_paid)
            pay_status = "Paid" if new_pending <= 0 else "Partial"
            cursor.execute(
                "UPDATE fees SET paid_fees=%s, pending_fees=%s, payment_date=%s, payment_status=%s WHERE student_id=%s",
                (new_paid, new_pending, time.strftime('%Y-%m-%d'), pay_status, s_id)
            )
            conn.commit()
            conn.close()
            handler_instance._send_json({"success": True, "message": f"Payment of ₹{pay_amount} processed successfully!"})
            return
        else:
            conn.close()
            handler_instance._send_json({"success": False, "message": "No fee record assigned for student"}, 404)
            return

    if role not in ["Administrator", "Admin", "HOD"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return

    s_id = body.get("studentId") or body.get("student_id")
    s_name = body.get("studentName", "Student")
    dept = user_dept if role == "HOD" else body.get("department", "Computer Science")
    total_fees = float(body.get("totalFees", 0))
    paid_fees = float(body.get("paidFees", 0))
    pending_fees = max(0.0, total_fees - paid_fees)
    pay_status = "Paid" if pending_fees <= 0 else "Partial" if paid_fees > 0 else "Pending"
    p_date = body.get("paymentDate", time.strftime('%Y-%m-%d'))

    if fee_id:
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
    conn.close()
    handler_instance._send_json({"success": True, "message": "Fee record saved successfully!"})
    return

#     . Timetable CRUD

register_route('POST', '/api/fees', handle_post_fees)

def handle_delete_fees(handler_instance, query_params, body):
    user = get_current_user(handler_instance)
    role = user['role'] if user else None
    user_dept = user['department'] if user else None
    student_id = user['student_id'] if user else None
    faculty_id = user['faculty_id'] if user else None
    conn = get_db_connection()
    if not conn: return handler_instance._send_json({'success': False, 'message': 'DB Error'}, 500)
    cursor = conn.cursor(dictionary=True)
    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        if conn: conn.close()
        handler_instance._send_json({"success": False, "message": "ID required"}, 400)
        return


    if role not in ["Administrator", "Admin", "HOD"]:
        conn.close()
        handler_instance._send_json({"success": False, "message": "Permission denied"}, 403)
        return
    if role == "HOD":
        cursor.execute("SELECT department FROM fees WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row or row[0] != user_dept:
            conn.close()
            handler_instance._send_json({"success": False, "message": "Cannot delete fee record outside your department"}, 403)
            return
    cursor.execute("DELETE FROM fees WHERE id = %s", (item_id,))


register_route('DELETE', '/api/fees', handle_delete_fees)

