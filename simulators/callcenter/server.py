"""Simulador HTTP simples para uma integração com call center."""

from __future__ import annotations

import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


CALL_CENTER_NAME = os.getenv("CALL_CENTER_NAME", "Call Center")
CALL_CENTER_ID = os.getenv("CALL_CENTER_ID", "call-center")
PORT = int(os.getenv("PORT", "8100"))
DELIVERY_DB_PATH = os.getenv("DELIVERY_DB_PATH", "/data/deliveries.sqlite3")


def open_delivery_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DELIVERY_DB_PATH) or ".", exist_ok=True)
    connection = sqlite3.connect(DELIVERY_DB_PATH)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS accepted_deliveries "
        "(event_id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, accepted_at TEXT NOT NULL)"
    )
    connection.commit()
    return connection


def accepted_delivery_count() -> int:
    with open_delivery_db() as connection:
        return connection.execute("SELECT COUNT(*) FROM accepted_deliveries").fetchone()[0]


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
                "acceptedCount": accepted_delivery_count(),
            },
        )

    def do_POST(self) -> None:
        if self.path != "/leads":
            self._send_json(404, {"error": "not_found"})
            return

        lead = self._read_lead()
        if lead is None:
            return

        event_id = lead.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            self._send_json(400, {"error": "event_id_is_required"})
            return
        lead_id = lead["lead_id"].strip()
        with open_delivery_db() as connection:
            inserted = connection.execute(
                "INSERT OR IGNORE INTO accepted_deliveries(event_id, lead_id, accepted_at) "
                "VALUES (?, ?, datetime('now'))",
                (event_id.strip(), lead_id),
            ).rowcount == 1
            connection.commit()
        print(f"[{CALL_CENTER_NAME}] {'received' if inserted else 'deduplicated'} lead {lead_id} event {event_id}", flush=True)
        self._send_json(
            200,
            {
                "status": "accepted",
                "duplicate": not inserted,
                "call_center": CALL_CENTER_NAME,
                "call_center_id": CALL_CENTER_ID,
                "lead_id": lead_id,
                "event_id": event_id,
            },
        )

    def do_DELETE(self) -> None:
        if self.path != "/deliveries":
            self._send_json(404, {"error": "not_found"})
            return

        with open_delivery_db() as connection:
            deleted = connection.execute("DELETE FROM accepted_deliveries").rowcount
            connection.commit()
        self._send_json(200, {"status": "ok", "deleted": deleted})

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
