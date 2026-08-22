"""Small expect-style command runner for prompt-based CLIs."""

from __future__ import annotations

import time
from dataclasses import dataclass
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

    # `float`, not `float | None`: passing an explicit `None` here would
    # reintroduce the "recv() blocks forever" issue that
    # transport.base.DEFAULT_RECV_TIMEOUT exists to prevent (a bare `None`
    # sets the underlying socket to blocking mode with no timeout at all).
    # Kept as a plain literal instead of importing DEFAULT_RECV_TIMEOUT to
    # avoid a circular import (transport.base imports this module).
    def recv(self, timeout: float = 30.0) -> bytes: ...


@dataclass(frozen=True)
class ExpectMatch:
    marker: str
    output: str


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

    def run(
        self,
        command: str,
        *,
        timeout: float = 10.0,
        strip_echo: bool = False,
        confirmations: dict[str, str] | None = None,
    ) -> str:
        self._connection.send(command + "\n")
        output = self._read_until_prompt(timeout, confirmations=confirmations or {})
        if strip_echo:
            output = self._strip_command_echo(output, command)
        return output

    def wait_for(self, markers: tuple[str, ...], *, timeout: float = 10.0) -> ExpectMatch:
        output = self._read_until(markers, timeout=timeout, confirmations={})
        marker = next(marker for marker in markers if marker in output)
        return ExpectMatch(marker=marker, output=output)

    def _read_until_prompt(self, timeout: float, *, confirmations: dict[str, str]) -> str:
        return self._read_until(self._prompt_markers, timeout=timeout, confirmations=confirmations)

    def _read_until(
        self,
        markers: tuple[str, ...],
        *,
        timeout: float,
        confirmations: dict[str, str],
    ) -> str:
        deadline = time.monotonic() + timeout
        buffer = ""
        answered_confirmations: set[str] = set()
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                chunk = self._connection.recv(timeout=max(remaining, 0.01))
            except ConnectionTimeoutError as exc:
                raise ConnectionTimeoutError(
                    f"Timed out waiting for prompt {markers!r}; got: {buffer!r}"
                ) from exc

            buffer += chunk.decode(errors="replace")
            buffer = self._answer_pagination(buffer)
            self._answer_confirmations(buffer, confirmations, answered_confirmations)
            if any(marker in buffer for marker in markers):
                return buffer

        raise ConnectionTimeoutError(f"Timed out waiting for prompt {markers!r}; got: {buffer!r}")

    def _answer_pagination(self, buffer: str) -> str:
        for marker in self._pagination_markers:
            if marker in buffer:
                self._connection.send(" ")
                buffer = buffer.replace(marker, "")
        return buffer

    def _answer_confirmations(
        self,
        buffer: str,
        confirmations: dict[str, str],
        answered: set[str],
    ) -> None:
        for marker, answer in confirmations.items():
            if marker in buffer and marker not in answered:
                self._connection.send(answer)
                answered.add(marker)

    @staticmethod
    def _strip_command_echo(output: str, command: str) -> str:
        normalized_command = command.strip()
        for separator in ("\r\n", "\n"):
            prefix = normalized_command + separator
            if output.startswith(prefix):
                return output[len(prefix) :]
        return output
