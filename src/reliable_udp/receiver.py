
"""Receiver-side protocol state for the START handshake."""


from reliable_udp.protocol import (
    MessageType,
    ProtocolError,
    decode_packet,
    encode_packet,
)
from reliable_udp.transport import make_ack

PeerAddress = tuple[str, int]


class ReceiverState:
    """Track one active transfer's START handshake.

    This class handles protocol messages only. It does not write files or
    open sockets; the caller supplies each datagram and its source address.
    """

    def __init__(self) -> None:
        self.active_peer: PeerAddress | None = None
        self.active_transfer_id: bytes | None = None
        self.start_payload: bytes | None = None

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

        # This milestone supports START only.
        if packet.message_type is not MessageType.START:
            return None

        if packet.sequence != 0:
            return None

        if not self.has_active_transfer:
            self.active_peer = peer
            self.active_transfer_id = packet.transfer_id
            self.start_payload = packet.payload
            return encode_packet(make_ack(packet))

        # Only the original peer may continue this transfer.
        if peer != self.active_peer:
            return None

        # A different transfer ID cannot replace an active transfer.
        if packet.transfer_id != self.active_transfer_id:
            return None

        # Repeated START is safe only if its metadata is identical.
        if packet.payload != self.start_payload:
            return None

        # Re-ACK the duplicate START without resetting state.
        return encode_packet(make_ack(packet))

    def reset(self) -> None:
        """Clear transfer state after a transfer has finished or been aborted."""
        self.active_peer = None
        self.active_transfer_id = None
        self.start_payload = None
