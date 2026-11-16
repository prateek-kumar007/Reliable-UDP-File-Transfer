
import hashlib
import struct

import pytest

from reliable_udp.metadata import (
    MAX_CHUNK_SIZE,
    StartMetadata,
    decode_start_metadata,
    encode_start_metadata,
)
from reliable_udp.protocol import ProtocolError


def valid_metadata(**overrides):
    values = {
        "filename": "report.txt",
        "file_size": 1234,
        "chunk_size": 1000,
        "sha256": hashlib.sha256(b"test data").digest(),
    }
    values.update(overrides)
    return StartMetadata(**values)


def test_metadata_round_trip():
    metadata = valid_metadata()

    encoded = encode_start_metadata(metadata)

    assert decode_start_metadata(encoded) == metadata


def test_empty_file_metadata_is_valid():
    metadata = valid_metadata(file_size=0)

    assert decode_start_metadata(encode_start_metadata(metadata)) == metadata


def test_maximum_chunk_size_is_valid():
    metadata = valid_metadata(chunk_size=MAX_CHUNK_SIZE)

    assert decode_start_metadata(encode_start_metadata(metadata)) == metadata


@pytest.mark.parametrize(
    "filename",
    [
        "",
        ".",
        "..",
        "../secret.txt",
        "folder/file.txt",
        r"folder\file.txt",
        "bad\x00name.txt",
    ],
)
def test_encode_rejects_unsafe_filename(filename):
    with pytest.raises(ProtocolError):
        encode_start_metadata(valid_metadata(filename=filename))


def test_encode_rejects_filename_over_255_utf8_bytes():
    with pytest.raises(ProtocolError):
        encode_start_metadata(valid_metadata(filename="é" * 128))


@pytest.mark.parametrize("file_size", [-1, 1 << 64, True])
def test_encode_rejects_invalid_file_size(file_size):
    with pytest.raises(ProtocolError):
        encode_start_metadata(valid_metadata(file_size=file_size))


@pytest.mark.parametrize("chunk_size", [0, -1, MAX_CHUNK_SIZE + 1])
def test_encode_rejects_invalid_chunk_size(chunk_size):
    with pytest.raises(ProtocolError):
        encode_start_metadata(valid_metadata(chunk_size=chunk_size))


@pytest.mark.parametrize("digest", [b"", b"x" * 31, b"x" * 33])
def test_encode_rejects_invalid_sha256_length(digest):
    with pytest.raises(ProtocolError):
        encode_start_metadata(valid_metadata(sha256=digest))


def test_decode_rejects_truncated_payload():
    with pytest.raises(ProtocolError):
        decode_start_metadata(b"\x00")


def test_decode_rejects_invalid_utf8_filename():
    # Filename length 1, followed by an invalid UTF-8 byte.
    payload = struct.pack("!H", 1) + b"\xff"
    with pytest.raises(ProtocolError):
        decode_start_metadata(payload)


def test_decode_rejects_trailing_bytes():
    payload = encode_start_metadata(valid_metadata()) + b"\x00"
    with pytest.raises(ProtocolError):
        decode_start_metadata(payload)


@pytest.mark.parametrize("filename", ["../secret.txt", r"..\secret.txt", ".", ".."])
def test_decode_rejects_unsafe_filename(filename):
    encoded_name = filename.encode("utf-8")
    payload = (
        struct.pack("!H", len(encoded_name))
        + encoded_name
        + struct.pack("!QH", 0, 100)
        + hashlib.sha256(b"").digest()
    )
    with pytest.raises(ProtocolError):
        decode_start_metadata(payload)


def test_decode_rejects_zero_chunk_size():
    encoded_name = b"a"
    payload = (
        struct.pack("!H", len(encoded_name))
        + encoded_name
        + struct.pack("!QH", 0, 0)
        + hashlib.sha256(b"").digest()
    )
    with pytest.raises(ProtocolError):
        decode_start_metadata(payload)