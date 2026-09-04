import os
import sys
import unittest
import json
import io
import uuid

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config.database import get_db_connection, init_db
from router import handle_request
from auth.permissions import SESSIONS
from auth.utils import hash_password, verify_password

class MockResponseHandler:
    def __init__(self, path="/", headers=None, body=None):
        self.path = path
        self.headers = headers or {}
        self._raw_body = json.dumps(body).encode("utf-8") if body is not None else b""
        if self._raw_body:
            self.headers["Content-Length"] = str(len(self._raw_body))
        self.rfile = io.BytesIO(self._raw_body)
        self.wfile = io.BytesIO()
        self.status_code = None
        self.response_data = None
        self._response_headers = {}

    def send_response(self, code):
        self.status_code = code

    def send_header(self, keyword, value):
        self._response_headers[keyword] = value

    def end_headers(self):
        pass

    def _send_json(self, data, status_code=200, headers=None):
        self.status_code = status_code
        self.response_data = data
        return data

class TestAll25Bugs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.token = "admin-test-token-all25"
        SESSIONS[cls.token] = {
            "id": 1,
            "username": "admin_tester",
            "role": "Administrator",
            "department": "Administration"
        }
        cls.hod_token = "hod-test-token-all25"
        SESSIONS[cls.hod_token] = {
            "id": 2,
            "username": "hod_tester",
            "role": "HOD",
            "department": "Computer Engineering"
        }

    def _req(self, method, path, body=None, token=None):
        headers = {}
        t = token or self.token
        if t:
            headers["Authorization"] = f"Bearer {t}"
        handler = MockResponseHandler(path=path, headers=headers, body=body)
        handle_request(method, handler)
        return handler.status_code, handler.response_data

    # --- BUG 1 & BUG 13: HOD Duplicates & Edit ---
    def test_bug_01_and_13_hod_duplicate_and_edit(self):
        dept = "Computer Engineering"
        # Edit existing or add
        status, res = self._req("POST", "/api/hods", {
            "department": dept,
            "name": "Dr. Shankar",
            "qualification": "Ph.D. in Computer Engg",
            "experience": "15 Years",
            "email": "shankar@gmail.com",
            "contact": "9876543210",
            "is_edit": True
        })
        self.assertEqual(status, 200)

        # Listing should return exactly 1 row for this department
        status, list_res = self._req("GET", "/api/hods")
        self.assertEqual(status, 200)
        matching = [h for h in list_res.get("hods", []) if h["department"] == dept]
        self.assertEqual(len(matching), 1, f"Expected 1 HOD for {dept}, got {len(matching)}")

        # Attempt duplicate without edit mode -> must return 400
        status, dup_res = self._req("POST", "/api/hods", {
            "department": dept,
            "name": "Dr. Duplicate Person",
            "qualification": "M.Tech",
            "experience": "3 Years",
            "email": "another_shankar@gmail.com",
            "contact": "9800000000",
            "faculty_id": "HOD_DIFF_CO"
        })
        self.assertEqual(status, 400)

    def _create_test_student(self, cur, stu_id, name="Test Student", dept="Computer Engineering", roll_no=None):
        r_no = roll_no or f"R_{uuid.uuid4().hex[:5]}"
        cur.execute(
            """INSERT INTO students (id, roll_number, name, email, mobile, gender, dob, department, year, semester, division, admission_year, address, status)
               VALUES (%s, %s, %s, %s, '9876543210', 'Male', '2000-01-01', %s, 'First Year', 'Semester 1', 'A', 2026, 'Campus', 'Active')""",
            (stu_id, r_no, name, f"{stu_id.lower()}@college.edu", dept)
        )

    # --- BUG 2 & BUG 4: Faculty Duplicates & UPDATE (No Data Loss) ---
    def test_bug_02_and_04_faculty_duplicate_and_update(self):
        fac_id = f"FAC_TEST_{uuid.uuid4().hex[:6]}"
        stu_id = f"STU_TEST_ASSIGN_{uuid.uuid4().hex[:6]}"
        
        # Create student first
        conn = get_db_connection()
        cur = conn.cursor(buffered=True)
        self._create_test_student(cur, stu_id, "Dummy Assign Stu", "Computer Engineering")
        conn.commit()

        # Create faculty
        status, res = self._req("POST", "/api/faculty", {
            "id": fac_id,
            "name": "Prof. Test Faculty",
            "department": "Computer Engineering",
            "designation": "Assistant Professor",
            "email": f"{fac_id.lower()}@college.edu",
            "mobile": "9876500001",
            "experience": "5 Years"
        }, token=self.hod_token)
        self.assertEqual(status, 200)

        # Assign student to this faculty in faculty_students
        cur.execute("INSERT INTO faculty_students (faculty_id, student_id) VALUES (%s, %s)", (fac_id, stu_id))
        conn.commit()

        # Update faculty details using UPDATE (must NOT delete assignment)
        status, edit_res = self._req("POST", "/api/faculty", {
            "id": fac_id,
            "name": "Prof. Test Faculty (Updated)",
            "department": "Computer Engineering",
            "designation": "Associate Professor",
            "email": f"{fac_id.lower()}@college.edu",
            "mobile": "9876500002",
            "experience": "6 Years",
            "is_edit": True
        }, token=self.hod_token)
        self.assertEqual(status, 200)

        # Verify assignment still exists
        cur.execute("SELECT id FROM faculty_students WHERE faculty_id = %s AND student_id = %s", (fac_id, stu_id))
        self.assertIsNotNone(cur.fetchone(), "Faculty student assignment was deleted during faculty update!")

        # Verify faculty listing has exactly 1 row for this faculty ID
        status, list_res = self._req("GET", "/api/faculty?department=Computer Engineering", token=self.hod_token)
        matching = [f for f in list_res.get("faculty", []) if f["id"] == fac_id]
        self.assertEqual(len(matching), 1)

        # Clean up
        cur.execute("DELETE FROM faculty_students WHERE faculty_id = %s", (fac_id,))
        cur.execute("DELETE FROM faculty WHERE id = %s", (fac_id,))
        cur.execute("DELETE FROM users WHERE faculty_id = %s", (fac_id,))
        cur.execute("DELETE FROM students WHERE id = %s", (stu_id,))
        conn.commit()
        cur.close()
        conn.close()

    # --- BUG 3: Student UPDATE Data Loss Prevention ---
    def test_bug_03_student_update_preserves_foreign_keys(self):
        stu_id = f"STU_TEST_{uuid.uuid4().hex[:6]}"
        fac_id = f"FAC_DUMMY_{uuid.uuid4().hex[:6]}"
        roll_no = f"R_{uuid.uuid4().hex[:5]}"

        conn = get_db_connection()
        cur = conn.cursor(buffered=True)
        cur.execute("INSERT INTO faculty (id, name, department, designation, email, mobile, experience, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')",
                    (fac_id, "Dummy Faculty", "Computer Engineering", "Professor", f"{fac_id.lower()}@college.edu", "9876543210", "10 Years"))
        conn.commit()

        # 1. Create Student
        status, res = self._req("POST", "/api/students", {
            "id": stu_id,
            "rollNumber": roll_no,
            "name": "Original Student Name",
            "department": "Computer Engineering",
            "email": f"{stu_id.lower()}@college.edu",
            "mobile": "9876543210",
            "year": "First Year",
            "semester": "Semester 1",
            "division": "A"
        }, token=self.hod_token)
        self.assertEqual(status, 200, f"Failed creating student: {res}")

        # 2. Insert related attendance, results, fees, and assignments
        cur.execute("INSERT INTO attendance (student_id, student_name, subject, date, status, department) VALUES (%s, %s, %s, %s, %s, %s)",
                    (stu_id, "Original Student Name", "Java", "2026-09-03", "Present", "Computer Engineering"))
        cur.execute("INSERT INTO results (student_id, student_name, subject, semester, internal_marks, end_sem_marks, total_marks, percentage, grade, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (stu_id, "Original Student Name", "Java", "Semester 1", 20, 60, 80, 80.0, "A", "Pass"))
        cur.execute("INSERT INTO fees (student_id, student_name, department, total_fees, paid_fees, pending_fees, payment_status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (stu_id, "Original Student Name", "Computer Engineering", 50000, 20000, 30000, "Partial"))
        cur.execute("INSERT INTO faculty_students (faculty_id, student_id) VALUES (%s, %s)", (fac_id, stu_id))
        conn.commit()

        # 3. Edit Student
        status, edit_res = self._req("POST", "/api/students", {
            "id": stu_id,
            "rollNumber": roll_no,
            "name": "Updated Student Name",
            "department": "Computer Engineering",
            "email": f"{stu_id.lower()}@college.edu",
            "mobile": "9876543210",
            "year": "First Year",
            "semester": "Semester 1",
            "division": "A",
            "is_edit": True
        }, token=self.hod_token)
        self.assertEqual(status, 200)

        # 4. Verify that attendance, results, fees, and faculty assignments ALL still exist!
        cur.execute("SELECT id FROM attendance WHERE student_id = %s", (stu_id,))
        self.assertIsNotNone(cur.fetchone(), "Attendance record lost during student edit!")

        cur.execute("SELECT id FROM results WHERE student_id = %s", (stu_id,))
        self.assertIsNotNone(cur.fetchone(), "Result record lost during student edit!")

        cur.execute("SELECT id FROM fees WHERE student_id = %s", (stu_id,))
        self.assertIsNotNone(cur.fetchone(), "Fee record lost during student edit!")

        cur.execute("SELECT id FROM faculty_students WHERE student_id = %s", (stu_id,))
        self.assertIsNotNone(cur.fetchone(), "Faculty student assignment lost during student edit!")

        # Clean up
        cur.execute("DELETE FROM attendance WHERE student_id = %s", (stu_id,))
        cur.execute("DELETE FROM results WHERE student_id = %s", (stu_id,))
        cur.execute("DELETE FROM fees WHERE student_id = %s", (stu_id,))
        cur.execute("DELETE FROM faculty_students WHERE student_id = %s", (stu_id,))
        cur.execute("DELETE FROM students WHERE id = %s", (stu_id,))
        cur.execute("DELETE FROM users WHERE student_id = %s", (stu_id,))
        cur.execute("DELETE FROM faculty WHERE id = %s", (fac_id,))
        conn.commit()
        cur.close()
        conn.close()

    # --- BUG 5: HOD Status Synchronization Scoping ---
    def test_bug_05_status_synchronization_scoping(self):
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True, buffered=True)
        # Create pending student and pending HOD in same department
        stu_uname = f"stu_pending_{uuid.uuid4().hex[:6]}"
        hod_uname = f"hod_pending_{uuid.uuid4().hex[:6]}"
        
        cur.execute("INSERT INTO users (username, password, role, name, email, department, status) VALUES (%s, %s, %s, %s, %s, %s, 'Pending')",
                    (stu_uname, hash_password("Pass123"), "Student", "Pending Student", f"{stu_uname}@college.edu", "Civil Engineering"))
        stu_id = cur.lastrowid
        cur.execute("INSERT INTO users (username, password, role, name, email, department, status) VALUES (%s, %s, %s, %s, %s, %s, 'Pending')",
                    (hod_uname, hash_password("Pass123"), "HOD", "Pending HOD", f"{hod_uname}@college.edu", "Civil Engineering"))
        hod_id = cur.lastrowid
        conn.commit()

        # Approve HOD
        status, res = self._req("POST", "/api/admin/approve-user", {"user_id": hod_id})
        self.assertEqual(status, 200)

        # Verify HOD is Active but Student remains Pending
        cur.execute("SELECT status FROM users WHERE id = %s", (hod_id,))
        self.assertEqual(cur.fetchone()["status"], "Active")

        cur.execute("SELECT status FROM users WHERE id = %s", (stu_id,))
        self.assertEqual(cur.fetchone()["status"], "Pending", "Student status was accidentally modified when approving HOD!")

        # Clean up
        cur.execute("DELETE FROM users WHERE id IN (%s, %s)", (stu_id, hod_id))
        conn.commit()
        cur.close()
        conn.close()

    # --- BUG 6 & BUG 16: Attendance Duplicate Prevention & Edit ---
    def test_bug_06_and_16_attendance_duplicates_and_edit(self):
        stu_id = f"STU_ATT_{uuid.uuid4().hex[:6]}"
        conn = get_db_connection()
        cur = conn.cursor(buffered=True)
        self._create_test_student(cur, stu_id, "Att Student", "Computer Engineering")
        conn.commit()

        # 1. First insertion -> 200 OK
        status, res = self._req("POST", "/api/attendance", {
            "studentId": stu_id,
            "studentName": "Att Student",
            "subject": "Mathematics",
            "date": "2026-09-04",
            "status": "Present"
        })
        self.assertEqual(status, 200)

        # 2. Duplicate insertion for same Student + Subject + Date -> must return 400
        status, dup_res = self._req("POST", "/api/attendance", {
            "studentId": stu_id,
            "studentName": "Att Student",
            "subject": "Mathematics",
            "date": "2026-09-04",
            "status": "Present"
        })
        self.assertEqual(status, 400)
        self.assertIn("already exists", dup_res["message"].lower())

        # 3. Edit attendance record using ID -> 200 OK
        cur.execute("SELECT id FROM attendance WHERE student_id = %s AND subject = 'Mathematics' AND date = '2026-09-04'", (stu_id,))
        att_id = cur.fetchone()[0]
        status, edit_res = self._req("POST", "/api/attendance", {
            "id": att_id,
            "studentId": stu_id,
            "studentName": "Att Student",
            "subject": "Mathematics",
            "date": "2026-09-04",
            "status": "Absent"
        })
        self.assertEqual(status, 200)

        # Clean up
        cur.execute("DELETE FROM attendance WHERE student_id = %s", (stu_id,))
        cur.execute("DELETE FROM students WHERE id = %s", (stu_id,))
        conn.commit()
        cur.close()
        conn.close()

    # --- BUG 7, 8, 9 & 17: Result Duplicates, Grading, Validation & Edit ---
    def test_bug_07_08_09_17_results(self):
        stu_id = f"STU_RES_{uuid.uuid4().hex[:6]}"
        conn = get_db_connection()
        cur = conn.cursor(buffered=True)
        self._create_test_student(cur, stu_id, "Res Student", "Computer Engineering")
        conn.commit()

        # Bug 9: Invalid/negative/overflow marks validation -> must return 400
        status, bad_res = self._req("POST", "/api/results", {
            "studentId": stu_id,
            "subject": "Database Systems",
            "semester": "Semester 1",
            "internalMarks": -5,
            "endSemMarks": 60
        })
        self.assertEqual(status, 400)

        status, bad_res2 = self._req("POST", "/api/results", {
            "studentId": stu_id,
            "subject": "Database Systems",
            "semester": "Semester 1",
            "internalMarks": 40,
            "endSemMarks": 80
        })
        self.assertEqual(status, 400)

        # Bug 8: Valid result save and grade calculation (Internal 20 + EndSem 65 = 85 -> Grade A)
        status, res = self._req("POST", "/api/results", {
            "studentId": stu_id,
            "studentName": "Res Student",
            "subject": "Database Systems",
            "semester": "Semester 1",
            "internalMarks": 20,
            "endSemMarks": 65
        })
        self.assertEqual(status, 200)
        res_id = res.get("id")

        cur.execute("SELECT grade, status, total_marks FROM results WHERE student_id = %s AND subject = 'Database Systems'", (stu_id,))
        row = cur.fetchone()
        self.assertEqual(row[0], "A")
        self.assertEqual(row[1], "Pass")
        self.assertEqual(row[2], 85)

        # Bug 7: Duplicate creation for same Student + Subject + Semester updates existing record
        status, dup_res = self._req("POST", "/api/results", {
            "studentId": stu_id,
            "studentName": "Res Student",
            "subject": "Database Systems",
            "semester": "Semester 1",
            "internalMarks": 25,
            "endSemMarks": 70
        })
        self.assertEqual(status, 200)
        cur.execute("SELECT COUNT(*) FROM results WHERE student_id = %s AND subject = 'Database Systems'", (stu_id,))
        self.assertEqual(cur.fetchone()[0], 1, "Duplicate result record created!")

        # Bug 17: Result edit
        status, edit_res = self._req("POST", "/api/results", {
            "id": res_id,
            "studentId": stu_id,
            "studentName": "Res Student",
            "subject": "Database Systems",
            "semester": "Semester 1",
            "internalMarks": 28,
            "endSemMarks": 70
        })
        self.assertEqual(status, 200)

        # Clean up
        cur.execute("DELETE FROM results WHERE student_id = %s", (stu_id,))
        cur.execute("DELETE FROM students WHERE id = %s", (stu_id,))
        conn.commit()
        cur.close()
        conn.close()

    # --- BUG 10 & BUG 11: Fees Overpayment Capping & Update Validation ---
    def test_bug_10_and_11_fees(self):
        stu_id = f"STU_FEE_{uuid.uuid4().hex[:6]}"
        conn = get_db_connection()
        cur = conn.cursor(buffered=True)
        self._create_test_student(cur, stu_id, "Fee Student", "Computer Engineering")
        cur.execute("INSERT INTO fees (student_id, student_name, department, total_fees, paid_fees, pending_fees, payment_status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (stu_id, "Fee Student", "Computer Engineering", 20000, 15000, 5000, "Partial"))
        fee_id = cur.lastrowid
        conn.commit()

        # Student pays ₹10,000 when pending is ₹5,000 -> must cap payment to ₹5,000
        stu_token = f"token_{stu_id}"
        SESSIONS[stu_token] = {"id": 999, "student_id": stu_id, "role": "Student", "department": "Computer Engineering"}
        status, pay_res = self._req("POST", "/api/fees", {"payAmount": 10000}, token=stu_token)
        self.assertEqual(status, 200)
        self.assertIn("5000", pay_res["message"])

        cur.execute("SELECT paid_fees, pending_fees, payment_status FROM fees WHERE student_id = %s", (stu_id,))
        row = cur.fetchone()
        self.assertEqual(row[0], 20000.0)
        self.assertEqual(row[1], 0.0)
        self.assertEqual(row[2], "Paid")

        # Clean up
        cur.execute("DELETE FROM fees WHERE student_id = %s", (stu_id,))
        cur.execute("DELETE FROM students WHERE id = %s", (stu_id,))
        conn.commit()
        cur.close()
        conn.close()

    # --- BUG 12 & BUG 18: Timetable Conflicts & Edit ---
    def test_bug_12_and_18_timetable(self):
        # 1. Create slot
        status, res = self._req("POST", "/api/timetable", {
            "department": "Computer Engineering",
            "semester": "Semester 1",
            "division": "A",
            "day": "Monday",
            "time": "09:00 AM - 10:00 AM",
            "subject": "Operating Systems",
            "faculty": "Prof. Smith",
            "room": "Lab 101"
        })
        self.assertEqual(status, 200)

        # 2. Conflicting slot for same division + day + time -> 400
        status, conf_res = self._req("POST", "/api/timetable", {
            "department": "Computer Engineering",
            "semester": "Semester 1",
            "division": "A",
            "day": "Monday",
            "time": "09:00 AM - 10:00 AM",
            "subject": "Data Structures",
            "faculty": "Prof. Davis",
            "room": "Lab 102"
        })
        self.assertEqual(status, 400)
        self.assertIn("conflict", conf_res["message"].lower())

        # Clean up
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM timetable WHERE department = 'Computer Engineering' AND day = 'Monday' AND time = '09:00 AM - 10:00 AM'")
        conn.commit()
        cur.close()
        conn.close()

    # --- BUG 19: Unique Subject Code Validation ---
    def test_bug_19_unique_subject_code(self):
        code = f"CS_{uuid.uuid4().hex[:4].upper()}"
        status, res = self._req("POST", "/api/subjects", {
            "code": code,
            "name": "Cloud Computing",
            "department": "Computer Engineering",
            "semester": "Semester 5",
            "credits": 4
        })
        self.assertEqual(status, 200)

        # Duplicate subject code -> must return 400
        status, dup_res = self._req("POST", "/api/subjects", {
            "code": code,
            "name": "Cloud Computing Advanced",
            "department": "Computer Engineering",
            "semester": "Semester 6",
            "credits": 4
        })
        self.assertEqual(status, 400)
        self.assertIn("already exists", dup_res["message"].lower())

        # Clean up
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM subjects WHERE code = %s", (code,))
        conn.commit()
        cur.close()
        conn.close()

    # --- BUG 20: Department Delete Protection ---
    def test_bug_20_department_delete_protection(self):
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True, buffered=True)
        # Verify Computer Engineering has students/faculty/HOD
        cur.execute("SELECT id FROM departments WHERE name = 'Computer Engineering'")
        dept_row = cur.fetchone()
        if dept_row:
            dept_id = dept_row["id"]
            status, res = self._req("DELETE", f"/api/departments?id={dept_id}")
            self.assertEqual(status, 400, "Department with dependent records was deleted without protection!")
            self.assertIn("cannot delete department", res["message"].lower())
        cur.close()
        conn.close()

    # --- BUG 21: Report CSV Exports ---
    def test_bug_21_report_exports(self):
        for r_type in ["student", "faculty", "attendance", "results", "fees"]:
            handler = MockResponseHandler(path=f"/api/reports/export?type={r_type}", headers={"Authorization": f"Bearer {self.token}"})
            handle_request("GET", handler)
            self.assertEqual(handler.status_code, 200, f"Export failed for report type {r_type}")
            self.assertEqual(handler._response_headers.get("Content-type"), "text/csv; charset=utf-8")

if __name__ == "__main__":
    unittest.main(verbosity=2)
