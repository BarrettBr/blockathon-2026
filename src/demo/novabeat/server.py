#!/usr/bin/env python3
"""NovaBeat vendor demo server — serves static files and proxies API calls to EquiPay."""

import json
import mimetypes
import os
import socket
import sys
import threading
import urllib.request
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EQUIPAY_BASE = os.getenv("EQUIPAY_BASE_URL", "http://127.0.0.1:8000/api/v1")
PORT = int(os.getenv("NOVA_DEMO_PORT", "7777"))
HOST = os.getenv("NOVA_DEMO_HOST", "127.0.0.1")
STATIC_DIR = Path(__file__).parent


def _claim_cycle(subscription_id: int, cycle_id: int, vendor_secret: str, vendor_seed: str) -> None:
    claim_url = f"{EQUIPAY_BASE}/subscriptions/{subscription_id}/cycles/{cycle_id}/claim"
    claim_body = json.dumps({"vendor_seed": vendor_seed}).encode("utf-8")
    try:
        req = urllib.request.Request(
            claim_url,
            data=claim_body,
            headers={
                "Content-Type": "application/json",
                "X-Vendor-Secret": vendor_secret,
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            resp.read()
        print(f"  Claimed cycle {cycle_id} for subscription {subscription_id}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(
            f"  Failed to claim cycle {cycle_id} for subscription {subscription_id}: "
            f"HTTP {exc.code} {detail}",
            file=sys.stderr,
        )
    except Exception as exc:
        print(
            f"  Failed to claim cycle {cycle_id} for subscription {subscription_id}: {exc}",
            file=sys.stderr,
        )


def _is_port_available(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _pick_port(host: str, preferred_port: int, max_tries: int = 20) -> int:
    for port in range(preferred_port, preferred_port + max_tries):
        if _is_port_available(host, port):
            return port
    raise RuntimeError(
        f"No free port found for {host} in range {preferred_port}-{preferred_port + max_tries - 1}"
    )


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
        if self.path.startswith("/webhook"):
            self._handle_vendor_webhook()
            return

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

    def _read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def _json_response(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            print(f"  Response client disconnected for {self.path}", file=sys.stderr)

    def _handle_vendor_webhook(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query or "")
        vendor_secret = (query.get("vendor_secret") or [""])[0].strip()
        vendor_seed = (query.get("vendor_seed") or [""])[0].strip()
        payload = self._read_json_body()

        event = str(payload.get("event") or "")
        if event not in {"subscription.approved", "subscription.cycle_created"}:
            self._json_response(200, {"ok": True, "message": "Event ignored", "event": event})
            return

        subscription_id = payload.get("subscription_id")
        cycle_id = payload.get("cycle_id")
        if not subscription_id or not cycle_id:
            self._json_response(
                400,
                {"ok": False, "error": "Missing subscription_id/cycle_id in webhook payload"},
            )
            return
        if not vendor_secret or not vendor_seed:
            self._json_response(
                400,
                {"ok": False, "error": "Missing vendor_secret/vendor_seed in webhook URL"},
            )
            return

        self._json_response(
            200,
            {
                "ok": True,
                "message": "Webhook received, vendor claim queued",
                "event": event,
                "subscription_id": subscription_id,
                "cycle_id": cycle_id,
            },
        )
        threading.Thread(
            target=_claim_cycle,
            args=(int(subscription_id), int(cycle_id), vendor_secret, vendor_seed),
            daemon=True,
        ).start()


if __name__ == "__main__":
    chosen_port = _pick_port(HOST, PORT)
    if chosen_port != PORT:
        print(f"  Port {PORT} is in use, using {chosen_port} instead.")

    server = ThreadingHTTPServer((HOST, chosen_port), Handler)
    print(f"\n  NovaBeat vendor demo")
    print(f"  → http://{HOST}:{chosen_port}")
    print(f"  → Proxying API calls to {EQUIPAY_BASE}")
    print(f"  → Serving files from {STATIC_DIR}")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
