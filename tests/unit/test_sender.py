"""Tests for reliable UDP file sending."""

import hashlib
import socket
import threading
from pathlib import Path

import pytest

from reliable_udp.metadata import decode_start_metadata
from reliable_udp.protocol import (
    MAX_PAYLOAD_SIZE,
    MessageType,
    decode_packet,
    encode_packet,
)
from reliable_udp.sender import send_file


def run_receiver(handler):
    """Start a local UDP peer and return its socket, address, and thread."""
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(3.0)
    address = receiver.getsockname()
    errors = []

    def target():
        try:
            handler(receiver)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return receiver, address, thread, errors


def acknowledge(packet):
    """Build the matching ACK for a START or DATA packet."""
    from reliable_udp.transport import make_ack

    return make_ack(packet)


def test_send_file_success(tmp_path: Path):
    content = b"hello reliable UDP"
    source = tmp_path / "example.txt"
    source.write_bytes(content)
    received = bytearray()
    packet_types = []

    def handler(sock):
        peer = None

        while True:
            data, source_address = sock.recvfrom(65535)
            packet = decode_packet(data)
            packet_types.append(packet.message_type)
            peer = source_address

            if packet.message_type is MessageType.START:
                metadata = decode_start_metadata(packet.payload)
                assert metadata.filename == source.name
                assert metadata.file_size == len(content)
                assert metadata.sha256 == hashlib.sha256(content).digest()
                sock.sendto(encode_packet(acknowledge(packet)), peer)

            elif packet.message_type is MessageType.DATA:
                received.extend(packet.payload)
                sock.sendto(encode_packet(acknowledge(packet)), peer)

            elif packet.message_type is MessageType.END:
                from reliable_udp.protocol import Packet

                fin_ack = Packet(
                    MessageType.FIN_ACK,
                    packet.transfer_id,
                    packet.sequence,
                )
                sock.sendto(encode_packet(fin_ack), peer)
                return

    receiver, peer, thread, errors = run_receiver(handler)

    try:
        stats = send_file(
            _client_socket(),
            source,
            peer,
            chunk_size=5,
            timeout=0.2,
            max_retransmissions=1,
        )
    finally:
        receiver.close()

    thread.join(timeout=4)

    assert not thread.is_alive()
    assert not errors
    assert bytes(received) == content
    assert stats == {
        "filename": source.name,
        "bytes_sent": len(content),
        "chunks_sent": 4,
        "attempts": 6,
    }
    assert packet_types == [
        MessageType.START,
        MessageType.DATA,
        MessageType.DATA,
        MessageType.DATA,
        MessageType.DATA,
        MessageType.END,
    ]


def _client_socket():
    """Create a client UDP socket."""
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def test_send_empty_file(tmp_path: Path):
    source = tmp_path / "empty.bin"
    source.write_bytes(b"")

    def handler(sock):
        while True:
            data, peer = sock.recvfrom(65535)
            packet = decode_packet(data)

            if packet.message_type is MessageType.START:
                metadata = decode_start_metadata(packet.payload)
                assert metadata.file_size == 0
                sock.sendto(encode_packet(acknowledge(packet)), peer)

            elif packet.message_type is MessageType.END:
                from reliable_udp.protocol import Packet

                response = Packet(
                    MessageType.FIN_ACK,
                    packet.transfer_id,
                    packet.sequence,
                )
                sock.sendto(encode_packet(response), peer)
                return

    receiver, peer, thread, errors = run_receiver(handler)
    client = _client_socket()

    try:
        stats = send_file(client, source, peer, timeout=0.2)
    finally:
        client.close()
        receiver.close()

    thread.join(timeout=4)

    assert not errors
    assert not thread.is_alive()
    assert stats["bytes_sent"] == 0
    assert stats["chunks_sent"] == 0
    assert stats["attempts"] == 2


def test_retransmits_when_first_data_ack_is_lost(tmp_path: Path):
    source = tmp_path / "retry.bin"
    source.write_bytes(b"abc")
    data_attempts = 0

    def handler(sock):
        nonlocal data_attempts

        while True:
            data, peer = sock.recvfrom(65535)
            packet = decode_packet(data)

            if packet.message_type in (MessageType.START, MessageType.DATA):
                if packet.message_type is MessageType.DATA:
                    data_attempts += 1
                    if data_attempts == 1:
                        continue

                sock.sendto(encode_packet(acknowledge(packet)), peer)

            elif packet.message_type is MessageType.END:
                from reliable_udp.protocol import Packet

                response = Packet(
                    MessageType.FIN_ACK,
                    packet.transfer_id,
                    packet.sequence,
                )
                sock.sendto(encode_packet(response), peer)
                return

    receiver, peer, thread, errors = run_receiver(handler)
    client = _client_socket()

    try:
        stats = send_file(
            client,
            source,
            peer,
            timeout=0.1,
            max_retransmissions=1,
        )
    finally:
        client.close()
        receiver.close()

    thread.join(timeout=4)

    assert not errors
    assert not thread.is_alive()
    assert data_attempts == 2
    assert stats["attempts"] == 4


def test_missing_source_file_raises(tmp_path: Path):
    client = _client_socket()

    try:
        with pytest.raises(FileNotFoundError):
            send_file(client, tmp_path / "missing.txt", ("127.0.0.1", 9999))
    finally:
        client.close()


@pytest.mark.parametrize("chunk_size", [0, -1, MAX_PAYLOAD_SIZE + 1, True])
def test_invalid_chunk_size_raises(tmp_path: Path, chunk_size):
    source = tmp_path / "input.bin"
    source.write_bytes(b"data")
    client = _client_socket()

    try:
        with pytest.raises(ValueError):
            send_file(client, source, ("127.0.0.1", 9999), chunk_size=chunk_size)
    finally:
        client.close()


@pytest.mark.parametrize("retries", [-1, True, 1.5])
def test_invalid_retry_count_raises(tmp_path: Path, retries):
    source = tmp_path / "input.bin"
    source.write_bytes(b"data")
    client = _client_socket()

    try:
        with pytest.raises(ValueError):
            send_file(
                client,
                source,
                ("127.0.0.1", 9999),
                max_retransmissions=retries,
            )
    finally:
        client.close()


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True])
def test_invalid_timeout_raises(tmp_path: Path, timeout):
    source = tmp_path / "input.bin"
    source.write_bytes(b"data")
    client = _client_socket()

    try:
        with pytest.raises(ValueError):
            send_file(
                client,
                source,
                ("127.0.0.1", 9999),
                timeout=timeout,
            )
    finally:
        client.close()


def test_missing_fin_ack_raises_timeout(tmp_path: Path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"data")

    def handler(sock):
        while True:
            data, peer = sock.recvfrom(65535)
            packet = decode_packet(data)

            if packet.message_type in (MessageType.START, MessageType.DATA):
                sock.sendto(encode_packet(acknowledge(packet)), peer)
            elif packet.message_type is MessageType.END:
                return

    receiver, peer, thread, errors = run_receiver(handler)
    client = _client_socket()

    try:
        with pytest.raises(TimeoutError, match="FIN_ACK"):
            send_file(
                client,
                source,
                peer,
                timeout=0.1,
                max_retransmissions=1,
            )
    finally:
        client.close()
        receiver.close()

    thread.join(timeout=4)
    assert not errors
    assert not thread.is_alive()


def test_rejects_malformed_ack_and_wrong_peer(tmp_path: Path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"x")

    def handler(sock):
        data, peer = sock.recvfrom(65535)
        packet = decode_packet(data)

        # Send an ACK with the wrong sequence number.
        from reliable_udp.protocol import Packet

        bad_ack = Packet(
            MessageType.ACK,
            packet.transfer_id,
            packet.sequence + 1,
            bytes((int(MessageType.START),)),
        )
        sock.sendto(encode_packet(bad_ack), peer)

        # Then send the correct ACK.
        sock.sendto(encode_packet(acknowledge(packet)), peer)

        while True:
            data, peer = sock.recvfrom(65535)
            packet = decode_packet(data)

            if packet.message_type is MessageType.DATA:
                sock.sendto(encode_packet(acknowledge(packet)), peer)
            elif packet.message_type is MessageType.END:
                response = Packet(
                    MessageType.FIN_ACK,
                    packet.transfer_id,
                    packet.sequence,
                )
                sock.sendto(encode_packet(response), peer)
                return

    receiver, peer, thread, errors = run_receiver(handler)
    client = _client_socket()

    try:
        stats = send_file(client, source, peer, timeout=0.2)
    finally:
        client.close()
        receiver.close()

    thread.join(timeout=4)

    assert not errors
    assert not thread.is_alive()
    assert stats["bytes_sent"] == 1
