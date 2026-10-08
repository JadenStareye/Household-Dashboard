import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import server
from dashboard.api import App
from dashboard.store import Store


class FakeWeather:
    def get(self):
        return {"available": False}


class ServerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        recipes = {k: [{"id": f"{k}{i}", "name": "n", "description": "d", "url": "https://e.com", "minutes": 1} for i in range(5)] for k in ("chris", "v")}
        app = App(Store(Path(tmp.name) / "data.json"), [], recipes, FakeWeather())
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.port = self.httpd.server_address[1]

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_binds_localhost_only(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")
        self.assertEqual(server.HOST, "127.0.0.1")

    def test_oversized_or_negative_body_rejected_without_reading(self):
        for length in ("-5", str(server.MAX_BODY + 1)):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            conn.putrequest("POST", "/api/tasks")
            conn.putheader("Content-Length", length)
            conn.endheaders()
            self.assertEqual(conn.getresponse().status, 400)
            conn.close()

    def test_state_endpoint(self):
        status, data = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(data)["dinners"]["chris"]["picks"]), 3)

    def test_post_task(self):
        status, data = self.request("POST", "/api/tasks", {"title": "Hello"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["tasks"]["today"][0]["title"], "Hello")

    def test_malformed_json_is_400(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/tasks", "{bad", {"Content-Length": "4"})
        self.assertEqual(conn.getresponse().status, 400)

    def test_non_object_json_is_400(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/tasks", "[1]", {"Content-Length": "3"})
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()

    def test_put_and_patch_reach_app(self):
        status, data = self.request("PUT", "/api/settings", {"theme": "dark"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["settings"]["theme"], "dark")
        _, data = self.request("POST", "/api/tasks", {"title": "Hello"})
        tid = json.loads(data)["tasks"]["today"][0]["id"]
        status, data = self.request("PATCH", f"/api/tasks/{tid}", {"title": "Renamed"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["tasks"]["today"][0]["title"], "Renamed")

    def test_path_traversal_blocked(self):
        status, _ = self.request("GET", "/../server.py")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
