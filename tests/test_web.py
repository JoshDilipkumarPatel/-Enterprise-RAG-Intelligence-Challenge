import json
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import enterprise_rag.web.server as server_module
from enterprise_rag.pipeline import EnterpriseRagPipeline


class WebApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        server_module._pipeline = EnterpriseRagPipeline(Path("data"))
        cls.server = HTTPServer(("127.0.0.1", 0), server_module._Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_health_endpoint(self) -> None:
        response = self._get_json("/api/health")

        self.assertEqual(response, {"status": "ok"})

    def test_users_endpoint_returns_login_choices(self) -> None:
        response = self._get_json("/api/users")

        self.assertIn("alice", response)
        self.assertIn("frank", response)
        self.assertEqual(response["frank"]["roles"], ["Compliance Officer"])

    def test_query_endpoint_returns_answer_payload(self) -> None:
        response = self._post_json(
            "/api/query",
            {
                "user_id": "frank",
                "query": "What is the GDPR compliance assessment status?",
            },
        )

        self.assertIn("GDPR", response["answer"])
        self.assertGreater(response["confidence"], 0)
        self.assertTrue(response["citations"])
        self.assertIn(response["answer_strategy"], {"single_source", "multi_source"})
        self.assertIn("trace", response)
        self.assertIn("timings_ms", response["trace"])

    def test_query_endpoint_enforces_rbac(self) -> None:
        response = self._post_json(
            "/api/query",
            {
                "user_id": "alice",
                "query": "What did the penetration test find?",
            },
        )

        blocked_titles = [
            item["title"] for item in response["trace"]["blocked_documents"]
        ]
        self.assertIn("Security Penetration Test Report", blocked_titles)
        self.assertTrue(response["trace"]["sensitivity_filter_applied"])

    def test_query_endpoint_rejects_unknown_user(self) -> None:
        with self.assertRaises(HTTPError) as context:
            self._post_json(
                "/api/query",
                {"user_id": "unknown", "query": "What is the GDPR status?"},
            )

        self.assertEqual(context.exception.code, 404)

    def test_query_endpoint_rejects_invalid_json(self) -> None:
        request = Request(
            self._url("/api/query"),
            data=b"{not-json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=5)

        self.assertEqual(context.exception.code, 400)

    def test_static_server_blocks_path_traversal(self) -> None:
        with self.assertRaises(HTTPError) as context:
            urlopen(self._url("/../server.py"), timeout=5)

        self.assertEqual(context.exception.code, 404)

    def _get_json(self, path: str) -> dict:
        with urlopen(self._url(path), timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self._url(path),
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"


if __name__ == "__main__":
    unittest.main()
