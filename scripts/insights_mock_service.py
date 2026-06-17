#!/usr/bin/env python3
"""Minimal stand-in HTTP service for the Insights agent demo.

Models the FloQast reconciliations/close-tasks style endpoints and returns
realistic JSON, so the Postman Insights agent has plausible API traffic to
observe and characterize. No real data, no external calls - safe mock traffic.

Run: python3 scripts/insights_mock_service.py 8080
"""
import json
import random
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

STATUSES = ["open", "in_review", "approved", "rejected"]


def sample(path: str):
    if path.rstrip("/").endswith("reconciliations") or "/reconciliations" in path:
        return {
            "id": f"rec_{random.randint(1000,9999)}",
            "account_name": random.choice(["Cash - Operating", "Accounts Payable", "Prepaid Expenses"]),
            "period": "2026-05",
            "gl_balance": random.randint(10000, 9000000),
            "supporting_balance": random.randint(10000, 9000000),
            "status": random.choice(STATUSES),
            "updated_at": "2026-06-17T05:00:00Z",
        }
    if "/close-tasks" in path:
        return {
            "id": f"task_{random.randint(1000,9999)}",
            "name": random.choice(["Bank rec", "Accruals", "FX revaluation"]),
            "status": random.choice(["not_started", "in_progress", "complete"]),
            "due_date": "2026-06-30",
        }
    return {"ok": True, "path": path}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        item = sample(self.path)
        if self.path.rstrip("/").endswith(("reconciliations", "close-tasks")):
            self._send(200, {"data": [item, sample(self.path)], "next_cursor": None})
        else:
            self._send(200, item)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)
        self._send(201, sample(self.path))

    def log_message(self, *args):  # quiet
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
