import os
import sys

# Ensure backend directory is in sys.path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config.database import test_db_connection, get_db_connection

if __name__ == "__main__":
    print("==================================================")
    print("COLLEGE ERP — MYSQL DATABASE CONNECTION TEST")
    print("==================================================")
    ok, msg, details = test_db_connection()
    status_str = "SUCCESS" if ok else "FAILED"
    print(f"Status: {status_str}")
    print(f"Message: {msg}")
    print("\nConnection Details:")
    for k, v in details.items():
        if k != "tables":
            print(f"  {k:<20}: {v}")
    if "tables" in details:
        print(f"  {'tables':<20}: {', '.join(details['tables'])}")
    print("==================================================")
    
    if ok:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS user_count FROM users")
            user_cnt = cursor.fetchone()["user_count"]
            print(f"Live Query Verification: Found {user_cnt} registered users in 'users' table.")
            cursor.close()
            conn.close()
        exit(0)
    else:
        exit(1)
