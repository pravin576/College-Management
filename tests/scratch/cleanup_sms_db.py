import sqlite3
import os

DB_FILE = "college_erp.db"

def cleanup_database():
    if not os.path.exists(DB_FILE):
        print(f"Database file '{DB_FILE}' not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Drop sms_logs table if it exists
    cursor.execute("DROP TABLE IF EXISTS sms_logs")
    conn.commit()
    print("[PASS] Dropped table 'sms_logs' if present.")

    # Verify existing core ERP tables remain completely intact
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"[INFO] Remaining ERP Database Tables: {tables}")
    
    conn.close()

if __name__ == "__main__":
    cleanup_database()
