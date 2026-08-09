from maxconn.transport.telnet.negotiation import (
    DO,
    DONT,
    IAC,
    OPT_ECHO,
    OPT_SUPPRESS_GO_AHEAD,
    WILL,
    WONT,
    TelnetNegotiator,
)


def test_plain_text_passes_through_unchanged():
    neg = TelnetNegotiator()
    plain, response = neg.feed(b"hello world")
    assert plain == b"hello world"
    assert response == b""


def test_will_echo_is_accepted_with_do():
    neg = TelnetNegotiator()
    plain, response = neg.feed(bytes([IAC, WILL, OPT_ECHO]))
    assert plain == b""
    assert response == bytes([IAC, DO, OPT_ECHO])


def test_will_suppress_go_ahead_is_accepted_with_do():
    neg = TelnetNegotiator()
    _plain, response = neg.feed(bytes([IAC, WILL, OPT_SUPPRESS_GO_AHEAD]))
    assert response == bytes([IAC, DO, OPT_SUPPRESS_GO_AHEAD])


def test_will_unsupported_option_is_refused_with_dont():
    neg = TelnetNegotiator()
    unsupported_option = 24  # TERMINAL-TYPE
    plain, response = neg.feed(bytes([IAC, WILL, unsupported_option]))
    assert plain == b""
    assert response == bytes([IAC, DONT, unsupported_option])


def test_do_any_option_is_refused_with_wont():
    neg = TelnetNegotiator()
    plain, response = neg.feed(bytes([IAC, DO, OPT_ECHO]))
    assert plain == b""
    assert response == bytes([IAC, WONT, OPT_ECHO])


def test_wont_and_dont_require_no_response():
    neg = TelnetNegotiator()
    _plain, response = neg.feed(bytes([IAC, WONT, OPT_ECHO]))
    assert response == b""
    _plain, response = neg.feed(bytes([IAC, DONT, OPT_ECHO]))
    assert response == b""


def test_escaped_iac_byte_is_preserved_as_data():
    neg = TelnetNegotiator()
    plain, response = neg.feed(bytes([IAC, IAC]))
    assert plain == bytes([IAC])
    assert response == b""


def test_negotiation_interleaved_with_text():
    neg = TelnetNegotiator()
    data = b"login: " + bytes([IAC, WILL, OPT_ECHO]) + b"more text"
    plain, response = neg.feed(data)
    assert plain == b"login: more text"
    assert response == bytes([IAC, DO, OPT_ECHO])


def test_subnegotiation_block_is_stripped():
    neg = TelnetNegotiator()
    SB, SE = 250, 240
    data = b"before" + bytes([IAC, SB, 24, 0]) + b"xterm" + bytes([IAC, SE]) + b"after"
    plain, response = neg.feed(data)
    assert plain == b"beforeafter"
    assert response == b""


def test_partial_sequence_is_buffered_across_feed_calls():
    neg = TelnetNegotiator()
    plain1, response1 = neg.feed(bytes([IAC]))
    assert plain1 == b""
    assert response1 == b""
    plain2, response2 = neg.feed(bytes([WILL, OPT_ECHO]))
    assert plain2 == b""
    assert response2 == bytes([IAC, DO, OPT_ECHO])
