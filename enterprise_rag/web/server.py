"""Lightweight HTTP server for the Enterprise RAG web dashboard."""

from __future__ import annotations

import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from enterprise_rag.pipeline import EnterpriseRagPipeline

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Will be set by ``start_server`` before the server starts.
_pipeline: EnterpriseRagPipeline | None = None


class _Handler(SimpleHTTPRequestHandler):

    def do_GET(self) -> None:
        if self.path == "/api/users":
            self._json_response(self._get_pipeline().get_users())
            return
        if self.path == "/api/health":
            self._json_response({"status": "ok"})
            return
        # Serve static files
        self._serve_static()

    def do_POST(self) -> None:
        if self.path == "/api/query":
            try:
                body = self._read_json_body()
            except ValueError as exc:
                self._json_response({"error": str(exc)}, status=400)
                return
            user_id = body.get("user_id", "")
            query = body.get("query", "")
            if not user_id or not query:
                self._json_response({"error": "user_id and query are required"}, status=400)
                return
            pipeline = self._get_pipeline()
            if user_id not in pipeline.users:
                self._json_response({"error": f"Unknown user: {user_id}"}, status=404)
                return
            if not pipeline.users[user_id].roles:
                self._json_response({"error": "User has no assigned roles"}, status=403)
                return
            answer = pipeline.ask(user_id, query)
            self._json_response(_serialize_answer(answer))
            return
        self._json_response({"error": "not found"}, status=404)

    # -- helpers ---

    def _get_pipeline(self) -> EnterpriseRagPipeline:
        assert _pipeline is not None
        return _pipeline

    def _json_response(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON request body") from exc
        if not isinstance(body, dict):
            raise ValueError("JSON request body must be an object")
        return body

    def _serve_static(self) -> None:
        path = unquote(urlsplit(self.path).path).lstrip("/")
        if not path:
            path = "index.html"
        file_path = (STATIC_DIR / path).resolve()
        static_root = STATIC_DIR.resolve()
        if not _is_relative_to(file_path, static_root) or not file_path.is_file():
            self.send_error(404)
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _content_type(file_path))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt: str, *args: Any) -> None:
        # quieter logs
        pass


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }.get(suffix, "application/octet-stream")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _serialize_answer(answer) -> dict:
    """Convert a frozen RagAnswer into a JSON-safe dict."""
    return {
        "answer": answer.answer,
        "citations": list(answer.citations),
        "confidence": answer.confidence,
        "answer_strategy": answer.answer_strategy,
        "trace": {
            "intent": answer.trace.intent.value if answer.trace.intent else None,
            "routed_sources": [s.value for s in answer.trace.routed_sources],
            "route_reason": answer.trace.route_reason,
            "accessible_documents": answer.trace.accessible_documents,
            "blocked_documents": [
                {
                    "doc_id": bd.doc_id,
                    "title": bd.title,
                    "required_roles": list(bd.required_roles),
                    "reason": bd.reason,
                }
                for bd in answer.trace.blocked_documents
            ],
            "retrieval_notes": list(answer.trace.retrieval_notes),
            "sensitivity_filter_applied": answer.trace.sensitivity_filter_applied,
            "reranker_applied": answer.trace.reranker_applied,
            "timings_ms": answer.trace.timings_ms,
        },
    }


def start_server(pipeline: EnterpriseRagPipeline, port: int = 8080) -> None:
    global _pipeline
    _pipeline = pipeline
    server = HTTPServer(("0.0.0.0", port), _Handler)
    print(f"\n  Enterprise RAG Dashboard")
    print(f"  http://localhost:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
