#!/usr/bin/env python3
"""NovaBeat vendor demo server — serves static files and proxies API calls to EquiPay."""

import json
import mimetypes
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

EQUIPAY_BASE = "http://localhost:8000/api/v1"
PORT = 7777
STATIC_DIR = Path(__file__).parent


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"  {self.command} {self.path} → {args[0]}")

    def do_GET(self):
        # Serve static files
        path = self.path.split("?")[0]
        if path == "/":
            path = "/index.html"

        file_path = STATIC_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            mime, _ = mimetypes.guess_type(str(file_path))
            self.send_response(200)
            self.send_header("Content-Type", mime or "text/plain")
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if not self.path.startswith("/proxy/"):
            self.send_response(404)
            self.end_headers()
            return

        api_path = self.path[len("/proxy"):]
        target_url = EQUIPAY_BASE + api_path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        forward_headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
        }
        vendor_secret = self.headers.get("X-Vendor-Secret")
        if vendor_secret:
            forward_headers["X-Vendor-Secret"] = vendor_secret

        try:
            req = urllib.request.Request(
                target_url, data=body, headers=forward_headers, method="POST"
            )
            with urllib.request.urlopen(req) as resp:
                response_body = resp.read()
                status = resp.getcode()
        except urllib.error.HTTPError as e:
            response_body = e.read()
            status = e.code
        except Exception as e:
            body = json.dumps({"detail": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response_body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Vendor-Secret")
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"\n  NovaBeat vendor demo")
    print(f"  → http://localhost:{PORT}")
    print(f"  → Proxying API calls to {EQUIPAY_BASE}")
    print(f"  → Serving files from {STATIC_DIR}")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
