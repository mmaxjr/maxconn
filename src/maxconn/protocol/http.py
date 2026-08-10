from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    reason: str
    headers: dict[str, str]
    body: bytes

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def text(self) -> str:
        content_type = self.headers.get("content-type", "")
        encoding = "utf-8"
        if "charset=" in content_type:
            encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
        return self.body.decode(encoding, errors="replace")


class HTTPClient:
    def __init__(self, *, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> HTTPResponse:
        return self.request("GET", url, headers=headers)

    def post(
        self,
        url: str,
        *,
        body: bytes | str = b"",
        headers: dict[str, str] | None = None,
    ) -> HTTPResponse:
        payload = body.encode() if isinstance(body, str) else body
        return self.request("POST", url, body=payload, headers=headers)

    def request(
        self,
        method: str,
        url: str,
        *,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> HTTPResponse:
        target = _Target.from_url(url)
        request = _build_request(method, target, body=body, headers=headers or {})
        with socket.create_connection((target.host, target.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            if target.scheme == "https":
                context = ssl.create_default_context()
                with context.wrap_socket(sock, server_hostname=target.host) as tls_sock:
                    tls_sock.sendall(request)
                    raw = _read_response(tls_sock)
            else:
                sock.sendall(request)
                raw = _read_response(sock)
        return _parse_response(raw)


@dataclass(frozen=True)
class _Target:
    scheme: str
    host: str
    port: int
    path: str

    @classmethod
    def from_url(cls, url: str) -> _Target:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("url scheme must be http or https")
        if not parsed.hostname:
            raise ValueError("url must include a host")
        default_port = 443 if parsed.scheme == "https" else 80
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return cls(
            scheme=parsed.scheme,
            host=parsed.hostname,
            port=parsed.port or default_port,
            path=path,
        )


def _build_request(
    method: str,
    target: _Target,
    *,
    body: bytes,
    headers: dict[str, str],
) -> bytes:
    outgoing_headers = {
        "Host": target.host if target.port in {80, 443} else f"{target.host}:{target.port}",
        "User-Agent": "maxconn",
        "Connection": "close",
        **headers,
    }
    if body:
        outgoing_headers["Content-Length"] = str(len(body))
    lines = [f"{method.upper()} {target.path} HTTP/1.1"]
    lines.extend(f"{name}: {value}" for name, value in outgoing_headers.items())
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body


def _read_response(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _parse_response(raw: bytes) -> HTTPResponse:
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1").split("\r\n")
    version, status, reason = lines[0].split(" ", 2)
    if not version.startswith("HTTP/"):
        raise ValueError("invalid HTTP response")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return HTTPResponse(status_code=int(status), reason=reason, headers=headers, body=body)
