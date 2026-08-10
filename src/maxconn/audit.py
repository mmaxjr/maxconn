from __future__ import annotations

import json
import logging
from typing import TextIO


class JsonAuditFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key in ("host", "protocol", "command", "elapsed", "ok"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, sort_keys=True)


def configure_audit_logging(
    *,
    stream: TextIO | None = None,
    json: bool = False,
    level: int = logging.INFO,
) -> logging.Logger:
    logger = logging.getLogger("maxconn.audit")
    logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(stream)
    if json:
        handler.setFormatter(JsonAuditFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    return logger
