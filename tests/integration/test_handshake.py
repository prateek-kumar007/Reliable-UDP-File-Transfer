
"""Real localhost UDP integration tests for Stop-and-Wait transmission."""

import socket
import threading

from reliable_udp.protocol import (
    MessageType,
    Packet,
    decode_packet,
    encode_packet,
)
from reliable_udp.transport import make_ack, send_with_ack


def test_real_udp_handshake_recovers_from_lost_ack():
    transfer_id = bytes(range(16))
    start = Packet(MessageType.START, transfer_id, 0, b"test metadata")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        receiver_address = receiver.getsockname()

        received_packets = []
        receiver_errors = []

        def receiver_worker():
            try:
                # Drop the first ACK. ACK the retransmitted START.
                for attempt in range(2):
                    data, sender_address = receiver.recvfrom(2048)
                    packet = decode_packet(data)
                    received_packets.append(packet)

                    if packet != start:
                        raise AssertionError(f"Unexpected packet: {packet!r}")

                    if attempt == 1:
                        receiver.sendto(
                            encode_packet(make_ack(packet)),
                            sender_address,
                        )
            except Exception as exc:
                receiver_errors.append(exc)

        worker = threading.Thread(target=receiver_worker, daemon=True)
        worker.start()

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                attempts = send_with_ack(
                    sender,
                    start,
                    receiver_address,
                    timeout=0.15,
                    max_retransmissions=2,
                )
        finally:
            worker.join(timeout=3.0)

        assert not worker.is_alive(), "Receiver thread did not finish"
        assert not receiver_errors, f"Receiver error: {receiver_errors}"
        assert attempts == 2
        assert received_packets == [start, start]
