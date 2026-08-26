import sqlite3

conn = sqlite3.connect('college_erp.db')
cursor = conn.cursor()

cursor.execute("SELECT sql FROM sqlite_master WHERE name='students'")
row = cursor.fetchone()
print("Students Table Schema:")
print(row[0] if row else "Table not found")

cursor.execute("SELECT id, roll_number, name FROM students LIMIT 5")
print("\nSample Students:")
for r in cursor.fetchall():
    print(r)
