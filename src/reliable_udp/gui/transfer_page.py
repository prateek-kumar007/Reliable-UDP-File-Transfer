
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

from .components import UI


class TransferPage(ttk.Frame):
    """Sender and receiver controls with thread-safe progress updates."""

    # Keep Tk responsive while processing bursts of per-packet events.
    MAX_EVENTS_PER_TICK = 200

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
        self.transfer_started_at = None
        self.current_transfer = None
        self.receiver_transfer = None

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
        """Build a compact dashboard without changing transfer behavior."""
        style = ttk.Style(self)

        style.configure(
            "App.TEntry",
            padding=(6, 4),
            fieldbackground=UI.WHITE,
        )
        style.configure(
            "Accent.TButton",
            padding=(11, 5),
            background=UI.TEAL,
            foreground=UI.WHITE,
            font=(UI.FONT, 9, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", UI.TEAL_DARK),
                ("disabled", UI.BORDER),
            ],
            foreground=[("disabled", UI.MUTED)],
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=UI.NEUTRAL_BG,
            background=UI.TEAL,
            thickness=9,
        )

        # Page heading.
        UI.page_header(
            self,
            "File Transfer",
            "Send files reliably over UDP with acknowledgements and retries.",
        ).pack(fill="x", pady=(0, 6))

        # Transfer mode and status.
        mode_card = UI.card(self, padding=8)
        mode_card.pack(fill="x", pady=(0, 6))

        ttk.Label(
            mode_card,
            text="TRANSFER MODE",
            style="App.TLabel",
        ).pack(side="left", padx=(0, 16))

        ttk.Radiobutton(
            mode_card,
            text="Send a file",
            value="Sender",
            variable=self.mode,
        ).pack(side="left", padx=(0, 12))

        ttk.Radiobutton(
            mode_card,
            text="Receive files",
            value="Receiver",
            variable=self.mode,
        ).pack(side="left")

        self.status_badge = UI.status_badge(
            mode_card,
            text="Idle",
            status="neutral",
        )
        self.status_badge.pack(side="right")

        # Connection and configuration.
        config = UI.card(self, padding=11)
        config.pack(fill="x", pady=(0, 6))

        UI.section_title(
            config,
            "Connection & configuration",
            "Set the peer, destination, and reliability options.",
        ).pack(anchor="w", pady=(0, 6))

        self.file_row = ttk.Frame(config, style="App.TFrame")
        self.file_row.pack(fill="x", pady=2)
        self.file_row.columnconfigure(1, weight=1)

        ttk.Label(
            self.file_row,
            text="Source file",
            style="App.TLabel",
            width=18,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        ttk.Entry(
            self.file_row,
            textvariable=self.file_path,
            style="App.TEntry",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ttk.Button(
            self.file_row,
            text="Browse...",
            command=self._choose_file,
            style="Accent.TButton",
        ).grid(row=0, column=2)

        self.destination_row = ttk.Frame(config, style="App.TFrame")
        self.destination_row.pack(fill="x", pady=2)
        self.destination_row.columnconfigure(1, weight=1)

        ttk.Label(
            self.destination_row,
            text="Save folder",
            style="App.TLabel",
            width=18,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        ttk.Entry(
            self.destination_row,
            textvariable=self.destination,
            style="App.TEntry",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ttk.Button(
            self.destination_row,
            text="Browse...",
            command=self._choose_destination,
        ).grid(row=0, column=2)

        network = ttk.Frame(config, style="App.TFrame")
        network.pack(fill="x", pady=(3, 2))

        ttk.Label(
            network,
            text="Peer IP",
            style="App.TLabel",
        ).pack(side="left")

        self.host_entry = ttk.Entry(
            network,
            textvariable=self.host,
            width=18,
            style="App.TEntry",
        )
        self.host_entry.pack(side="left", padx=(8, 16))

        ttk.Label(
            network,
            text="UDP port",
            style="App.TLabel",
        ).pack(side="left")

        self.port_entry = ttk.Entry(
            network,
            textvariable=self.port,
            width=8,
            style="App.TEntry",
        )
        self.port_entry.pack(side="left", padx=(8, 0))

        settings = ttk.Frame(config, style="App.TFrame")
        settings.pack(fill="x", pady=2)

        ttk.Label(
            settings,
            text="Chunk size",
            style="App.TLabel",
        ).pack(side="left")

        self.chunk_entry = ttk.Entry(
            settings,
            textvariable=self.chunk_size,
            width=9,
            style="App.TEntry",
        )
        self.chunk_entry.pack(side="left", padx=(8, 16))

        ttk.Label(
            settings,
            text="Timeout (s)",
            style="App.TLabel",
        ).pack(side="left")

        self.timeout_entry = ttk.Entry(
            settings,
            textvariable=self.timeout,
            width=8,
            style="App.TEntry",
        )
        self.timeout_entry.pack(side="left", padx=(8, 16))

        ttk.Label(
            settings,
            text="Max retries",
            style="App.TLabel",
        ).pack(side="left")

        self.retries_entry = ttk.Entry(
            settings,
            textvariable=self.retries,
            width=7,
            style="App.TEntry",
        )
        self.retries_entry.pack(side="left", padx=(8, 0))

        # Transfer actions.
        actions = ttk.Frame(self, style="App.TFrame")
        actions.pack(fill="x", pady=(0, 5))

        self.start_button = ttk.Button(
            actions,
            text="Start transfer",
            command=self._start_sender,
            style="Accent.TButton",
        )
        self.start_button.pack(side="left", padx=(0, 8))

        self.listen_button = ttk.Button(
            actions,
            text="Start listening",
            command=self._start_receiver,
        )
        self.listen_button.pack(side="left", padx=(0, 8))

        self.stop_button = ttk.Button(
            actions,
            text="Stop listening",
            command=self._stop_receiver,
            state="disabled",
        )
        self.stop_button.pack(side="left")

        ttk.Label(
            actions,
            textvariable=self.status,
            style="Muted.TLabel",
        ).pack(side="right", padx=(10, 0))

        # Live progress.
        progress = UI.card(self, padding=11)
        progress.pack(fill="x", pady=(0, 5))

        UI.section_title(
            progress,
            "Live progress",
            "Transfer progress and protocol statistics update as packets "
            "are acknowledged.",
        ).pack(anchor="w", pady=(0, 6))

        progress_head = ttk.Frame(progress, style="App.TFrame")
        progress_head.pack(fill="x", pady=(0, 4))

        ttk.Label(
            progress_head,
            textvariable=self.filename,
            style="App.TLabel",
        ).pack(side="left")

        ttk.Label(
            progress_head,
            textvariable=self.progress_text,
            style="App.TLabel",
        ).pack(side="right")

        self.progress_bar = ttk.Progressbar(
            progress,
            maximum=100,
            mode="determinate",
            style="Horizontal.TProgressbar",
        )
        self.progress_bar.pack(fill="x", pady=(0, 6), ipady=2)

        metrics = ttk.Frame(progress, style="App.TFrame")
        metrics.pack(fill="x")
        metrics.columnconfigure(
            (0, 1, 2, 3, 4),
            weight=1,
            uniform="metrics",
        )

        self._metric(metrics, "BYTES TRANSFERRED", self.bytes_text, 0)
        self._metric(metrics, "CHUNKS", self.chunks_text, 1)
        self._metric(metrics, "PACKET ATTEMPTS", self.attempts_text, 2)
        self._metric(metrics, "ELAPSED", self.elapsed_text, 3)
        self._metric(metrics, "TRANSFER RATE", self.speed_text, 4)

        # Activity panel with an empty state.
        activity_card = UI.card(self, padding=10)
        activity_card.pack(
            fill="both",
            expand=True,
            pady=(0, 2),
        )
        activity_card.configure(height=155)
        activity_card.pack_propagate(False)

        activity_header = ttk.Frame(
            activity_card,
            style="App.TFrame",
        )
        activity_header.pack(fill="x", pady=(0, 5))

        UI.section_title(
            activity_header,
            "Activity",
            "Recent sender and receiver events.",
        ).pack(side="left", anchor="w")

        ttk.Button(
            activity_header,
            text="Clear",
            command=self._clear_activity,
        ).pack(side="right")

        text_frame = tk.Frame(activity_card, bg=UI.WHITE)
        text_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
        )
        scrollbar.pack(side="right", fill="y")

        self.activity = tk.Text(
            text_frame,
            height=4,
            wrap="word",
            state="disabled",
            bg=UI.WHITE,
            fg=UI.TEXT,
            relief="flat",
            bd=0,
            font=(UI.FONT, 9),
            padx=7,
            pady=5,
            yscrollcommand=scrollbar.set,
        )
        self.activity.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.activity.yview)

        self.activity_empty = tk.Label(
            text_frame,
            text="No transfer activity yet",
            bg=UI.WHITE,
            fg=UI.MUTED,
            font=(UI.FONT, 10),
        )
        self.activity_empty.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
        )

        self._mode_changed()

    @staticmethod
    def _metric(parent, title, value, column):
        cell = tk.Frame(
            parent,
            bg=UI.WHITE,
            padx=7,
            pady=5,
            highlightbackground=UI.BORDER,
            highlightthickness=1,
        )
        cell.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=(0, 5),
        )

        tk.Label(
            cell,
            text=title,
            bg=UI.WHITE,
            fg=UI.MUTED,
            font=(UI.FONT, 8, "bold"),
        ).pack(anchor="w")

        tk.Label(
            cell,
            textvariable=value,
            bg=UI.WHITE,
            fg=UI.TEXT,
            font=(UI.FONT, 10, "bold"),
        ).pack(anchor="w", pady=(3, 0))

    def _clear_activity(self):
        """Clear the activity panel and restore its empty state."""
        self.activity.configure(state="normal")
        self.activity.delete("1.0", "end")
        self.activity.configure(state="disabled")
        self.activity_empty.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
        )

    def _mode_changed(self, *_):
        sender_mode = self.mode.get() == "Sender"

        self._set_row_visible(self.file_row, sender_mode)
        self._set_row_visible(self.destination_row, not sender_mode)

        self.start_button.configure(
            state=(
                "normal"
                if sender_mode and not self.transfer_active
                else "disabled"
            )
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

        status = self.status.get().lower()
        if "complete" in status:
            badge_text, badge_status = self.status.get(), "success"
        elif "fail" in status or "error" in status:
            badge_text, badge_status = self.status.get(), "error"
        elif (
            "listen" in status
            or "sending" in status
            or "stopping" in status
        ):
            badge_text, badge_status = self.status.get(), "active"
        else:
            badge_text, badge_status = self.status.get(), "neutral"

        self.status_badge.configure(
            text=badge_text,
            bg={
                "success": UI.SUCCESS_BG,
                "error": UI.ERROR_BG,
                "active": UI.TEAL_LIGHT,
                "neutral": UI.NEUTRAL_BG,
            }.get(badge_status, UI.NEUTRAL_BG),
            fg={
                "success": UI.SUCCESS,
                "error": UI.ERROR,
                "active": UI.TEAL_DARK,
                "neutral": UI.MUTED,
            }.get(badge_status, UI.MUTED),
        )

    @staticmethod
    def _set_row_visible(widget, visible):
        if visible:
            widget.pack(fill="x", pady=2)
        else:
            widget.pack_forget()

    def _choose_file(self):
        path = filedialog.askopenfilename(
            title="Select a file to send",
        )
        if path:
            self.file_path.set(path)
            self.filename.set(Path(path).name)

    def _choose_destination(self):
        path = filedialog.askdirectory(
            title="Choose received-file folder",
        )
        if path:
            self.destination.set(path)

    def _log(self, message):
        """Append an event and record it in the shared application logs."""
        timestamp = time.strftime("%H:%M:%S")

        self.activity.configure(state="normal")
        self.activity.insert("end", f"[{timestamp}] {message}\n")
        self.activity.see("end")
        self.activity.configure(state="disabled")

        self.activity_empty.place_forget()

        if hasattr(self.app, "record_log"):
            self.app.record_log(message)

    def _start_timer(self):
        """Start timing once, when a transfer begins."""
        if self.started_at is not None:
            return

        self.started_at = time.monotonic()
        self.last_speed_time = self.started_at
        self.speed_bytes = 0

    def _finish_timer(self):
        """Freeze elapsed time when a transfer ends."""
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
                return (
                    f"{amount:.1f} {unit}"
                    if unit != "B"
                    else f"{int(amount)} B"
                )
            amount /= 1024

        return f"{amount:.1f} TB"

    def _start_sender(self):
        if self.transfer_active:
            return

        source = Path(self.file_path.get().strip())
        if not source.is_file():
            messagebox.showerror(
                "Invalid file",
                "Select an existing source file.",
                parent=self,
            )
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
                raise ValueError(
                    "Timeout must be a finite positive number."
                )
            if retries < 0:
                raise ValueError("Max retries cannot be negative.")

        except ValueError as exc:
            messagebox.showerror(
                "Invalid settings",
                str(exc),
                parent=self,
            )
            return

        self._reset_metrics()
        self.transfer_started_at = time.monotonic()
        self.current_transfer = {
            "filename": source.name,
            "size": source.stat().st_size,
        }
        self.transfer_active = True
        self.status.set("Sending")
        self._mode_changed()
        self._log(f"Starting transfer to {host}:{port}")

        def worker():
            try:
                with socket.socket(
                    socket.AF_INET,
                    socket.SOCK_DGRAM,
                ) as sock:
                    result = send_file(
                        sock,
                        source,
                        (host, port),
                        chunk_size=chunk,
                        timeout=timeout,
                        max_retransmissions=retries,
                        event_callback=self.events.put,
                    )

                self.events.put({
                    "event": "sender_finished",
                    "result": result,
                })

            except Exception as exc:
                self.events.put({
                    "event": "transfer_failed",
                    "error": str(exc),
                })

        threading.Thread(target=worker, daemon=True).start()

    def _start_receiver(self):
        """Bind the UDP socket before reporting that the receiver is listening."""
        if self.receiver_thread is not None:
            return

        destination = Path(self.destination.get().strip())
        sock = None

        try:
            destination.mkdir(parents=True, exist_ok=True)
            port = int(self.port.get())
            if not 1 <= port <= 65535:
                raise ValueError("Port must be between 1 and 65535.")

            # Bind on the GUI thread first so address-in-use and permission
            # errors are reported immediately instead of showing a false
            # "Listening" status.
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("0.0.0.0", port))
            sock.settimeout(0.25)

        except (OSError, ValueError) as exc:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

            self.status.set("Receiver error")
            self._log(f"Receiver could not bind UDP port: {exc}")
            self._mode_changed()
            messagebox.showerror(
                "Receiver could not start",
                f"Could not listen on UDP port {self.port.get().strip()}.\\n\\n"
                f"{exc}\\n\\n"
                "Close any other application using this port, then try again.",
                parent=self,
            )
            return

        self.receiver_stop.clear()
        self._reset_metrics()
        self.receiver_socket = sock
        self.status.set(f"Listening on UDP {port}")
        self._log(f"Listening on 0.0.0.0:{port}")
        self._mode_changed()

        self.receiver_thread = threading.Thread(
            target=self._receiver_worker,
            args=(destination, sock),
            daemon=True,
        )
        self.receiver_thread.start()
        self._mode_changed()

    def _receiver_worker(self, destination, sock):
        """Process datagrams in a worker thread without blocking Tkinter."""
        service = None

        try:
            service = ReceiverService(destination)

            # The socket was already bound in _start_receiver. Keep all
            # blocking receive and protocol work in this background thread.
            with sock:
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
                                    metadata.file_size
                                    + metadata.chunk_size
                                    - 1
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
                                "chunks_acknowledged": (
                                    state.next_expected_sequence
                                ),
                                "total_chunks": (
                                    state.metadata.file_size
                                    + state.metadata.chunk_size
                                    - 1
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
                "error": f"{type(exc).__name__}: {exc}",
            })

        finally:
            if service is not None:
                service.close()

            try:
                sock.close()
            except OSError:
                pass

            self.receiver_socket = None
            self.events.put({"event": "receiver_stopped"})

    def _stop_receiver(self):
        if self.receiver_thread is None:
            return

        self.receiver_stop.set()
        self.status.set("Stopping receiver...")
        self._mode_changed()
        self._log("Receiver stop requested.")

    def _record_transfer(
        self,
        *,
        direction,
        filename,
        size,
        duration,
        status,
        integrity,
        error=None,
    ):
        """Save a transfer result through the app's history interface."""
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "filename": str(filename or "Unknown file"),
            "direction": direction,
            "bytes_transferred": max(0, int(size or 0)),
            "duration_seconds": round(max(0.0, float(duration or 0)), 2),
            "status": status,
            "integrity": integrity,
        }

        if error:
            record["error"] = str(error)

        recorder = getattr(self.app, "record_transfer", None)
        if callable(recorder):
            recorder(record)
        else:
            self._log("History unavailable: app.record_transfer() is missing.")

    def _process_events(self):
        processed = 0
        try:
            while processed < self.MAX_EVENTS_PER_TICK:
                event = self.events.get_nowait()
                processed += 1
                name = event.get("event", "")

                if name == "transfer_started":
                    self._start_timer()
                    self.filename.set(str(event.get("filename", "")))
                    self._log(f"Transfer started: {event.get('filename', '')}")

                elif name == "packet_sent":
                    message_type = event.get("message_type", "packet")
                    attempt = event.get("attempt", 1)
                    retransmission = bool(event.get("retransmission"))
                    self.attempts_text.set(
                        str(int(self.attempts_text.get()) + 1)
                    )

                    # DATA packets can produce thousands of events for a
                    # large file. Log START/END and retries, not every DATA.
                    if message_type != "DATA" or retransmission:
                        suffix = " (retry)" if retransmission else ""
                        self._log(
                            f"Sent {message_type}, "
                            f"seq {event.get('sequence')}, "
                            f"attempt {attempt}{suffix}"
                        )

                elif name == "ack_received":
                    message_type = event.get("message_type", "packet")
                    attempt = event.get("attempt", 1)

                    # Avoid flooding Tk and the shared log with thousands
                    # of routine DATA acknowledgements.
                    if message_type != "DATA" or attempt > 1:
                        self._log(
                            f"Received {message_type} ACK for "
                            f"sequence {event.get('sequence')}"
                            + (f" (attempt {attempt})" if attempt > 1 else "")
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
                    self.receiver_transfer = {
                        "filename": event.get("filename", "Unknown file"),
                        "size": int(event.get("total_bytes", 0)),
                        "started_at": time.monotonic(),
                    }
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
                    duration = (
                        time.monotonic() - self.transfer_started_at
                        if self.transfer_started_at is not None
                        else 0.0
                    )
                    transfer = self.current_transfer or {}

                    self._finish_timer()
                    self.transfer_active = False
                    self.status.set("Completed")
                    self._mode_changed()

                    self._record_transfer(
                        direction="Send",
                        filename=transfer.get(
                            "filename",
                            self.filename.get(),
                        ),
                        size=transfer.get("size", 0),
                        duration=duration,
                        status="COMPLETED",
                        integrity="Sender acknowledged",
                    )

                    self.current_transfer = None
                    self.transfer_started_at = None
                    self._log(f"Sender completed: {event.get('result')}")

                elif name == "receiver_finished":
                    transfer = self.receiver_transfer or {}
                    duration = (
                        time.monotonic() - transfer["started_at"]
                        if "started_at" in transfer
                        else 0.0
                    )
                    filename = event.get(
                        "filename",
                        transfer.get("filename", "Unknown file"),
                    )
                    total = int(
                        event.get("total_bytes", transfer.get("size", 0))
                    )

                    self._finish_timer()
                    self.status.set("Completed — integrity verified")
                    self.progress_bar["value"] = 100
                    self.progress_text.set("100%")
                    self.bytes_text.set(
                        f"{self._format_bytes(total)} / "
                        f"{self._format_bytes(total)}"
                    )
                    self._mode_changed()

                    self._record_transfer(
                        direction="Receive",
                        filename=filename,                        size=total,
                        duration=duration,
                        status="COMPLETED",
                        integrity="Verified",
                    )

                    self.receiver_transfer = None
                    self._log(f"Receiver verified and saved {filename}")

                elif name == "transfer_failed":
                    duration = (
                        time.monotonic() - self.transfer_started_at
                        if self.transfer_started_at is not None
                        else 0.0
                    )
                    transfer = self.current_transfer or {}

                    self._finish_timer()
                    self.transfer_active = False
                    self.status.set("Failed")
                    self._mode_changed()

                    self._record_transfer(
                        direction="Send",
                        filename=transfer.get(
                            "filename",
                            self.filename.get(),
                        ),
                        size=0,
                        duration=duration,
                        status="FAILED",
                        integrity="Not verified",
                        error=event.get("error"),
                    )

                    self.current_transfer = None
                    self.transfer_started_at = None
                    self._log(f"Transfer failed: {event.get('error')}")

                elif name == "receiver_failed":
                    transfer = self.receiver_transfer or {}
                    duration = (
                        time.monotonic() - transfer["started_at"]
                        if "started_at" in transfer
                        else 0.0
                    )

                    self._finish_timer()
                    self.status.set("Receiver error")
                    self._mode_changed()

                    if transfer:
                        self._record_transfer(
                            direction="Receive",
                            filename=transfer.get(
                                "filename",
                                "Unknown file",
                            ),
                            size=0,
                            duration=duration,
                            status="FAILED",
                            integrity="Not verified",
                            error=event.get("error"),
                        )

                    self.receiver_transfer = None
                    self._log(f"Receiver error: {event.get('error')}")

                elif name == "receiver_ignored":
                    self._log(str(event.get("message")))

                elif name == "receiver_stopped":
                    if self.started_at is not None:
                        self._finish_timer()

                    self.receiver_thread = None
                    self.receiver_socket = None

                    if self.status.get().startswith(("Listening", "Stopping")):
                        self.status.set("Idle")

                    self._mode_changed()

        except queue.Empty:
            pass

        if self.started_at is not None:
            elapsed = time.monotonic() - self.started_at
            self.elapsed_text.set(f"{elapsed:.1f} s")

        # Drain event bursts in bounded batches so Tk can remain responsive.
        delay_ms = 1 if processed >= self.MAX_EVENTS_PER_TICK else 100
        self.after(delay_ms, self._process_events)

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