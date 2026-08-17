from __future__ import annotations

import json
import logging
from pathlib import Path
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
    logger.handlers = [h for h in logger.handlers if getattr(h, "_maxconn_persistent", False)]
    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(stream)
    if json:
        handler.setFormatter(JsonAuditFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    return logger


def enable_persistent_audit_log(path: str | Path, *, level: int = logging.INFO) -> logging.Logger:
    """Add a JSONL file handler to the audit logger, kept across configure_audit_logging() calls.

    Idempotent for a given path - calling it again does not add a duplicate handler.
    """
    logger = logging.getLogger("maxconn.audit")
    resolved = Path(path)
    for existing in logger.handlers:
        if getattr(existing, "_maxconn_persistent", False) and getattr(existing, "_maxconn_path", None) == resolved:
            return logger

    resolved.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(resolved, encoding="utf-8")
    handler.setFormatter(JsonAuditFormatter())
    handler._maxconn_persistent = True
    handler._maxconn_path = resolved
    logger.addHandler(handler)
    if logger.level == logging.NOTSET or logger.level > level:
        logger.setLevel(level)
    logger.propagate = False
    return logger
