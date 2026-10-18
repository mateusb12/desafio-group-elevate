import unittest
import json
from urllib.error import HTTPError
from urllib.request import urlopen

from shared.health_server import HealthServer


class HealthServerTests(unittest.TestCase):
    def test_health_endpoint_reports_liveness_without_dependencies(self):
        server = HealthServer("127.0.0.1", 0)
        server.start()
        self.addCleanup(server.stop)
        port = server._server.server_address[1]

        with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {"status": "ok"})

    def test_unknown_path_is_not_a_health_response(self):
        server = HealthServer("127.0.0.1", 0)
        server.start()
        self.addCleanup(server.stop)
        port = server._server.server_address[1]

        with self.assertRaises(HTTPError) as error:
            urlopen(f"http://127.0.0.1:{port}/", timeout=1)
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
