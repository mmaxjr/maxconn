import io
import logging

import pytest

from maxconn.audit import (
    _PersistentAuditHandler,
    configure_audit_logging,
    enable_persistent_audit_log,
)


@pytest.fixture(autouse=True)
def _remove_persistent_audit_handler():
    yield
    logger = logging.getLogger("maxconn.audit")
    logger.handlers = [h for h in logger.handlers if not isinstance(h, _PersistentAuditHandler)]


def test_configure_audit_logging_can_emit_json_records():
    stream = io.StringIO()
    logger = configure_audit_logging(stream=stream, json=True)

    logger.info("command completed", extra={"host": "192.0.2.10", "ok": True})

    line = stream.getvalue()
    assert '"message": "command completed"' in line
    assert '"host": "192.0.2.10"' in line
    assert '"ok": true' in line


def test_enable_persistent_audit_log_writes_json_lines_to_a_file(tmp_path):
    path = tmp_path / "audit.jsonl"

    logger = enable_persistent_audit_log(path)
    logger.info("command completed", extra={"host": "192.0.2.10", "ok": True})
    for handler in logger.handlers:
        handler.flush()

    line = path.read_text(encoding="utf-8").strip()
    assert '"host": "192.0.2.10"' in line


def test_enable_persistent_audit_log_is_idempotent(tmp_path):
    path = tmp_path / "audit.jsonl"

    logger = enable_persistent_audit_log(path)
    enable_persistent_audit_log(path)
    logger.info("command completed", extra={"host": "192.0.2.10", "ok": True})
    for handler in logger.handlers:
        handler.flush()

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # not duplicated by a second handler


def test_configure_audit_logging_preserves_the_persistent_handler(tmp_path):
    path = tmp_path / "audit.jsonl"
    enable_persistent_audit_log(path)

    stream = io.StringIO()
    logger = configure_audit_logging(stream=stream, json=True)
    logger.info("command completed", extra={"host": "192.0.2.10", "ok": True})
    for handler in logger.handlers:
        handler.flush()

    assert '"host": "192.0.2.10"' in stream.getvalue()
    assert '"host": "192.0.2.10"' in path.read_text(encoding="utf-8")
