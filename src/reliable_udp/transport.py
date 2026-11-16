
"""Stop-and-Wait packet transmission over a UDP socket."""

import socket
import time
from collections.abc import Callable

from reliable_udp.protocol import (
    MessageType,
    Packet,
    ProtocolError,
    decode_packet,
    encode_packet,
)

DEFAULT_TIMEOUT_SECONDS = 0.5
DEFAULT_MAX_RETRANSMISSIONS = 8

EventCallback = Callable[[dict[str, object]], None]


def _emit(
    callback: EventCallback | None,
    event: str,
    **details: object,
) -> None:
    """Report a transport event when a callback is configured."""
    if callback is not None:
        callback({"event": event, **details})


def make_ack(packet: Packet) -> Packet:
    """Build an ACK for a START or DATA packet."""
    if packet.message_type not in (MessageType.START, MessageType.DATA):
        raise ProtocolError("ACK can only acknowledge START or DATA")

    return Packet(
        message_type=MessageType.ACK,
        transfer_id=packet.transfer_id,
        sequence=packet.sequence,
        payload=bytes((int(packet.message_type),)),
    )


def _matches_ack(response: Packet, sent: Packet) -> bool:
    """Return whether an ACK acknowledges this exact START or DATA packet."""
    return (
        response.message_type == MessageType.ACK
        and response.transfer_id == sent.transfer_id
        and response.sequence == sent.sequence
        and response.payload == bytes((int(sent.message_type),))
    )


def send_with_ack(
    sock: socket.socket,
    packet: Packet,
    peer: tuple[str, int],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retransmissions: int = DEFAULT_MAX_RETRANSMISSIONS,
    *,
    event_callback: EventCallback | None = None,
) -> int:
    """Send START or DATA until its matching ACK arrives.

    Returns transmission attempts, including the initial send.
    Raises TimeoutError after all attempts fail.
    """
    if packet.message_type not in (MessageType.START, MessageType.DATA):
        raise ProtocolError("send_with_ack supports START and DATA only")

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    if (
        not isinstance(max_retransmissions, int)
        or isinstance(max_retransmissions, bool)
        or max_retransmissions < 0
    ):
        raise ValueError("max_retransmissions must be a non-negative integer")

    datagram = encode_packet(packet)
    total_attempts = max_retransmissions + 1

    for attempt in range(1, total_attempts + 1):
        sock.sendto(datagram, peer)
        _emit(
            event_callback,
            "packet_sent",
            message_type=packet.message_type.name,
            sequence=packet.sequence,
            attempt=attempt,
            retransmission=attempt > 1,
        )
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            sock.settimeout(remaining)

            try:
                response_data, source = sock.recvfrom(65535)
            except TimeoutError:
                break

            if source != peer:
                continue

            try:
                response = decode_packet(response_data)
            except ProtocolError:
                continue

            if _matches_ack(response, packet):
                _emit(
                    event_callback,
                    "ack_received",
                    message_type=packet.message_type.name,
                    sequence=packet.sequence,
                    attempt=attempt,
                )
                return attempt

        _emit(
            event_callback,
            "timeout",
            message_type=packet.message_type.name,
            sequence=packet.sequence,
            attempt=attempt,
            retries_remaining=total_attempts - attempt,
        )

    raise TimeoutError(
        f"No matching ACK after {total_attempts} transmission attempts"
    )