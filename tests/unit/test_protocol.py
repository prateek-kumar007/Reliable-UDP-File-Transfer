
import struct

import pytest

from reliable_udp.protocol import (
    HEADER_FORMAT,
    HEADER_SIZE,
    MAGIC,
    MAX_DATAGRAM_SIZE,
    MAX_PAYLOAD_SIZE,
    MessageType,
    Packet,
    ProtocolError,
    decode_packet,
    encode_packet,
)

TRANSFER_ID = bytes(range(16))


def test_packet_round_trip():
    original = Packet(MessageType.DATA, TRANSFER_ID, 7, b"hello")

    encoded = encode_packet(original)

    assert decode_packet(encoded) == original


def test_header_size_and_maximum_datagram():
    assert HEADER_SIZE == 27

    packet = Packet(
        MessageType.DATA,
        TRANSFER_ID,
        0,
        b"x" * MAX_PAYLOAD_SIZE,
    )

    encoded = encode_packet(packet)

    assert len(encoded) == MAX_DATAGRAM_SIZE
    assert decode_packet(encoded) == packet


def test_reject_payload_that_is_too_large():
    packet = Packet(
        MessageType.DATA,
        TRANSFER_ID,
        0,
        b"x" * (MAX_PAYLOAD_SIZE + 1),
    )

    with pytest.raises(ProtocolError):
        encode_packet(packet)


def test_reject_invalid_transfer_id():
    packet = Packet(MessageType.DATA, b"short", 0, b"")

    with pytest.raises(ProtocolError):
        encode_packet(packet)


def test_reject_truncated_header():
    with pytest.raises(ProtocolError):
        decode_packet(b"RFT1")


def test_reject_wrong_magic():
    valid = encode_packet(Packet(MessageType.DATA, TRANSFER_ID, 0, b"data"))
    malformed = b"BAD!" + valid[4:]

    with pytest.raises(ProtocolError, match="magic"):
        decode_packet(malformed)


def test_reject_unknown_message_type():
    malformed = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        0xFF,
        TRANSFER_ID,
        0,
        0,
    )

    with pytest.raises(ProtocolError, match="Unknown message type"):
        decode_packet(malformed)


def test_reject_incorrect_payload_length():
    valid = encode_packet(Packet(MessageType.DATA, TRANSFER_ID, 0, b"hello"))
    malformed = valid[:25] + struct.pack("!H", 4) + valid[27:]

    with pytest.raises(ProtocolError, match="payload length"):
        decode_packet(malformed)


def test_reject_oversized_datagram():
    oversized = b"x" * (MAX_DATAGRAM_SIZE + 1)

    with pytest.raises(ProtocolError, match="maximum size"):
        decode_packet(oversized)


def test_reject_sequence_number_out_of_range():
    packet = Packet(MessageType.DATA, TRANSFER_ID, 1 << 32, b"")

    with pytest.raises(ProtocolError, match="Sequence number"):
        encode_packet(packet)
