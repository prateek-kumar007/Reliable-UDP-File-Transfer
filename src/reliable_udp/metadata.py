
"""Encoding and validation for START packet metadata."""

import struct
from dataclasses import dataclass

from reliable_udp.protocol import MAX_PAYLOAD_SIZE, ProtocolError

MAX_FILENAME_BYTES = 255
FILE_SIZE_BYTES = 8
CHUNK_SIZE_BYTES = 2
SHA256_SIZE = 32

# Two-byte filename length + filename + file size + chunk size + SHA-256.
FIXED_METADATA_SIZE = 2 + FILE_SIZE_BYTES + CHUNK_SIZE_BYTES + SHA256_SIZE
MAX_CHUNK_SIZE = MAX_PAYLOAD_SIZE


@dataclass(frozen=True)
class StartMetadata:
    """Metadata describing the file being transferred."""

    filename: str
    file_size: int
    chunk_size: int
    sha256: bytes


def _validate_filename(filename: str) -> bytes:
    if not isinstance(filename, str):
        raise ProtocolError("Filename must be a string")

    try:
        encoded = filename.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ProtocolError("Filename must be valid UTF-8") from exc

    if not encoded or len(encoded) > MAX_FILENAME_BYTES:
        raise ProtocolError("Filename must be 1-255 UTF-8 bytes")

    if filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise ProtocolError("Filename must be a basename, not a path")

    if "\x00" in filename:
        raise ProtocolError("Filename cannot contain a NUL character")

    return encoded


def _validate_metadata(metadata: StartMetadata) -> bytes:
    if not isinstance(metadata, StartMetadata):
        raise ProtocolError("Expected StartMetadata")

    filename_bytes = _validate_filename(metadata.filename)

    if (
        not isinstance(metadata.file_size, int)
        or isinstance(metadata.file_size, bool)
        or not 0 <= metadata.file_size < (1 << 64)
    ):
        raise ProtocolError("File size must be an unsigned 64-bit integer")

    if (
        not isinstance(metadata.chunk_size, int)
        or isinstance(metadata.chunk_size, bool)
        or not 1 <= metadata.chunk_size <= MAX_CHUNK_SIZE
    ):
        raise ProtocolError(
            f"Chunk size must be between 1 and {MAX_CHUNK_SIZE}"
        )

    if not isinstance(metadata.sha256, bytes) or len(metadata.sha256) != SHA256_SIZE:
        raise ProtocolError("SHA-256 digest must be exactly 32 bytes")

    return filename_bytes


def encode_start_metadata(metadata: StartMetadata) -> bytes:
    """Serialize validated START metadata."""
    filename_bytes = _validate_metadata(metadata)

    payload = (
        struct.pack("!H", len(filename_bytes))
        + filename_bytes
        + struct.pack("!QH", metadata.file_size, metadata.chunk_size)
        + metadata.sha256
    )

    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ProtocolError("START metadata exceeds the maximum payload size")

    return payload


def decode_start_metadata(payload: bytes) -> StartMetadata:
    """Parse START metadata, rejecting malformed or unsafe values."""
    if not isinstance(payload, bytes):
        raise ProtocolError("START metadata must be bytes")

    if len(payload) < FIXED_METADATA_SIZE:
        raise ProtocolError("START metadata is truncated")

    filename_length = struct.unpack("!H", payload[:2])[0]

    if not 1 <= filename_length <= MAX_FILENAME_BYTES:
        raise ProtocolError("Filename length must be between 1 and 255 bytes")

    expected_length = FIXED_METADATA_SIZE + filename_length
    if len(payload) != expected_length:
        raise ProtocolError("START metadata has an invalid length")

    filename_start = 2
    filename_end = filename_start + filename_length

    try:
        filename = payload[filename_start:filename_end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Filename is not valid UTF-8") from exc

    file_size, chunk_size = struct.unpack(
        "!QH", payload[filename_end : filename_end + 10]
    )
    sha256 = payload[filename_end + 10 :]

    metadata = StartMetadata(
        filename=filename,
        file_size=file_size,
        chunk_size=chunk_size,
        sha256=sha256,
    )

    _validate_metadata(metadata)
    return metadata