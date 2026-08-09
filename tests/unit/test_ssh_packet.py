from maxconn.transport.ssh.packet import decode_binary_packet, encode_binary_packet


def test_encode_pads_to_block_size_multiple():
    payload = b"hello"
    packet = encode_binary_packet(payload, block_size=8, random_bytes=lambda n: b"\x00" * n)
    packet_length = int.from_bytes(packet[:4], "big")
    # length field covers padding_length(1) + payload + padding, not itself
    assert len(packet) == 4 + packet_length
    # RFC 4253 §6: the 4-byte length field itself counts toward the multiple.
    assert len(packet) % 8 == 0


def test_encode_padding_length_is_at_least_four():
    packet = encode_binary_packet(b"", block_size=8, random_bytes=lambda n: b"\x00" * n)
    padding_length = packet[4]
    assert padding_length >= 4


def test_encode_decode_round_trip():
    payload = b"the quick brown fox"
    packet = encode_binary_packet(payload, block_size=8, random_bytes=lambda n: b"\xaa" * n)

    reader_state = {"data": packet}

    def read_exact(n: int) -> bytes:
        chunk = reader_state["data"][:n]
        reader_state["data"] = reader_state["data"][n:]
        return chunk

    decoded = decode_binary_packet(read_exact)
    assert decoded == payload


def test_encode_decode_round_trip_empty_payload():
    packet = encode_binary_packet(b"", block_size=8, random_bytes=lambda n: b"\x00" * n)

    reader_state = {"data": packet}

    def read_exact(n: int) -> bytes:
        chunk = reader_state["data"][:n]
        reader_state["data"] = reader_state["data"][n:]
        return chunk

    assert decode_binary_packet(read_exact) == b""


def test_encode_decode_round_trip_large_block_size():
    payload = b"x" * 37
    packet = encode_binary_packet(payload, block_size=16, random_bytes=lambda n: b"\x55" * n)

    reader_state = {"data": packet}

    def read_exact(n: int) -> bytes:
        chunk = reader_state["data"][:n]
        reader_state["data"] = reader_state["data"][n:]
        return chunk

    assert decode_binary_packet(read_exact) == payload
    assert len(packet) % 16 == 0
