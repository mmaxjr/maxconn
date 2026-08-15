"""Client-side Telnet IAC option negotiation (RFC 854 / RFC 855)."""

from __future__ import annotations

from maxconn.exceptions import ProtocolError

IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240

OPT_ECHO = 1
OPT_SUPPRESS_GO_AHEAD = 3

_ACCEPTED_SERVER_WILL = {OPT_ECHO, OPT_SUPPRESS_GO_AHEAD}
_NEGOTIATION_COMMANDS = (WILL, WONT, DO, DONT)
# Real option negotiation payloads (terminal type, window size, ...) are a
# handful of bytes; a peer that never closes a subnegotiation with IAC SE
# must not be allowed to grow the buffer without bound across feed() calls.
MAX_SUBNEGOTIATION_SIZE = 4096


class TelnetNegotiator:
    """Consumes raw Telnet stream bytes, stripping and answering IAC
    option-negotiation sequences, and returns the remaining plain text.

    Policy: accepts the peer enabling ECHO and SUPPRESS-GO-AHEAD on their
    side (WILL -> DO), refuses every other WILL (-> DONT), and never
    enables options on our own side (DO -> WONT). Subnegotiation blocks
    (IAC SB ... IAC SE) are discarded without a reply.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> tuple[bytes, bytes]:
        self._buffer.extend(data)
        plain = bytearray()
        response = bytearray()

        buf = self._buffer
        i = 0
        while i < len(buf):
            if buf[i] != IAC:
                plain.append(buf[i])
                i += 1
                continue

            if i + 1 >= len(buf):
                break  # incomplete IAC sequence, wait for more data

            command = buf[i + 1]

            if command == IAC:
                plain.append(IAC)
                i += 2
                continue

            if command in _NEGOTIATION_COMMANDS:
                if i + 2 >= len(buf):
                    break  # wait for the option byte
                option = buf[i + 2]
                response.extend(self._respond(command, option))
                i += 3
                continue

            if command == SB:
                end = self._find_subnegotiation_end(buf, i)
                if end is None:
                    break  # wait for IAC SE
                i = end
                continue

            # Unrecognized command byte (NOP, DM, ...): skip IAC + command
            i += 2

        del self._buffer[:i]
        return bytes(plain), bytes(response)

    @staticmethod
    def _respond(command: int, option: int) -> bytes:
        if command == DO:
            return bytes([IAC, WONT, option])
        if command == WILL:
            if option in _ACCEPTED_SERVER_WILL:
                return bytes([IAC, DO, option])
            return bytes([IAC, DONT, option])
        return b""  # WONT / DONT need no reply

    @staticmethod
    def _find_subnegotiation_end(buf: bytearray, start: int) -> int | None:
        j = start + 2
        while j + 1 < len(buf):
            if buf[j] == IAC and buf[j + 1] == SE:
                return j + 2
            if j - start > MAX_SUBNEGOTIATION_SIZE:
                raise ProtocolError("Telnet subnegotiation exceeded maximum size without IAC SE")
            j += 1
        return None
