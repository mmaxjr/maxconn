"""Small expect-style command runner for prompt-based CLIs."""

from __future__ import annotations

import time
from enum import Enum
from typing import Protocol

from maxconn.exceptions import ConnectionTimeoutError


class PromptProfile(Enum):
    GENERIC = ("generic", (">", "#"))
    CISCO = ("cisco", (">", "#"))
    HUAWEI = ("huawei", ("<", ">", "]"))

    @property
    def markers(self) -> tuple[str, ...]:
        return self.value[1]


class ExpectConnection(Protocol):
    def send(self, data: bytes | str) -> None: ...

    def recv(self, timeout: float | None = None) -> bytes: ...


class ExpectSession:
    def __init__(
        self,
        connection: ExpectConnection,
        *,
        prompt_markers: tuple[str, ...] | PromptProfile,
        pagination_markers: tuple[str, ...] = (),
    ) -> None:
        self._connection = connection
        self._prompt_markers = (
            prompt_markers.markers if isinstance(prompt_markers, PromptProfile) else prompt_markers
        )
        self._pagination_markers = pagination_markers

    def run(self, command: str, *, timeout: float = 10.0, strip_echo: bool = False) -> str:
        self._connection.send(command + "\n")
        output = self._read_until_prompt(timeout)
        if strip_echo:
            output = self._strip_command_echo(output, command)
        return output

    def _read_until_prompt(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        buffer = ""
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                chunk = self._connection.recv(timeout=max(remaining, 0.01))
            except ConnectionTimeoutError as exc:
                raise ConnectionTimeoutError(
                    f"Timed out waiting for prompt {self._prompt_markers!r}; got: {buffer!r}"
                ) from exc

            buffer += chunk.decode(errors="replace")
            buffer = self._answer_pagination(buffer)
            if any(marker in buffer for marker in self._prompt_markers):
                return buffer

        raise ConnectionTimeoutError(
            f"Timed out waiting for prompt {self._prompt_markers!r}; got: {buffer!r}"
        )

    def _answer_pagination(self, buffer: str) -> str:
        for marker in self._pagination_markers:
            if marker in buffer:
                self._connection.send(" ")
                buffer = buffer.replace(marker, "")
        return buffer

    @staticmethod
    def _strip_command_echo(output: str, command: str) -> str:
        normalized_command = command.strip()
        for separator in ("\r\n", "\n"):
            prefix = normalized_command + separator
            if output.startswith(prefix):
                return output[len(prefix) :]
        return output
