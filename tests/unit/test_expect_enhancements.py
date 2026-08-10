from maxconn.automation import ExpectSession


class FakeConnection:
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent = []

    def send(self, data):
        self.sent.append(data)

    def recv(self, timeout=None):
        return self._chunks.pop(0).encode()


def test_expect_confirm_answers_confirmation_prompt_then_waits_for_final_prompt():
    conn = FakeConnection(["reset? [Y/N]", "\r\nDone\r\ndevice#"])
    expect = ExpectSession(conn, prompt_markers=("#",))

    output = expect.run(
        "reset slot 1",
        timeout=1.0,
        confirmations={"[Y/N]": "Y\n"},
        strip_echo=False,
    )

    assert conn.sent == ["reset slot 1\n", "Y\n"]
    assert "Done" in output


def test_wait_for_returns_matching_marker_and_output():
    conn = FakeConnection(["booting...", "ready>"])
    expect = ExpectSession(conn, prompt_markers=(">",))

    match = expect.wait_for(("ready>", "failed"), timeout=1.0)

    assert match.marker == "ready>"
    assert match.output == "booting...ready>"
