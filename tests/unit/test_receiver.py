import hashlib

import pytest

from reliable_udp.metadata import StartMetadata, encode_start_metadata
from reliable_udp.protocol import (
    MessageType,
    Packet,
    decode_packet,
    encode_packet,
)
from reliable_udp.receiver import ReceiverState

PEER = ("127.0.0.1", 9000)
OTHER_PEER = ("127.0.0.1", 9001)
TRANSFER_ID = bytes(range(16))


def valid_payload(filename="report.txt"):
    return encode_start_metadata(
        StartMetadata(
            filename=filename,
            file_size=8,
            chunk_size=1000,
            sha256=hashlib.sha256(b"filedata").digest(),
        )
    )


def start_packet(
    transfer_id=TRANSFER_ID,
    payload=None,
    sequence=0,
):
    if payload is None:
        payload = valid_payload()
    return Packet(MessageType.START, transfer_id, sequence, payload)


def send_start(state, packet, peer=PEER):
    return state.handle_datagram(encode_packet(packet), peer)


def test_accepts_first_start_and_returns_ack():
    state = ReceiverState()
    start = start_packet()

    response = send_start(state, start)

    assert response is not None
    ack = decode_packet(response)
    assert ack.message_type is MessageType.ACK
    assert ack.transfer_id == TRANSFER_ID
    assert ack.sequence == 0
    assert ack.payload == bytes((MessageType.START,))
    assert state.has_active_transfer


def test_duplicate_start_is_acknowledged_without_resetting_state():
    state = ReceiverState()
    start = start_packet()

    first_response = send_start(state, start)
    original_payload = state.start_payload
    second_response = send_start(state, start)

    assert first_response == second_response
    assert state.start_payload == original_payload


def test_ignores_start_from_different_peer():
    state = ReceiverState()
    send_start(state, start_packet())

    response = send_start(state, start_packet(), OTHER_PEER)

    assert response is None
    assert state.active_peer == PEER


def test_ignores_different_transfer_id_while_busy():
    state = ReceiverState()
    send_start(state, start_packet())

    other_id = b"\xff" * 16
    response = send_start(state, start_packet(transfer_id=other_id))

    assert response is None
    assert state.active_transfer_id == TRANSFER_ID


def test_ignores_conflicting_metadata_for_same_transfer():
    state = ReceiverState()
    send_start(state, start_packet(payload=valid_payload("original.txt")))

    response = send_start(state, start_packet(payload=valid_payload("changed.txt")))

    assert response is None
    assert state.start_payload == valid_payload("original.txt")


def test_ignores_start_with_nonzero_sequence():
    state = ReceiverState()

    response = send_start(state, start_packet(sequence=1))

    assert response is None
    assert not state.has_active_transfer


def test_ignores_non_start_messages():
    state = ReceiverState()
    data = Packet(MessageType.DATA, TRANSFER_ID, 0, b"file bytes")

    response = state.handle_datagram(encode_packet(data), PEER)

    assert response is None
    assert not state.has_active_transfer


def test_ignores_malformed_datagram():
    state = ReceiverState()

    response = state.handle_datagram(b"not a valid packet", PEER)

    assert response is None
    assert not state.has_active_transfer


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"not metadata",
        valid_payload() + b"\x00",
        b"\x00\x01\xff",
    ],
)
def test_rejects_invalid_metadata_without_activating_receiver(payload):
    state = ReceiverState()

    response = send_start(state, start_packet(payload=payload))

    assert response is None
    assert not state.has_active_transfer
    assert state.active_peer is None
    assert state.active_transfer_id is None
    assert state.start_payload is None


def test_reset_allows_a_new_transfer():
    state = ReceiverState()
    send_start(state, start_packet())

    state.reset()

    new_id = b"\xaa" * 16
    response = send_start(state, start_packet(transfer_id=new_id))

    assert response is not None
    assert state.active_transfer_id == new_id
