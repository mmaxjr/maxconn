class MaxConnError(Exception):
    """Base exception for all maxconn errors."""


class ConnectionTimeoutError(MaxConnError):
    """Raised when a connection attempt or a read times out."""


class AuthenticationError(MaxConnError):
    """Raised when authentication with the remote host fails."""


class ProtocolError(MaxConnError):
    """Raised when a malformed or unexpected protocol message is received."""


class ChannelError(MaxConnError):
    """Raised when a channel operation fails (SSH channels)."""
