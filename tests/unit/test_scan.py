from __future__ import annotations

import socket
import threading

from maxconn.net import scan


def _start_tcp_server() -> tuple[socket.socket, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def accept_once() -> None:
        conn, _addr = server.accept()
        conn.close()
        server.close()

    threading.Thread(target=accept_once, daemon=True).start()
    return server, port


def _unused_tcp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_scan_reports_open_and_closed_tcp_ports():
    _server, open_port = _start_tcp_server()
    closed_port = _unused_tcp_port()

    results = scan("127.0.0.1", ports=[open_port, closed_port], timeout=0.5, concurrency=2)

    by_port = {result.port: result for result in results}
    assert by_port[open_port].open is True
    assert by_port[closed_port].open is False
    assert by_port[open_port].host == "127.0.0.1"
    assert by_port[open_port].elapsed >= 0


def test_scan_rejects_invalid_ports():
    try:
        scan("127.0.0.1", ports=[0])
    except ValueError as exc:
        assert "port must be between 1 and 65535" in str(exc)
    else:
        raise AssertionError("scan should reject port 0")
