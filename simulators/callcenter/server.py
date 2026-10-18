"""Small HTTP simulator for a call center integration."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


CALL_CENTER_NAME = os.getenv("CALL_CENTER_NAME", "Call Center")
CALL_CENTER_ID = os.getenv("CALL_CENTER_ID", "call-center")
PORT = int(os.getenv("PORT", "8100"))


def response_payload(**values: Any) -> bytes:
    return json.dumps(values, ensure_ascii=False).encode("utf-8")


class CallCenterHandler(BaseHTTPRequestHandler):
    server_version = "ElevateCallCenterSimulator/1.0"

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_json(404, {"error": "not_found"})
            return

        self._send_json(
            200,
            {
                "status": "ok",
                "call_center": CALL_CENTER_NAME,
                "call_center_id": CALL_CENTER_ID,
            },
        )

    def do_POST(self) -> None:
        if self.path != "/leads":
            self._send_json(404, {"error": "not_found"})
            return

        lead = self._read_lead()
        if lead is None:
            return

        lead_id = lead["lead_id"].strip()
        print(
            f"[{CALL_CENTER_NAME}] received lead {lead_id}",
            flush=True,
        )
        self._send_json(
            200,
            {
                "status": "accepted",
                "call_center": CALL_CENTER_NAME,
                "call_center_id": CALL_CENTER_ID,
                "lead_id": lead_id,
            },
        )

    def _read_lead(self) -> dict[str, Any] | None:
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            self._send_json(400, {"error": "request_body_must_be_json"})
            return None

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return None

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "payload_must_be_an_object"})
            return None

        lead_id = payload.get("lead_id")
        if not isinstance(lead_id, str) or not lead_id.strip():
            self._send_json(400, {"error": "lead_id_is_required"})
            return None

        return payload

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = response_payload(**payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the standard access log, which contains only method/path/status.
        super().log_message(format, *args)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), CallCenterHandler)
    print(
        f"{CALL_CENTER_NAME} ({CALL_CENTER_ID}) simulator listening on port {PORT}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
