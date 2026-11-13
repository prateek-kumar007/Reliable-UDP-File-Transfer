
"""Transfer dashboard for the Reliable UDP File Transfer application."""

import queue
import socket
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from reliable_udp.protocol import (
    MAX_DATAGRAM_SIZE,
    MAX_PAYLOAD_SIZE,
    MessageType,
    ProtocolError,
    decode_packet,
)
from reliable_udp.receiver_service import ReceiverService
from reliable_udp.sender import send_file
from reliable_udp.transport import (
    DEFAULT_MAX_RETRANSMISSIONS,
    DEFAULT_TIMEOUT_SECONDS,
)


class TransferPage(ttk.Frame):
    """Sender and receiver controls with thread-safe progress updates."""

    def __init__(self, parent, app):
        super().__init__(parent, style="App.TFrame")
        self.app = app
        self.events = queue.Queue()
        self.receiver_thread = None
        self.receiver_socket = None
        self.receiver_stop = threading.Event()
        self.transfer_active = False
        self.started_at = None
        self.last_bytes = 0
        self.last_speed_time = None
        self.speed_bytes = 0

        self.mode = tk.StringVar(value="Sender")
        self.file_path = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.cwd() / "received"))
        self.host = tk.StringVar(value="127.0.0.1")
        self.port = tk.StringVar(value="5001")
        self.chunk_size = tk.StringVar(value=str(MAX_PAYLOAD_SIZE))
        self.timeout = tk.StringVar(value=str(DEFAULT_TIMEOUT_SECONDS))
        self.retries = tk.StringVar(value=str(DEFAULT_MAX_RETRANSMISSIONS))

        self.status = tk.StringVar(value="Idle")
        self.filename = tk.StringVar(value="No file selected")
        self.progress_text = tk.StringVar(value="0%")
        self.bytes_text = tk.StringVar(value="0 B / 0 B")
        self.chunks_text = tk.StringVar(value="0 / 0")
        self.attempts_text = tk.StringVar(value="0")
        self.elapsed_text = tk.StringVar(value="0.0 s")
        self.speed_text = tk.StringVar(value="0 B/s")

        self._build_ui()
        self.mode.trace_add("write", self._mode_changed)
        self.after(100, self._process_events)

    def _build_ui(self):
        ttk.Label(
            self, text="File Transfer", style="Title.TLabel"
        ).pack(anchor="w")

        ttk.Label(
            self,
            text="Send files reliably over UDP with acknowledgements and retries.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 18))

        mode_frame = ttk.Frame(self, style="App.TFrame")
        mode_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(mode_frame, text="Mode:", style="App.TLabel").pack(
            side="left", padx=(0, 12)
        )
        ttk.Radiobutton(
            mode_frame, text="Sender", value="Sender", variable=self.mode
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            mode_frame, text="Receiver", value="Receiver", variable=self.mode
        ).pack(side="left")

        config = ttk.LabelFrame(self, text="Transfer Configuration", padding=14)
        config.pack(fill="x", pady=(0, 12))
        config.columnconfigure(1, weight=1)

        self.file_row = ttk.Frame(config)
        self.file_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)
        self.file_row.columnconfigure(1, weight=1)
        ttk.Label(self.file_row, text="Source file").grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        ttk.Entry(self.file_row, textvariable=self.file_path).grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            self.file_row, text="Browse...", command=self._choose_file
        ).grid(row=0, column=2)

        self.destination_row = ttk.Frame(config)
        self.destination_row.grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=5
        )
        self.destination_row.columnconfigure(1, weight=1)
        ttk.Label(self.destination_row, text="Save received files").grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        ttk.Entry(
            self.destination_row, textvariable=self.destination
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(
            self.destination_row,
            text="Browse...",
            command=self._choose_destination,
        ).grid(row=0, column=2)

        network = ttk.Frame(config)
        network.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

        ttk.Label(network, text="Peer IP").pack(side="left")
        self.host_entry = ttk.Entry(
            network, textvariable=self.host, width=18
        )
        self.host_entry.pack(side="left", padx=(8, 18))

        ttk.Label(network, text="UDP port").pack(side="left")
        self.port_entry = ttk.Entry(
            network, textvariable=self.port, width=8
        )
        self.port_entry.pack(side="left", padx=(8, 0))

        settings = ttk.Frame(config)
        settings.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)

        ttk.Label(settings, text="Chunk size (bytes)").pack(side="left")
        self.chunk_entry = ttk.Entry(
            settings, textvariable=self.chunk_size, width=9
        )
        self.chunk_entry.pack(side="left", padx=(6, 18))

        ttk.Label(settings, text="Timeout (s)").pack(side="left")
        self.timeout_entry = ttk.Entry(
            settings, textvariable=self.timeout, width=8
        )
        self.timeout_entry.pack(side="left", padx=(6, 18))

        ttk.Label(settings, text="Max retries").pack(side="left")
        self.retries_entry = ttk.Entry(
            settings, textvariable=self.retries, width=7
        )
        self.retries_entry.pack(side="left", padx=(6, 0))

        controls = ttk.Frame(self, style="App.TFrame")
        controls.pack(fill="x", pady=(0, 12))

        self.start_button = ttk.Button(
            controls, text="Start Transfer", command=self._start_sender
        )
        self.start_button.pack(side="left", padx=(0, 8))

        self.listen_button = ttk.Button(
            controls, text="Start Listening", command=self._start_receiver
        )
        self.listen_button.pack(side="left", padx=(0, 8))

        self.stop_button = ttk.Button(
            controls,
            text="Stop Listening",
            command=self._stop_receiver,
            state="disabled",
        )
        self.stop_button.pack(side="left")

        ttk.Label(
            controls, textvariable=self.status, style="Muted.TLabel"
        ).pack(side="right")

        progress = ttk.LabelFrame(self, text="Live Progress", padding=14)
        progress.pack(fill="x", pady=(0, 12))

        top = ttk.Frame(progress)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(
            top, textvariable=self.filename, style="App.TLabel"
        ).pack(side="left")
        ttk.Label(
            top, textvariable=self.progress_text, style="App.TLabel"
        ).pack(side="right")

        self.progress_bar = ttk.Progressbar(
            progress, maximum=100, mode="determinate"
        )
        self.progress_bar.pack(fill="x", pady=(0, 12))

        metrics = ttk.Frame(progress)
        metrics.pack(fill="x")

        self._metric(metrics, "Acknowledged / received", self.bytes_text, 0)
        self._metric(metrics, "Chunks", self.chunks_text, 1)
        self._metric(metrics, "Attempts", self.attempts_text, 2)
        self._metric(metrics, "Elapsed", self.elapsed_text, 3)
        self._metric(metrics, "Transfer rate", self.speed_text, 4)

        log_frame = ttk.LabelFrame(self, text="Activity", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.activity = tk.Text(
            log_frame,
            height=7,
            wrap="word",
            state="disabled",
            bg="#FFFFFF",
            fg="#172B32",
            relief="flat",
            font=("Consolas", 9),
        )
        self.activity.pack(fill="both", expand=True)

        self._mode_changed()

    @staticmethod
    def _metric(parent, title, value, column):
        cell = ttk.Frame(parent)
        cell.grid(row=0, column=column, sticky="w", padx=(0, 18))
        ttk.Label(cell, text=title, style="Muted.TLabel").pack(anchor="w")
        ttk.Label(cell, textvariable=value, style="App.TLabel").pack(
            anchor="w", pady=(4, 0)
        )

    def _mode_changed(self, *_):
        sender_mode = self.mode.get() == "Sender"

        self._set_row_visible(self.file_row, sender_mode)
        self._set_row_visible(self.destination_row, not sender_mode)

        self.start_button.configure(
            state="normal" if sender_mode and not self.transfer_active else "disabled"
        )
        self.listen_button.configure(
            state=(
                "normal"
                if not sender_mode and self.receiver_thread is None
                else "disabled"
            )
        )
        self.stop_button.configure(
            state="normal" if self.receiver_thread is not None else "disabled"
        )

        self.host_entry.configure(
            state="normal" if sender_mode else "disabled"
        )
        self.chunk_entry.configure(
            state="normal" if sender_mode else "disabled"
        )
        self.timeout_entry.configure(
            state="normal" if sender_mode else "disabled"
        )
        self.retries_entry.configure(
            state="normal" if sender_mode else "disabled"
        )

    @staticmethod
    def _set_row_visible(widget, visible):
        if visible:
            widget.grid()
        else:
            widget.grid_remove()

    def _choose_file(self):
        path = filedialog.askopenfilename(title="Select a file to send")
        if path:
            self.file_path.set(path)
            self.filename.set(Path(path).name)

    def _choose_destination(self):
        path = filedialog.askdirectory(title="Choose received-file folder")
        if path:
            self.destination.set(path)

    def _log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.activity.configure(state="normal")
        self.activity.insert("end", f"[{timestamp}] {message}\n")
        self.activity.see("end")
        self.activity.configure(state="disabled")

    def _start_timer(self):
        """Start timing once, when a transfer begins (not while listening)."""
        if self.started_at is not None:
            return
        self.started_at = time.monotonic()
        self.last_speed_time = self.started_at
        self.speed_bytes = 0

    def _finish_timer(self):
        """Freeze the elapsed time when a transfer ends."""
        if self.started_at is not None:
            elapsed = time.monotonic() - self.started_at
            self.elapsed_text.set(f"{elapsed:.1f} s")
        self.started_at = None

    def _reset_metrics(self):
        self.progress_bar["value"] = 0
        self.progress_text.set("0%")
        self.bytes_text.set("0 B / 0 B")
        self.chunks_text.set("0 / 0")
        self.attempts_text.set("0")
        self.elapsed_text.set("0.0 s")
        self.speed_text.set("0 B/s")
        self.last_bytes = 0
        self.speed_bytes = 0
        self.started_at = None
        self.last_speed_time = None

    @staticmethod
    def _format_bytes(value):
        amount = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if amount < 1024 or unit == "TB":
                return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
            amount /= 1024
        return f"{amount:.1f} TB"

    def _start_sender(self):
        if self.transfer_active:
            return

        source = Path(self.file_path.get().strip())
        if not source.is_file():
            messagebox.showerror("Invalid file", "Select an existing source file.")
            return

        try:
            host = self.host.get().strip()
            port = int(self.port.get())
            chunk = int(self.chunk_size.get())
            timeout = float(self.timeout.get())
            retries = int(self.retries.get())

            if not host:
                raise ValueError("Peer IP cannot be empty.")
            if not 1 <= port <= 65535:
                raise ValueError("Port must be between 1 and 65535.")
            if not 1 <= chunk <= MAX_PAYLOAD_SIZE:
                raise ValueError(
                    f"Chunk size must be between 1 and {MAX_PAYLOAD_SIZE}."
                )
            if not 0 < timeout < float("inf"):
                raise ValueError("Timeout must be a finite positive number.")
            if retries < 0:
                raise ValueError("Max retries cannot be negative.")
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        self._reset_metrics()
        self.transfer_active = True
        self.status.set("Sending")
        self._mode_changed()
        self._log(f"Starting transfer to {host}:{port}")

        def worker():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    result = send_file(
                        sock,
                        source,
                        (host, port),
                        chunk_size=chunk,
                        timeout=timeout,
                        max_retransmissions=retries,
                        event_callback=self.events.put,
                    )
                self.events.put({"event": "sender_finished", "result": result})
            except Exception as exc:
                self.events.put({
                    "event": "transfer_failed",
                    "error": str(exc),
                })

        threading.Thread(target=worker, daemon=True).start()

    def _start_receiver(self):
        if self.receiver_thread is not None:
            return

        destination = Path(self.destination.get().strip())
        try:
            destination.mkdir(parents=True, exist_ok=True)
            port = int(self.port.get())
            if not 1 <= port <= 65535:
                raise ValueError("Port must be between 1 and 65535.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Invalid receiver settings", str(exc))
            return

        self.receiver_stop.clear()
        self._reset_metrics()
        self.status.set(f"Listening on UDP {port}")
        self._log(f"Listening on 0.0.0.0:{port}")
        self._mode_changed()

        self.receiver_thread = threading.Thread(
            target=self._receiver_worker,
            args=(destination, port),
            daemon=True,
        )
        self.receiver_thread.start()
        self._mode_changed()

    def _receiver_worker(self, destination, port):
        service = None
        try:
            service = ReceiverService(destination)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                self.receiver_socket = sock
                sock.bind(("0.0.0.0", port))
                sock.settimeout(0.25)

                while not self.receiver_stop.is_set():
                    try:
                        datagram, peer = sock.recvfrom(MAX_DATAGRAM_SIZE)
                    except TimeoutError:
                        continue
                    except OSError:
                        if self.receiver_stop.is_set():
                            break
                        raise

                    try:
                        packet = decode_packet(datagram)
                    except ProtocolError:
                        self.events.put({
                            "event": "receiver_ignored",
                            "message": f"Ignored malformed datagram from {peer}",
                        })
                        continue

                    metadata_before = service.state.metadata
                    response = service.handle_datagram(datagram, peer)

                    if response is not None:
                        sock.sendto(response, peer)

                    if packet.message_type is MessageType.START:
                        metadata = service.state.metadata
                        if metadata is not None:
                            self.events.put({
                                "event": "receiver_started",
                                "filename": metadata.filename,
                                "total_bytes": metadata.file_size,
                                "total_chunks": (
                                    metadata.file_size + metadata.chunk_size - 1
                                ) // metadata.chunk_size,
                                "peer": peer,
                            })

                    elif packet.message_type is MessageType.DATA:
                        state = service.state
                        if state.metadata is not None:
                            self.events.put({
                                "event": "receiver_progress",
                                "filename": state.metadata.filename,
                                "bytes_acknowledged": state.received_bytes,
                                "total_bytes": state.metadata.file_size,
                                "chunks_acknowledged": state.next_expected_sequence,
                                "total_chunks": (
                                    state.metadata.file_size
                                    + state.metadata.chunk_size - 1
                                ) // state.metadata.chunk_size,
                            })

                    elif (
                        packet.message_type is MessageType.END
                        and response is not None
                        and metadata_before is not None
                    ):
                        self.events.put({
                            "event": "receiver_finished",
                            "filename": metadata_before.filename,
                            "total_bytes": metadata_before.file_size,
                        })

        except Exception as exc:
            self.events.put({
                "event": "receiver_failed",
                "error": str(exc),
            })
        finally:
            if service is not None:
                service.close()
            self.receiver_socket = None
            self.events.put({"event": "receiver_stopped"})

    def _stop_receiver(self):
        if self.receiver_thread is None:
            return
        self.receiver_stop.set()
        self.status.set("Stopping receiver...")
        self._log("Receiver stop requested.")

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                name = event.get("event", "")

                if name == "transfer_started":
                    self._start_timer()
                    self.filename.set(str(event.get("filename", "")))
                    self._log(
                        f"Transfer started: {event.get('filename', '')}"
                    )
                elif name == "packet_sent":
                    message_type = event.get("message_type", "packet")
                    attempt = event.get("attempt", 1)
                    self.attempts_text.set(str(
                        int(self.attempts_text.get()) + 1
                    ))
                    suffix = " (retry)" if event.get("retransmission") else ""
                    self._log(
                        f"Sent {message_type}, seq {event.get('sequence')}, "
                        f"attempt {attempt}{suffix}"
                    )
                elif name == "ack_received":
                    self._log(
                        f"Received {event.get('message_type')} ACK for "
                        f"sequence {event.get('sequence')}"
                    )
                elif name == "timeout":
                    self._log(
                        f"Timeout: {event.get('message_type')} sequence "
                        f"{event.get('sequence')}"
                    )
                elif name in ("progress", "receiver_progress"):
                    self._update_progress(event)
                elif name == "receiver_started":
                    self._start_timer()
                    self.filename.set(str(event.get("filename", "")))
                    self._update_progress({
                        "bytes_acknowledged": 0,
                        "total_bytes": event.get("total_bytes", 0),
                        "chunks_acknowledged": 0,
                        "total_chunks": event.get("total_chunks", 0),
                    })
                    self._log(
                        f"Receiving {event.get('filename')} from "
                        f"{event.get('peer')}"
                    )
                elif name == "sender_finished":
                    self._finish_timer()
                    self.transfer_active = False
                    self.status.set("Completed")
                    self._mode_changed()
                    self._log(f"Sender completed: {event.get('result')}")
                elif name == "receiver_finished":
                    self._finish_timer()
                    self.status.set("Completed — integrity verified")
                    self.progress_bar["value"] = 100
                    self.progress_text.set("100%")
                    total = int(event.get("total_bytes", 0))
                    self.bytes_text.set(
                        f"{self._format_bytes(total)} / {self._format_bytes(total)}"
                    )
                    self._log(
                        f"Receiver verified and saved {event.get('filename')}"
                    )
                elif name == "transfer_failed":
                    self._finish_timer()
                    self.transfer_active = False
                    self.status.set("Failed")
                    self._mode_changed()
                    self._log(f"Transfer failed: {event.get('error')}")
                elif name == "receiver_failed":
                    self._finish_timer()
                    self.status.set("Receiver error")
                    self._log(f"Receiver error: {event.get('error')}")
                elif name == "receiver_ignored":
                    self._log(str(event.get("message")))
                elif name == "receiver_stopped":
                    if self.started_at is not None:
                        self._finish_timer()
                    self.receiver_thread = None
                    self.receiver_socket = None
                    status = self.status.get()
                    if status.startswith(("Listening", "Stopping")):
                        self.status.set("Idle")

        except queue.Empty:
            pass

        if self.started_at is not None:
            elapsed = time.monotonic() - self.started_at
            self.elapsed_text.set(f"{elapsed:.1f} s")

        self.after(100, self._process_events)

    def _update_progress(self, event):
        current = int(event.get("bytes_acknowledged", 0))
        total = int(event.get("total_bytes", 0))
        chunks = int(event.get("chunks_acknowledged", 0))
        total_chunks = int(event.get("total_chunks", 0))

        percent = 100 if total == 0 else min(100, current * 100 / total)
        self.progress_bar["value"] = percent
        self.progress_text.set(f"{percent:.1f}%")
        self.bytes_text.set(
            f"{self._format_bytes(current)} / {self._format_bytes(total)}"
        )
        self.chunks_text.set(f"{chunks} / {total_chunks}")

        now = time.monotonic()
        if self.last_speed_time is not None and now > self.last_speed_time:
            delta = current - self.speed_bytes
            rate = max(0, delta) / (now - self.last_speed_time)
            self.speed_text.set(f"{self._format_bytes(rate)}/s")
        self.speed_bytes = current
        self.last_speed_time = now

    def destroy(self):
        self.receiver_stop.set()
        if self.receiver_socket is not None:
            try:
                self.receiver_socket.close()
            except OSError:
                pass
        super().destroy()
