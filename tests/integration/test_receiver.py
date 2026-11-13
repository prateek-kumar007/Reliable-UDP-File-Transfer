
import hashlib
import socket
import threading

from reliable_udp.metadata import StartMetadata, encode_start_metadata
from reliable_udp.protocol import MessageType, Packet, decode_packet, encode_packet
from reliable_udp.receiver import ReceiverState


def test_receiver_reacks_duplicate_start_over_real_udp():
    state = ReceiverState()
    errors = []

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind(("127.0.0.1", 0))
        server.settimeout(2.0)
        server_address = server.getsockname()

        def serve_two_packets():
            try:
                for _ in range(2):
                    datagram, peer = server.recvfrom(2048)
                    response = state.handle_datagram(datagram, peer)
                    if response is not None:
                        server.sendto(response, peer)
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=serve_two_packets, daemon=True)
        worker.start()

        start = Packet(
            MessageType.START,
            bytes(range(16)),
            0,
            encode_start_metadata(
                StartMetadata(
                    filename="sample.txt",
                    file_size=4,
                    chunk_size=1000,
                    sha256=hashlib.sha256(b"data").digest(),
                )
            ),
        )
        encoded_start = encode_packet(start)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2.0)

            acknowledgements = []
            for _ in range(2):
                client.sendto(encoded_start, server_address)
                data, _ = client.recvfrom(2048)
                acknowledgements.append(decode_packet(data))

        worker.join(timeout=3.0)

        assert not worker.is_alive(), "Receiver thread did not finish"
        assert not errors, f"Receiver error: {errors}"
        assert len(acknowledgements) == 2
        assert acknowledgements[0] == acknowledgements[1]
        assert acknowledgements[0].message_type is MessageType.ACK
        assert state.has_active_transfer
