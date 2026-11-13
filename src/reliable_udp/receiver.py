
"""Receiver-side protocol state for START and DATA messages."""

from reliable_udp.metadata import StartMetadata, decode_start_metadata
from reliable_udp.protocol import (
    MessageType,
    ProtocolError,
    decode_packet,
    encode_packet,
)
from reliable_udp.transport import make_ack

PeerAddress = tuple[str, int]


class ReceiverState:
    """Track one active transfer's START and DATA state."""

    def __init__(self) -> None:
        self.active_peer: PeerAddress | None = None
        self.active_transfer_id: bytes | None = None
        self.start_payload: bytes | None = None
        self.metadata: StartMetadata | None = None
        self.next_expected_sequence = 0
        self.last_data_sequence: int | None = None
        self.last_data_payload: bytes | None = None
        self.received_bytes = 0

    @property
    def has_active_transfer(self) -> bool:
        """Whether a START handshake has established an active transfer."""
        return self.active_transfer_id is not None

    def handle_datagram(
        self,
        datagram: bytes,
        peer: PeerAddress,
    ) -> bytes | None:
        """Process one datagram and return a response, or None to ignore it."""
        try:
            packet = decode_packet(datagram)
        except ProtocolError:
            return None

        if packet.message_type is MessageType.START:
            return self._handle_start(packet, peer)

        if packet.message_type is MessageType.DATA:
            return self._handle_data(packet, peer)

        return None

    def _handle_start(self, packet, peer: PeerAddress) -> bytes | None:
        if packet.sequence != 0:
            return None

        try:
            metadata = decode_start_metadata(packet.payload)
        except ProtocolError:
            return None

        if not self.has_active_transfer:
            self.active_peer = peer
            self.active_transfer_id = packet.transfer_id
            self.start_payload = packet.payload
            self.metadata = metadata
            return encode_packet(make_ack(packet))

        if peer != self.active_peer:
            return None

        if packet.transfer_id != self.active_transfer_id:
            return None

        if packet.payload != self.start_payload:
            return None

        # A duplicate START must not reset DATA progress.
        return encode_packet(make_ack(packet))

    def _handle_data(self, packet, peer: PeerAddress) -> bytes | None:
        if not self.has_active_transfer or self.metadata is None:
            return None

        if peer != self.active_peer:
            return None

        if packet.transfer_id != self.active_transfer_id:
            return None

        metadata = self.metadata
        total_chunks = (
            metadata.file_size + metadata.chunk_size - 1
        ) // metadata.chunk_size

        # Empty files contain no DATA packets.
        if total_chunks == 0:
            return None

        # Re-ACK the last accepted packet without counting it twice.
        if packet.sequence == self.last_data_sequence:
            if packet.payload == self.last_data_payload:
                return encode_packet(make_ack(packet))
            return None

        if packet.sequence != self.next_expected_sequence:
            return None

        if packet.sequence >= total_chunks:
            return None

        expected_length = min(
            metadata.chunk_size,
            metadata.file_size - packet.sequence * metadata.chunk_size,
        )
        if len(packet.payload) != expected_length:
            return None

        self.last_data_sequence = packet.sequence
        self.last_data_payload = packet.payload
        self.next_expected_sequence += 1
        self.received_bytes += len(packet.payload)

        return encode_packet(make_ack(packet))

    def reset(self) -> None:
        """Clear state after a transfer has finished or been aborted."""
        self.active_peer = None
        self.active_transfer_id = None
        self.start_payload = None
        self.metadata = None
        self.next_expected_sequence = 0
        self.last_data_sequence = None
        self.last_data_payload = None
        self.received_bytes = 0
