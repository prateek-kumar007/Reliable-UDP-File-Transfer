"""End-to-end file-transfer tests over real localhost UDP sockets."""

import hashlib
import socket
import threading
from pathlib import Path

import pytest

from reliable_udp.protocol import (
    MAX_DATAGRAM_SIZE,
    MessageType,
    Packet,
    decode_packet,
    encode_packet,
)
from reliable_udp.receiver_service import ReceiverService
from reliable_udp.sender import send_file


def _start_receiver(destination: Path, *, drop_first_data_ack: bool = False):
    """Start a UDP server backed by the real ReceiverService."""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(0.2)
    address = server.getsockname()
    service = ReceiverService(destination)
    stop_event = threading.Event()
    errors = []
    counters = {"data_packets": 0, "dropped_data_acks": 0}

    def worker():
        try:
            while not stop_event.is_set():
                try:
                    datagram, peer = server.recvfrom(MAX_DATAGRAM_SIZE)
                except TimeoutError:
                    continue
                except OSError:
                    if stop_event.is_set():
                        break
                    raise

                packet = decode_packet(datagram)

                if packet.message_type is MessageType.DATA:
                    counters["data_packets"] += 1

                response = service.handle_datagram(datagram, peer)

                if response is None:
                    continue

                response_packet = decode_packet(response)

                if (
                    drop_first_data_ack
                    and packet.message_type is MessageType.DATA
                    and response_packet.message_type is MessageType.ACK
                    and counters["dropped_data_acks"] == 0
                ):
                    counters["dropped_data_acks"] += 1
                    continue

                server.sendto(response, peer)

                if response_packet.message_type is MessageType.FIN_ACK:
                    return
        except Exception as exc:
            errors.append(exc)
        finally:
            service.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return server, address, stop_event, thread, errors, counters


def _stop_receiver(server, stop_event, thread):
    stop_event.set()
    server.close()
    thread.join(timeout=3.0)
    assert not thread.is_alive(), "Receiver thread did not stop"


@pytest.mark.parametrize(
    "content",
    [
        b"Reliable UDP file transfer test.",
        b"",
        bytes(range(256)) * 20,
    ],
    ids=["small-file", "empty-file", "binary-file"],
)
def test_send_file_end_to_end(tmp_path: Path, content: bytes):
    source = tmp_path / "sample.bin"
    destination = tmp_path / "received"
    destination.mkdir()
    source.write_bytes(content)

    server, peer, stop_event, thread, errors, _ = _start_receiver(destination)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        stats = send_file(
            client,
            source,
            peer,
            chunk_size=500,
            timeout=0.1,
            max_retransmissions=3,
        )
    finally:
        client.close()
        _stop_receiver(server, stop_event, thread)

    output = destination / source.name

    assert not errors, f"Receiver error: {errors}"
    assert output.is_file()
    assert output.read_bytes() == content
    assert hashlib.sha256(output.read_bytes()).digest() == hashlib.sha256(
        content
    ).digest()
    assert stats["filename"] == source.name
    assert stats["bytes_sent"] == len(content)
    assert stats["chunks_sent"] == (len(content) + 499) // 500


def test_transfer_recovers_from_lost_data_ack(tmp_path: Path):
    content = b"lost acknowledgement recovery" * 30
    source = tmp_path / "retry.bin"
    destination = tmp_path / "received"
    destination.mkdir()
    source.write_bytes(content)

    server, peer, stop_event, thread, errors, counters = _start_receiver(
        destination,
        drop_first_data_ack=True,
    )
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        stats = send_file(
            client,
            source,
            peer,
            chunk_size=100,
            timeout=0.1,
            max_retransmissions=3,
        )
    finally:
        client.close()
        _stop_receiver(server, stop_event, thread)

    output = destination / source.name

    assert not errors, f"Receiver error: {errors}"
    assert counters["dropped_data_acks"] == 1
    assert counters["data_packets"] > stats["chunks_sent"]
    assert output.read_bytes() == content
    assert stats["attempts"] > stats["chunks_sent"] + 2


def test_receiver_does_not_overwrite_existing_file(tmp_path: Path):
    source = tmp_path / "report.txt"
    destination = tmp_path / "received"
    destination.mkdir()

    source.write_bytes(b"incoming contents")
    existing = destination / source.name
    existing.write_bytes(b"original contents")

    server, peer, stop_event, thread, errors, _ = _start_receiver(destination)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        with pytest.raises(TimeoutError):
            send_file(
                client,
                source,
                peer,
                chunk_size=100,
                timeout=0.1,
                max_retransmissions=1,
            )
    finally:
        client.close()
        _stop_receiver(server, stop_event, thread)

    assert not errors, f"Receiver error: {errors}"
    assert existing.read_bytes() == b"original contents"
    assert list(destination.iterdir()) == [existing]


def test_receiver_reacks_duplicate_data_without_duplicate_write(
    tmp_path: Path,
):
    content = b"duplicate-safe"
    destination = tmp_path / "received"
    destination.mkdir()
    transfer_id = bytes(range(16))
    peer = ("127.0.0.1", 40000)

    from reliable_udp.metadata import StartMetadata, encode_start_metadata

    service = ReceiverService(destination)
    metadata = StartMetadata(
        filename="duplicate.txt",
        file_size=len(content),
        chunk_size=len(content),
        sha256=hashlib.sha256(content).digest(),
    )
    start = Packet(
        MessageType.START,
        transfer_id,
        0,
        encode_start_metadata(metadata),
    )
    data = Packet(MessageType.DATA, transfer_id, 0, content)
    end = Packet(MessageType.END, transfer_id, 1)

    try:
        start_response = service.handle_datagram(encode_packet(start), peer)
        assert start_response is not None

        first_ack = service.handle_datagram(encode_packet(data), peer)
        duplicate_ack = service.handle_datagram(encode_packet(data), peer)

        assert first_ack is not None
        assert duplicate_ack == first_ack

        final_ack = service.handle_datagram(encode_packet(end), peer)
        assert final_ack is not None
        assert decode_packet(final_ack).message_type is MessageType.FIN_ACK
        assert (destination / "duplicate.txt").read_bytes() == content
    finally:
        service.close()