from __future__ import annotations

import http.server
import threading

from maxconn.protocol.http import HTTPClient


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"hello from maxconn")

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(201)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"posted:" + body)

    def log_message(self, format: str, *args: object) -> None:
        return None


def _serve() -> tuple[http.server.HTTPServer, str]:
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    return server, url


def test_http_client_get_parses_status_headers_and_text():
    server, url = _serve()
    try:
        response = HTTPClient(timeout=1.0).get(url)
    finally:
        server.shutdown()

    assert response.status_code == 200
    assert response.reason == "OK"
    assert response.headers["content-type"] == "text/plain"
    assert response.text == "hello from maxconn"
    assert response.ok is True


def test_http_client_post_sends_body_and_headers():
    server, url = _serve()
    try:
        response = HTTPClient(timeout=1.0).post(
            url,
            body=b"payload",
            headers={"X-Test": "1"},
        )
    finally:
        server.shutdown()

    assert response.status_code == 201
    assert response.text == "posted:payload"
