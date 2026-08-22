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


class _PersistentAuditHandler(logging.FileHandler):
    """A FileHandler tagged with its own path, kept across configure_audit_logging() calls.

    A plain FileHandler has no such attribute (hence a dedicated subclass
    instead of setting an ad-hoc attribute on a base FileHandler instance).
    """

    def __init__(self, path: Path, *, encoding: str = "utf-8") -> None:
        super().__init__(path, encoding=encoding)
        self.maxconn_path = path


def configure_audit_logging(
    *,
    stream: TextIO | None = None,
    json: bool = False,
    level: int = logging.INFO,
) -> logging.Logger:
    logger = logging.getLogger("maxconn.audit")
    logger.handlers = [h for h in logger.handlers if isinstance(h, _PersistentAuditHandler)]
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
        if isinstance(existing, _PersistentAuditHandler) and existing.maxconn_path == resolved:
            return logger

    resolved.parent.mkdir(parents=True, exist_ok=True)
    handler = _PersistentAuditHandler(resolved)
    handler.setFormatter(JsonAuditFormatter())
    logger.addHandler(handler)
    if logger.level == logging.NOTSET or logger.level > level:
        logger.setLevel(level)
    logger.propagate = False
    return logger
