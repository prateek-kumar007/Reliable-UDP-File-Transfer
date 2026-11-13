
import hashlib

import pytest

from reliable_udp.file_storage import ReceiveFile
from reliable_udp.metadata import StartMetadata
from reliable_udp.protocol import ProtocolError


def metadata_for(data: bytes, filename: str = "received.bin") -> StartMetadata:
    return StartMetadata(
        filename=filename,
        file_size=len(data),
        chunk_size=100,
        sha256=hashlib.sha256(data).digest(),
    )


def test_writes_and_publishes_verified_file(tmp_path):
    data = b"reliable transfer"
    destination = tmp_path / "received.bin"

    with ReceiveFile(destination, metadata_for(data)) as received:
        received.write_chunk(data)
        result = received.finalize()

    assert result == destination
    assert destination.read_bytes() == data


def test_rejects_incomplete_file(tmp_path):
    destination = tmp_path / "received.bin"
    received = ReceiveFile(destination, metadata_for(b"complete"))

    try:
        received.write_chunk(b"partial")
        with pytest.raises(ProtocolError, match="size"):
            received.finalize()
    finally:
        received.close()

    assert not destination.exists()
    assert not list(tmp_path.glob(".rft-*.part"))


def test_rejects_hash_mismatch(tmp_path):
    destination = tmp_path / "received.bin"
    received = ReceiveFile(destination, metadata_for(b"expected"))

    try:
        received.write_chunk(b"Expected")
        with pytest.raises(ProtocolError, match="SHA-256"):
            received.finalize()
    finally:
        received.close()

    assert not destination.exists()


def test_does_not_overwrite_existing_destination(tmp_path):
    destination = tmp_path / "received.bin"
    destination.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        ReceiveFile(destination, metadata_for(b"new data"))

    assert destination.read_bytes() == b"original"


def test_rejects_data_beyond_declared_size(tmp_path):
    destination = tmp_path / "received.bin"
    received = ReceiveFile(destination, metadata_for(b"abc"))

    try:
        with pytest.raises(ProtocolError, match="exceeds"):
            received.write_chunk(b"abcd")
    finally:
        received.close()


def test_empty_file_can_be_published(tmp_path):
    destination = tmp_path / "empty.bin"

    with ReceiveFile(destination, metadata_for(b"")) as received:
        result = received.finalize()

    assert result == destination
    assert destination.read_bytes() == b""
