from config.database import get_db_connection
conn = get_db_connection()
c=conn.cursor(dictionary=True)
c.execute("SELECT student_id, faculty_id FROM users WHERE username='testuser2'")
print("USER RECORD:", c.fetchall())
