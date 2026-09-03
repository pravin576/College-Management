import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if os.path.join(os.path.dirname(__file__), "backend") not in sys.path:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import router
from config.database import init_db

init_db()

class DummyHandler:
    def __init__(self):
        self.headers = {}
        self.path = '/api/notices'
    
    def _send_json(self, data, status_code=200):
        print("SENT JSON:", data)

if __name__ == "__main__":
    h = DummyHandler()
    try:
        router.handle_request("GET", h)
    except Exception as e:
        import traceback
        traceback.print_exc()
