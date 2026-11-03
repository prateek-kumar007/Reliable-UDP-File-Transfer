
"""Packet encoding and decoding for Reliable File Transfer over UDP."""

import struct
from dataclasses import dataclass
from enum import IntEnum

MAGIC = b"RFT1"
HEADER_FORMAT = "!4sB16sIH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 27 bytes
MAX_DATAGRAM_SIZE = 1200
MAX_PAYLOAD_SIZE = MAX_DATAGRAM_SIZE - HEADER_SIZE  # 1173 bytes
MAX_SEQUENCE = (1 << 32) - 1


class MessageType(IntEnum):
    START = 0x01
    DATA = 0x02
    ACK = 0x03
    END = 0x04
    FIN_ACK = 0x05
    ERROR = 0x06


class ProtocolError(ValueError):
    """Raised when a packet violates the wire-format rules."""


@dataclass(frozen=True)
class Packet:
    message_type: MessageType
    transfer_id: bytes
    sequence: int
    payload: bytes = b""


def encode_packet(packet: Packet) -> bytes:
    """Serialize a validated packet into a UDP datagram."""
    if not isinstance(packet.message_type, MessageType):
        raise ProtocolError("Unknown message type")

    if not isinstance(packet.transfer_id, bytes) or len(packet.transfer_id) != 16:
        raise ProtocolError("Transfer ID must be exactly 16 bytes")

    if (
        not isinstance(packet.sequence, int)
        or isinstance(packet.sequence, bool)
        or not 0 <= packet.sequence <= MAX_SEQUENCE
    ):
        raise ProtocolError("Sequence number must be an unsigned 32-bit integer")

    if not isinstance(packet.payload, bytes):
        raise ProtocolError("Payload must be bytes")

    if len(packet.payload) > MAX_PAYLOAD_SIZE:
        raise ProtocolError(
            f"Payload exceeds the {MAX_PAYLOAD_SIZE}-byte limit"
        )

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        packet.message_type,
        packet.transfer_id,
        packet.sequence,
        len(packet.payload),
    )
    return header + packet.payload


def decode_packet(datagram: bytes) -> Packet:
    """Parse a UDP datagram, rejecting malformed or oversized input."""
    if not isinstance(datagram, bytes):
        raise ProtocolError("Datagram must be bytes")

    if len(datagram) > MAX_DATAGRAM_SIZE:
        raise ProtocolError("Datagram exceeds the maximum size")

    if len(datagram) < HEADER_SIZE:
        raise ProtocolError("Datagram is shorter than the packet header")

    magic, raw_type, transfer_id, sequence, payload_length = struct.unpack(
        HEADER_FORMAT, datagram[:HEADER_SIZE]
    )

    if magic != MAGIC:
        raise ProtocolError("Invalid protocol magic")

    try:
        message_type = MessageType(raw_type)
    except ValueError as exc:
        raise ProtocolError(f"Unknown message type: {raw_type}") from exc

    actual_payload = datagram[HEADER_SIZE:]

    if payload_length != len(actual_payload):
        raise ProtocolError("Declared payload length does not match datagram")

    return Packet(
        message_type=message_type,
        transfer_id=transfer_id,
        sequence=sequence,
        payload=actual_payload,
    )
