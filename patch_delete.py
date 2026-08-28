import os
import re

backend_dir = os.path.join(os.path.dirname(__file__), "backend")

def patch_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    # Find where cursor = conn.cursor(dictionary=True) is inside handle_delete_*
    
    # We will use regex to find the handle_delete_* definitions
    # and insert the item_id logic right before the cursor.execute("DELETE...") or SELECT if HOD
    
    # Actually, a simpler way is to just replace:
    #     cursor = conn.cursor(dictionary=True)
    # with:
    #     cursor = conn.cursor(dictionary=True)
    #     item_id = query_params.get("id", [None])[0] or body.get("id")
    #     if not item_id:
    #         conn.close()
    #         return handler_instance._send_json({"success": False, "message": "ID required"}, 400)
    
    # But wait, this might inject it in handle_get and handle_post too!
    # Let's split by "def handle_delete_"
    
    parts = content.split("def handle_delete_")
    if len(parts) == 1:
        return
        
    new_content = parts[0]
    for i in range(1, len(parts)):
        part = parts[i]
        
        injection = """
    item_id = query_params.get("id", [None])[0] or body.get("id")
    if not item_id:
        if conn: conn.close()
        handler_instance._send_json({"success": False, "message": "ID required"}, 400)
        return
"""
        # Find the line with cursor = conn.cursor(dictionary=True)
        part = part.replace("cursor = conn.cursor(dictionary=True)", "cursor = conn.cursor(dictionary=True)" + injection, 1)
        new_content += "def handle_delete_" + part

    with open(filepath, "w") as f:
        f.write(new_content)
    print(f"Patched {os.path.basename(filepath)}")

for root, dirs, files in os.walk(backend_dir):
    for file in files:
        if file.endswith("_controller.py"):
            patch_file(os.path.join(root, file))
