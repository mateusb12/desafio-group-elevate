"""Servidor HTTP mínimo para verificar se um processo está vivo."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return

        body = json.dumps(self.server.health_payload()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


class HealthServer:
    """Executa o endpoint de liveness em uma thread do processo principal."""

    def __init__(self, host: str, port: int, health_payload: Callable[[], dict] | None = None) -> None:
        self._server = ThreadingHTTPServer((host, port), _HealthHandler)
        self._server.health_payload = health_payload or (lambda: {"status": "ok"})
        self._server.daemon_threads = True
        self._thread = Thread(target=self._server.serve_forever, name="health-server", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


def start_health_server(port: int, health_payload: Callable[[], dict] | None = None) -> HealthServer:
    """Inicia um endpoint de liveness escutando em todas as interfaces."""
    server = HealthServer("0.0.0.0", port, health_payload)
    server.start()
    return server
