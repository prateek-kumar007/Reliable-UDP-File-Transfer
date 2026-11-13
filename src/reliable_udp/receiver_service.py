"""File-receiving service combining protocol state and verified storage."""

from collections import OrderedDict
from pathlib import Path

from reliable_udp.file_storage import ReceiveFile
from reliable_udp.protocol import (
    MessageType,
    Packet,
    ProtocolError,
    decode_packet,
    encode_packet,
)
from reliable_udp.receiver import PeerAddress, ReceiverState


class ReceiverService:
    """Receive one file at a time and publish only verified transfers."""

    COMPLETED_CACHE_SIZE = 128

    def __init__(
        self,
        destination_dir: str | Path,
        state: ReceiverState | None = None,
    ) -> None:
        self.destination_dir = Path(destination_dir)
        if not self.destination_dir.is_dir():
            raise FileNotFoundError(self.destination_dir)

        self.state = state or ReceiverState()
        self._storage: ReceiveFile | None = None
        self._completed: OrderedDict[
            tuple[PeerAddress, bytes, int], None
        ] = OrderedDict()

    def handle_datagram(
        self,
        datagram: bytes,
        peer: PeerAddress,
    ) -> bytes | None:
        """Handle START, DATA, and END messages and return a response."""
        try:
            packet = decode_packet(datagram)
        except ProtocolError:
            return None

        if packet.message_type is MessageType.START:
            return self._handle_start(datagram, packet, peer)

        if packet.message_type is MessageType.DATA:
            return self._handle_data(datagram, packet, peer)

        if packet.message_type is MessageType.END:
            return self._handle_end(packet, peer)

        return None

    def _handle_start(
        self,
        datagram: bytes,
        packet: Packet,
        peer: PeerAddress,
    ) -> bytes | None:
        was_active = self.state.has_active_transfer
        response = self.state.handle_datagram(datagram, peer)

        if response is None:
            return None

        if was_active:
            return response

        metadata = self.state.metadata
        if metadata is None:
            self.state.reset()
            return None

        destination = self.destination_dir / metadata.filename

        try:
            self._storage = ReceiveFile(destination, metadata)
        except (OSError, ValueError):
            self.state.reset()
            return None

        return response

    def _handle_data(
        self,
        datagram: bytes,
        packet: Packet,
        peer: PeerAddress,
    ) -> bytes | None:
        if self._storage is None:
            return None

        previous_sequence = self.state.last_data_sequence
        response = self.state.handle_datagram(datagram, peer)

        if response is None:
            return None

        # A retransmitted DATA packet must be ACKed, not written twice.
        if packet.sequence == previous_sequence:
            return response

        try:
            self._storage.write_chunk(packet.payload)
        except (OSError, ProtocolError, RuntimeError):
            self._abort()
            return None

        return response

    def _handle_end(
        self,
        packet: Packet,
        peer: PeerAddress,
    ) -> bytes | None:
        if packet.payload:
            return None

        cache_key = (peer, packet.transfer_id, packet.sequence)
        if cache_key in self._completed:
            self._completed.move_to_end(cache_key)
            return encode_packet(
                Packet(
                    MessageType.FIN_ACK,
                    packet.transfer_id,
                    packet.sequence,
                )
            )

        if (
            self._storage is None
            or not self.state.has_active_transfer
            or peer != self.state.active_peer
            or packet.transfer_id != self.state.active_transfer_id
            or self.state.metadata is None
        ):
            return None

        metadata = self.state.metadata
        total_chunks = (
            metadata.file_size + metadata.chunk_size - 1
        ) // metadata.chunk_size

        if (
            packet.sequence != total_chunks
            or self.state.next_expected_sequence != total_chunks
            or self.state.received_bytes != metadata.file_size
        ):
            return None

        try:
            self._storage.finalize()
        except (OSError, ProtocolError, RuntimeError):
            self._abort()
            return None

        self._storage = None
        self.state.reset()

        self._completed[cache_key] = None
        while len(self._completed) > self.COMPLETED_CACHE_SIZE:
            self._completed.popitem(last=False)

        return encode_packet(
            Packet(
                MessageType.FIN_ACK,
                packet.transfer_id,
                packet.sequence,
            )
        )

    def _abort(self) -> None:
        """Remove partial data and reset the active transfer."""
        if self._storage is not None:
            self._storage.close()
            self._storage = None
        self.state.reset()

    def close(self) -> None:
        """Clean up an unfinished transfer when shutting down."""
        self._abort()
