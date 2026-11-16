import hashlib

from reliable_udp.metadata import StartMetadata, encode_start_metadata
from reliable_udp.protocol import (
    MessageType,
    Packet,
    decode_packet,
    encode_packet,
)
from reliable_udp.receiver_service import ReceiverService

PEER = ("127.0.0.1", 9000)
TRANSFER_ID = bytes(range(16))


def make_start(data: bytes, filename: str = "received.bin") -> Packet:
    metadata = StartMetadata(
        filename=filename,
        file_size=len(data),
        chunk_size=4,
        sha256=hashlib.sha256(data).digest(),
    )
    return Packet(
        MessageType.START,
        TRANSFER_ID,
        0,
        encode_start_metadata(metadata),
    )


def send(service: ReceiverService, packet: Packet) -> bytes | None:
    return service.handle_datagram(encode_packet(packet), PEER)


def test_receives_and_publishes_file(tmp_path):
    service = ReceiverService(tmp_path)
    data = b"abcdefgh"

    response = send(service, make_start(data))
    assert decode_packet(response).message_type is MessageType.ACK

    response = send(
        service,
        Packet(MessageType.DATA, TRANSFER_ID, 0, b"abcd"),
    )
    assert decode_packet(response).message_type is MessageType.ACK

    response = send(
        service,
        Packet(MessageType.DATA, TRANSFER_ID, 1, b"efgh"),
    )
    assert decode_packet(response).message_type is MessageType.ACK

    response = send(service, Packet(MessageType.END, TRANSFER_ID, 2))
    assert decode_packet(response).message_type is MessageType.FIN_ACK
    assert (tmp_path / "received.bin").read_bytes() == data
    assert not list(tmp_path.glob(".rft-*.part"))


def test_duplicate_data_is_not_written_twice(tmp_path):
    service = ReceiverService(tmp_path)
    data = b"abcd"
    send(service, make_start(data))

    packet = Packet(MessageType.DATA, TRANSFER_ID, 0, data)
    first = send(service, packet)
    duplicate = send(service, packet)

    assert first == duplicate

    response = send(service, Packet(MessageType.END, TRANSFER_ID, 1))
    assert decode_packet(response).message_type is MessageType.FIN_ACK
    assert (tmp_path / "received.bin").read_bytes() == data


def test_end_before_all_data_does_not_publish(tmp_path):
    service = ReceiverService(tmp_path)
    send(service, make_start(b"abcdefgh"))

    response = send(service, Packet(MessageType.END, TRANSFER_ID, 2))

    assert response is None
    assert not (tmp_path / "received.bin").exists()


def test_duplicate_end_is_acknowledged(tmp_path):
    service = ReceiverService(tmp_path)
    send(service, make_start(b"abcd"))
    send(service, Packet(MessageType.DATA, TRANSFER_ID, 0, b"abcd"))
    end = Packet(MessageType.END, TRANSFER_ID, 1)

    first = send(service, end)
    duplicate = send(service, end)

    assert first == duplicate
    assert decode_packet(duplicate).message_type is MessageType.FIN_ACK


def test_hash_mismatch_aborts_without_publishing(tmp_path):
    service = ReceiverService(tmp_path)
    metadata = StartMetadata(
        filename="received.bin",
        file_size=4,
        chunk_size=4,
        sha256=hashlib.sha256(b"xxxx").digest(),
    )
    start = Packet(
        MessageType.START,
        TRANSFER_ID,
        0,
        encode_start_metadata(metadata),
    )

    send(service, start)
    send(service, Packet(MessageType.DATA, TRANSFER_ID, 0, b"abcd"))

    response = send(service, Packet(MessageType.END, TRANSFER_ID, 1))

    assert response is None
    assert not (tmp_path / "received.bin").exists()
    assert not list(tmp_path.glob(".rft-*.part"))


def test_existing_destination_is_not_overwritten(tmp_path):
    destination = tmp_path / "received.bin"
    destination.write_bytes(b"original")
    service = ReceiverService(tmp_path)

    response = send(service, make_start(b"new!"))

    assert response is None
    assert destination.read_bytes() == b"original"
    assert not service.state.has_active_transfer


def test_empty_file_transfer(tmp_path):
    service = ReceiverService(tmp_path)
    send(service, make_start(b""))

    response = send(service, Packet(MessageType.END, TRANSFER_ID, 0))

    assert decode_packet(response).message_type is MessageType.FIN_ACK
    assert (tmp_path / "received.bin").read_bytes() == b""