import http.server
import socketserver
import json
import os
import urllib.parse
import datetime
import decimal

try:
    from dotenv import load_dotenv
    env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if not os.path.exists(env_path):
        env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env.example"))
    load_dotenv(env_path)
except ImportError:
    pass

from config.database import init_db
from router import handle_request

PORT = int(os.environ.get("PORT", 8000))
CUR_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.normpath(os.path.join(CUR_FILE_DIR, "..", "frontend"))

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        return super().default(obj)

class ERPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def _send_json(self, data, status_code=200, headers=None):
        try:
            body = json.dumps(data, cls=CustomJSONEncoder).encode("utf-8")
        except Exception as e:
            body = json.dumps({"success": False, "message": "JSON Encode Error", "error": str(e)}).encode("utf-8")
            status_code = 500
            
        try:
            self.send_response(status_code)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Session-Token")
            if headers:
                for k, v in headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Session-Token")
        self.end_headers()

    def serve_static_file(self, rel_path):
        clean_path = rel_path.split("?")[0].lstrip("/")
        if not clean_path:
            clean_path = "index.html"
            
        # Secure Path Normalization (Prevent directory traversal)
        clean_path = clean_path.replace("\\", "/")
        if ".." in clean_path.split("/"):
            self.send_response(403)
            self.end_headers()
            return

        full_path = os.path.normpath(os.path.join(FRONTEND_DIR, clean_path))
        frontend_norm = os.path.normpath(FRONTEND_DIR)
        if not full_path.startswith(frontend_norm + os.sep) and full_path != frontend_norm:
            self.send_response(403)
            self.end_headers()
            return

        if not os.path.exists(full_path) or os.path.isdir(full_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>404 Not Found</h1><p>File not found.</p>")
            return

        ext = os.path.splitext(full_path)[1].lower()
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".pdf": "application/pdf"
        }
        content_type = content_types.get(ext, "application/octet-stream")

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            try:
                self.send_response(500)
                self.end_headers()
            except Exception:
                pass

    def _safe_handle(self, method):
        try:
            from router import handle_request
            handle_request(method, self)
        except Exception as e:
            try:
                self._send_json({"success": False, "message": "Internal Server Error"}, 500)
            except:
                pass

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/" or path == "/index.html":
            return self.serve_static_file("index.html")

        if not path.startswith("/api/"):
            return self.serve_static_file(path)

        self._safe_handle("GET")

    def do_POST(self):
        self._safe_handle("POST")

    def do_PUT(self):
        self._safe_handle("PUT")
        
    def do_DELETE(self):
        self._safe_handle("DELETE")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

def main(port=PORT):
    init_db()
    print("==================================================")
    print("College ERP System - Secure Python Backend Server")
    print(f"Running at: http://localhost:{port}")
    print(f"Serving frontend from: {FRONTEND_DIR}")
    print("==================================================")
    try:
        with ThreadedHTTPServer(("", port), ERPRequestHandler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down ERP Python server...")
    except Exception as e:
        print(f"Port binding error on {port}: {e}")

if __name__ == "__main__":
    main()

