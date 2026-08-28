import sys
sys.path.insert(0, 'backend')
import router
from config.database import init_db

init_db()

class DummyHandler:
    def __init__(self):
        self.headers = {}
        self.path = '/api/notices'
    
    def _send_json(self, data, status_code=200):
        print("SENT JSON:", data)

h = DummyHandler()
try:
    router.handle_request("GET", h)
except Exception as e:
    import traceback
    traceback.print_exc()
