
"""Temporary file storage and integrity verification for received transfers."""

import hashlib
import os
import tempfile
from pathlib import Path

from reliable_udp.metadata import StartMetadata
from reliable_udp.protocol import ProtocolError


class ReceiveFile:
    """Write received chunks to a temporary file and publish after verification."""

    def __init__(self, destination: str | Path, metadata: StartMetadata) -> None:
        self.destination = Path(destination)
        self.metadata = metadata
        self.temp_path: Path | None = None
        self._file = None
        self._hasher = hashlib.sha256()
        self.bytes_written = 0
        self._published = False

        if self.destination.exists():
            raise FileExistsError(self.destination)

        if not self.destination.parent.is_dir():
            raise FileNotFoundError(self.destination.parent)

        # Use the destination directory so publication stays on the same filesystem.
        fd, temp_name = tempfile.mkstemp(
            prefix=".rft-",
            suffix=".part",
            dir=self.destination.parent,
        )
        self.temp_path = Path(temp_name)
        self._file = os.fdopen(fd, "wb")

    def write_chunk(self, data: bytes) -> None:
        """Write one chunk after checking that it fits the declared file size."""
        if self._file is None:
            raise RuntimeError("Receive file is not open")

        if not isinstance(data, bytes) or not data:
            raise ProtocolError("DATA payload must not be empty")

        if self.bytes_written + len(data) > self.metadata.file_size:
            raise ProtocolError("Received data exceeds the declared file size")

        self._file.write(data)
        self._hasher.update(data)
        self.bytes_written += len(data)

    def finalize(self) -> Path:
        """Verify the complete file and publish it without overwriting."""
        if self._file is None or self.temp_path is None:
            raise RuntimeError("Receive file is not open")

        if self.bytes_written != self.metadata.file_size:
            raise ProtocolError("Received file size does not match metadata")

        if self._hasher.digest() != self.metadata.sha256:
            raise ProtocolError("Received file SHA-256 does not match metadata")

        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.close()
        self._file = None

        # Atomic create-if-absent publication on the same filesystem.
        try:
            os.link(self.temp_path, self.destination)
        except FileExistsError:
            raise
        else:
            self._published = True
            self.temp_path.unlink()
            self.temp_path = None

        return self.destination

    def close(self) -> None:
        """Close and remove an unpublished temporary file."""
        if self._file is not None:
            self._file.close()
            self._file = None

        if self.temp_path is not None:
            self.temp_path.unlink(missing_ok=True)
            self.temp_path = None

    def __enter__(self) -> "ReceiveFile":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if not self._published:
            self.close()
