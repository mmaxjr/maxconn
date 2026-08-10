import io

from maxconn.audit import configure_audit_logging


def test_configure_audit_logging_can_emit_json_records():
    stream = io.StringIO()
    logger = configure_audit_logging(stream=stream, json=True)

    logger.info("command completed", extra={"host": "192.0.2.10", "ok": True})

    line = stream.getvalue()
    assert '"message": "command completed"' in line
    assert '"host": "192.0.2.10"' in line
    assert '"ok": true' in line
