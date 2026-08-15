"""Shared secret-redaction used before writing a command to any log or
history file (maxconn.audit logging, history.py's HistoryStore).

Kept in one place on purpose: this exact pattern set was fixed once in
history.py (to also catch the "--flag=value" equals-sign form and
credentials embedded in a URL) and then found to still be broken, as a
separate unfixed copy, in transport/base.py's audit logging - a second
copy is how that class of bug comes back.
"""

from __future__ import annotations

import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|secret|token|key)\s+\S+"),
    # Matches both space-separated ("--password X") and equals-sign
    # ("--password=X") flag forms - argparse accepts both, so redaction
    # must too.
    re.compile(r"(?i)(--password|--passwd|--secret|--token|--key)(?:=|\s+)\S+"),
)
# scheme://user:PASSWORD@host - only the credential between ":" and "@" is
# redacted, so the username/host stay visible for context.
_URL_CREDENTIAL_PATTERN = re.compile(r"([a-zA-Z][\w+.-]*://[^\s:/@]+:)([^\s@]+)(@)")


def redact(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)} <redacted>", redacted)
    redacted = _URL_CREDENTIAL_PATTERN.sub(lambda match: f"{match.group(1)}<redacted>{match.group(3)}", redacted)
    return redacted
