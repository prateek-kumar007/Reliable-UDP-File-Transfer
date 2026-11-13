"""Sender-side file transfer using Stop-and-Wait ARQ."""

import hashlib
import secrets
import socket
import time
from pathlib import Path

from reliable_udp.metadata import StartMetadata, encode_start_metadata
from reliable_udp.protocol import (
    MAX_DATAGRAM_SIZE,
    MAX_PAYLOAD_SIZE,
    MAX_SEQUENCE,
    MessageType,
    Packet,
    ProtocolError,
    decode_packet,
    encode_packet,
)
from reliable_udp.transport import (
    DEFAULT_MAX_RETRANSMISSIONS,
    DEFAULT_TIMEOUT_SECONDS,
    send_with_ack,
)

PeerAddress = tuple[str, int]


def _file_details(file_obj) -> tuple[int, bytes]:
    """Calculate file size and SHA-256 without loading the file into memory."""
    digest = hashlib.sha256()
    size = 0

    while chunk := file_obj.read(1024 * 1024):
        size += len(chunk)
        digest.update(chunk)

    file_obj.seek(0)
    return size, digest.digest()


def _send_end(
    sock: socket.socket,
    packet: Packet,
    peer: PeerAddress,
    timeout: float,
    max_retransmissions: int,
) -> int:
    """Send END until the matching FIN_ACK arrives or retries are exhausted."""
    original_timeout = sock.gettimeout()

    try:
        for attempt in range(max_retransmissions + 1):
            sock.sendto(encode_packet(packet), peer)
            deadline = time.monotonic() + timeout

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break

                sock.settimeout(remaining)

                try:
                    datagram, source = sock.recvfrom(MAX_DATAGRAM_SIZE)
                except TimeoutError:
                    break

                if source != peer:
                    continue

                try:
                    response = decode_packet(datagram)
                except ProtocolError:
                    continue

                if (
                    response.message_type is MessageType.FIN_ACK
                    and response.transfer_id == packet.transfer_id
                    and response.sequence == packet.sequence
                    and not response.payload
                ):
                    return attempt + 1

        raise TimeoutError(
            f"No FIN_ACK received after {max_retransmissions + 1} attempts"
        )
    finally:
        sock.settimeout(original_timeout)


def send_file(
    sock: socket.socket,
    source_path: str | Path,
    peer: PeerAddress,
    *,
    chunk_size: int = MAX_PAYLOAD_SIZE,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retransmissions: int = DEFAULT_MAX_RETRANSMISSIONS,
) -> dict[str, int | str]:
    """Transfer one file and return transfer statistics."""
    source = Path(source_path)

    if not source.is_file():
        raise FileNotFoundError(source)

    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or not 1 <= chunk_size <= MAX_PAYLOAD_SIZE
    ):
        raise ValueError(
            f"chunk_size must be between 1 and {MAX_PAYLOAD_SIZE}"
        )

    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0 < timeout < float("inf")
    ):
        raise ValueError("timeout must be a finite positive number")

    if (
        isinstance(max_retransmissions, bool)
        or not isinstance(max_retransmissions, int)
        or max_retransmissions < 0
    ):
        raise ValueError("max_retransmissions must be a non-negative integer")

    total_attempts = 0

    with source.open("rb") as file_obj:
        file_size, digest = _file_details(file_obj)
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        if total_chunks > MAX_SEQUENCE:
            raise ValueError("File requires too many DATA chunks")

        metadata = StartMetadata(
            filename=source.name,
            file_size=file_size,
            chunk_size=chunk_size,
            sha256=digest,
        )

        transfer_id = secrets.token_bytes(16)

        start_packet = Packet(
            MessageType.START,
            transfer_id,
            0,
            encode_start_metadata(metadata),
        )

        total_attempts += send_with_ack(
            sock,
            start_packet,
            peer,
            timeout=timeout,
            max_retransmissions=max_retransmissions,
        )

        bytes_sent = 0

        for sequence in range(total_chunks):
            data = file_obj.read(chunk_size)

            if not data:
                raise OSError("Source file changed during transfer")

            packet = Packet(
                MessageType.DATA,
                transfer_id,
                sequence,
                data,
            )

            total_attempts += send_with_ack(
                sock,
                packet,
                peer,
                timeout=timeout,
                max_retransmissions=max_retransmissions,
            )
            bytes_sent += len(data)

        if file_obj.read(1):
            raise OSError("Source file grew during transfer")

        # Detect content changes between hashing and transmission.
        file_obj.seek(0)
        verification_digest = hashlib.sha256()

        while chunk := file_obj.read(1024 * 1024):
            verification_digest.update(chunk)

        if verification_digest.digest() != digest:
            raise OSError("Source file changed during transfer")

    end_packet = Packet(
        MessageType.END,
        transfer_id,
        total_chunks,
    )

    total_attempts += _send_end(
        sock,
        end_packet,
        peer,
        timeout,
        max_retransmissions,
    )

    return {
        "filename": source.name,
        "bytes_sent": bytes_sent,
        "chunks_sent": total_chunks,
        "attempts": total_attempts,
    }
