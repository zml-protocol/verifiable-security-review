"""Stub auth service and header-echoing upstream for the Caddy truth probe.

auth (port A): 200 for every request. It adds X-User-ID: alice only when the
original URI (X-Forwarded-Uri) starts with /with-id; otherwise it omits it.
upstream (port U): echoes the X-User-ID header values it received as JSON.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Auth(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        if self.headers.get("X-Forwarded-Uri", "").startswith("/with-id"):
            self.send_header("X-User-ID", "alice")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class Upstream(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"x_user_id": self.headers.get_all("X-User-ID") or []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


auth_port, upstream_port = int(sys.argv[1]), int(sys.argv[2])
servers = [ThreadingHTTPServer(("127.0.0.1", auth_port), Auth),
           ThreadingHTTPServer(("127.0.0.1", upstream_port), Upstream)]
for s in servers:
    threading.Thread(target=s.serve_forever, daemon=True).start()
print("ready", flush=True)
threading.Event().wait()
