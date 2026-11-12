

import pytest

from reliable_udp.protocol import MessageType, Packet, ProtocolError, encode_packet
from reliable_udp.transport import make_ack, send_with_ack

TRANSFER_ID = bytes(range(16))
PEER = ("127.0.0.1", 9000)
OTHER_PEER = ("127.0.0.1", 9001)


def start_packet():
    return Packet(MessageType.START, TRANSFER_ID, 0, b"metadata")


def ack_for(packet):
    return encode_packet(make_ack(packet))


class FakeSocket:
    """Small fake UDP socket for deterministic unit tests."""

    def __init__(self, incoming=()):
        self.incoming = list(incoming)
        self.sent = []
        self.timeouts = []

    def sendto(self, data, address):
        self.sent.append((data, address))

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recvfrom(self, _buffer_size):
        if not self.incoming:
            raise TimeoutError

        item = self.incoming.pop(0)
        if isinstance(item, Exception):
            raise item

        return item


def test_make_ack_preserves_transfer_and_sequence():
    packet = start_packet()

    ack = make_ack(packet)

    assert ack.message_type == MessageType.ACK
    assert ack.transfer_id == packet.transfer_id
    assert ack.sequence == packet.sequence
    assert ack.payload == bytes((MessageType.START,))


def test_make_ack_rejects_unsupported_message_type():
    packet = Packet(MessageType.ACK, TRANSFER_ID, 0, b"")

    with pytest.raises(ProtocolError):
        make_ack(packet)


def test_successful_handshake_on_first_attempt():
    packet = start_packet()
    sock = FakeSocket([(ack_for(packet), PEER)])

    attempts = send_with_ack(sock, packet, PEER, timeout=0.1)

    assert attempts == 1
    assert len(sock.sent) == 1
    assert sock.sent[0][1] == PEER


def test_ignores_wrong_source_and_mismatched_ack():
    packet = start_packet()
    wrong_sequence = encode_packet(
        Packet(MessageType.ACK, TRANSFER_ID, 1, bytes((MessageType.START,)))
    )
    wrong_message = encode_packet(
        Packet(MessageType.ACK, TRANSFER_ID, 0, bytes((MessageType.DATA,)))
    )
    sock = FakeSocket(
        [
            (ack_for(packet), OTHER_PEER),
            (wrong_sequence, PEER),
            (wrong_message, PEER),
            (ack_for(packet), PEER),
        ]
    )

    attempts = send_with_ack(sock, packet, PEER, timeout=0.1)

    assert attempts == 1


def test_ignores_malformed_datagram():
    packet = start_packet()
    sock = FakeSocket([(b"bad", PEER), (ack_for(packet), PEER)])

    attempts = send_with_ack(sock, packet, PEER, timeout=0.1)

    assert attempts == 1


def test_retransmits_after_timeout():
    packet = start_packet()
    sock = FakeSocket([TimeoutError(), (ack_for(packet), PEER)])

    attempts = send_with_ack(
        sock,
        packet,
        PEER,
        timeout=0.1,
        max_retransmissions=2,
    )

    assert attempts == 2
    assert len(sock.sent) == 2


def test_fails_after_retry_limit():
    packet = start_packet()
    sock = FakeSocket([TimeoutError(), TimeoutError(), TimeoutError()])

    with pytest.raises(TimeoutError, match="3 transmission attempts"):
        send_with_ack(
            sock,
            packet,
            PEER,
            timeout=0.1,
            max_retransmissions=2,
        )

    assert len(sock.sent) == 3


def test_rejects_end_packet():
    packet = Packet(MessageType.END, TRANSFER_ID, 0, b"")

    with pytest.raises(ProtocolError):
        send_with_ack(FakeSocket(), packet, PEER)


def test_rejects_nonpositive_timeout():
    with pytest.raises(ValueError, match="timeout"):
        send_with_ack(FakeSocket(), start_packet(), PEER, timeout=0)


def test_rejects_negative_retransmission_count():
    with pytest.raises(ValueError, match="max_retransmissions"):
        send_with_ack(
            FakeSocket(),
            start_packet(),
            PEER,
            max_retransmissions=-1,
        )
