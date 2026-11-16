"""Persistent settings page for Reliable UDP File Transfer."""

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from reliable_udp.protocol import MAX_PAYLOAD_SIZE
from reliable_udp.transport import (
    DEFAULT_MAX_RETRANSMISSIONS,
    DEFAULT_TIMEOUT_SECONDS,
)
from .components import UI


class SettingsPage(ttk.Frame):
    """Edit and persist default transfer configuration."""

    SETTINGS_FILE = Path.home() / ".reliable_udp" / "settings.json"

    DEFAULTS = {
        "peer_ip": "127.0.0.1",
        "port": 5001,
        "chunk_size": MAX_PAYLOAD_SIZE,
        "timeout": DEFAULT_TIMEOUT_SECONDS,
        "max_retries": DEFAULT_MAX_RETRANSMISSIONS,
        "receive_folder": str(Path.cwd() / "received"),
    }

    def __init__(self, parent, app):
        super().__init__(parent, style="App.TFrame")
        self.app = app

        self.settings = self._load_settings()

        self.peer_ip = tk.StringVar(
            value=str(self.settings["peer_ip"])
        )
        self.port = tk.StringVar(
            value=str(self.settings["port"])
        )
        self.chunk_size = tk.StringVar(
            value=str(self.settings["chunk_size"])
        )
        self.timeout = tk.StringVar(
            value=str(self.settings["timeout"])
        )
        self.max_retries = tk.StringVar(
            value=str(self.settings["max_retries"])
        )
        self.receive_folder = tk.StringVar(
            value=str(self.settings["receive_folder"])
        )
        self.save_status = tk.StringVar(value="")

        self._build_ui()

        # TransferPage is created before SettingsPage by the app.
        self._apply_to_transfer_page()

    # ---------------------------------------------------------
    # Settings storage
    # ---------------------------------------------------------

    def _load_settings(self):
        """Load saved values and safely fall back to defaults."""
        settings = dict(self.DEFAULTS)

        try:
            if self.SETTINGS_FILE.is_file():
                with self.SETTINGS_FILE.open(
                    "r",
                    encoding="utf-8",
                ) as file:
                    saved = json.load(file)

                if isinstance(saved, dict):
                    for key in settings:
                        if key in saved:
                            settings[key] = saved[key]

        except (OSError, json.JSONDecodeError):
            # A missing or damaged settings file must not stop startup.
            pass

        return settings

    def _write_settings(self):
        """Write settings atomically to avoid partial JSON files."""
        self.SETTINGS_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_file = self.SETTINGS_FILE.with_suffix(".tmp")

        with temporary_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self.settings,
                file,
                indent=4,
            )

        temporary_file.replace(self.SETTINGS_FILE)

    # ---------------------------------------------------------
    # User interface
    # ---------------------------------------------------------

    def _build_ui(self):
        style = ttk.Style(self)

        style.configure(
            "Settings.TEntry",
            padding=7,
            fieldbackground=UI.WHITE,
        )

        UI.page_header(
            self,
            "Settings",
            "Configure default transfer behavior and receive-file location.",
        ).pack(fill="x", pady=(0, 16))

        # Transfer defaults.
        transfer_card = UI.card(self, padding=18)
        transfer_card.pack(fill="x", pady=(0, 14))

        UI.section_title(
            transfer_card,
            "Transfer defaults",
            "These values will be used by the Transfer page.",
        ).pack(anchor="w", pady=(0, 16))

        fields = ttk.Frame(
            transfer_card,
            style="App.TFrame",
        )
        fields.pack(fill="x")

        fields.columnconfigure(1, weight=1)
        fields.columnconfigure(3, weight=1)

        self._add_field(
            fields,
            "Default peer IP",
            self.peer_ip,
            row=0,
            column=0,
            width=24,
        )
        self._add_field(
            fields,
            "UDP port",
            self.port,
            row=0,
            column=2,
            width=12,
        )
        self._add_field(
            fields,
            "Chunk size (bytes)",
            self.chunk_size,
            row=1,
            column=0,
            width=16,
        )
        self._add_field(
            fields,
            "Timeout (seconds)",
            self.timeout,
            row=1,
            column=2,
            width=12,
        )
        self._add_field(
            fields,
            "Maximum retries",
            self.max_retries,
            row=2,
            column=0,
            width=12,
        )

        # Receive-file settings.
        receive_card = UI.card(self, padding=18)
        receive_card.pack(fill="x", pady=(0, 14))

        UI.section_title(
            receive_card,
            "Receive files",
            "Choose where incoming files should be saved.",
        ).pack(anchor="w", pady=(0, 16))

        folder_row = ttk.Frame(
            receive_card,
            style="App.TFrame",
        )
        folder_row.pack(fill="x")
        folder_row.columnconfigure(1, weight=1)

        ttk.Label(
            folder_row,
            text="Default save folder",
            style="App.TLabel",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 12),
        )

        ttk.Entry(
            folder_row,
            textvariable=self.receive_folder,
            style="Settings.TEntry",
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, 8),
        )

        ttk.Button(
            folder_row,
            text="Browse...",
            command=self._browse_folder,
        ).grid(
            row=0,
            column=2,
        )

        # Storage information.
        info_card = UI.card(self, padding=14)
        info_card.pack(fill="x", pady=(0, 14))

        UI.section_title(
            info_card,
            "Settings storage",
            "Your preferences persist between application launches.",
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            info_card,
            text=str(self.SETTINGS_FILE),
            style="App.TLabel",
            wraplength=850,
        ).pack(anchor="w")

        # Actions.
        actions = ttk.Frame(
            self,
            style="App.TFrame",
        )
        actions.pack(fill="x", pady=(2, 0))

        ttk.Button(
            actions,
            text="Save settings",
            command=self._save_settings,
            style="Accent.TButton",
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            actions,
            text="Reset defaults",
            command=self._reset_defaults,
        ).pack(side="left")

        ttk.Label(
            actions,
            textvariable=self.save_status,
            style="Muted.TLabel",
        ).pack(side="left", padx=14)

    @staticmethod
    def _add_field(
        parent,
        label,
        variable,
        *,
        row,
        column,
        width=16,
    ):
        """Add a label and input to the two-column settings grid."""
        ttk.Label(
            parent,
            text=label,
            style="App.TLabel",
        ).grid(
            row=row,
            column=column,
            sticky="w",
            padx=(0, 10),
            pady=8,
        )

        ttk.Entry(
            parent,
            textvariable=variable,
            style="Settings.TEntry",
            width=width,
        ).grid(
            row=row,
            column=column + 1,
            sticky="ew",
            padx=(0, 22),
            pady=8,
        )

    # ---------------------------------------------------------
    # Actions
    # ---------------------------------------------------------

    def _browse_folder(self):
        folder = filedialog.askdirectory(
            title="Choose default receive folder",
            initialdir=(
                self.receive_folder.get()
                if Path(self.receive_folder.get()).is_dir()
                else str(Path.home())
            ),
        )

        if folder:
            self.receive_folder.set(folder)

    def _collect_and_validate(self):
        """Validate all fields before changing the active defaults."""
        peer_ip = self.peer_ip.get().strip()
        receive_folder = self.receive_folder.get().strip()

        if not peer_ip:
            raise ValueError("Default peer IP cannot be empty.")

        if not receive_folder:
            raise ValueError("Default receive folder cannot be empty.")

        try:
            port = int(self.port.get())
            chunk_size = int(self.chunk_size.get())
            timeout = float(self.timeout.get())
            max_retries = int(self.max_retries.get())
        except ValueError as exc:
            raise ValueError(
                "Port, chunk size, retries, and timeout must be numeric."
            ) from exc

        if not 1 <= port <= 65535:
            raise ValueError("UDP port must be between 1 and 65535.")

        if not 1 <= chunk_size <= MAX_PAYLOAD_SIZE:
            raise ValueError(
                f"Chunk size must be between 1 and {MAX_PAYLOAD_SIZE}."
            )

        if not 0 < timeout < float("inf"):
            raise ValueError(
                "Timeout must be a finite positive number."
            )

        if max_retries < 0:
            raise ValueError("Maximum retries cannot be negative.")

        return {
            "peer_ip": peer_ip,
            "port": port,
            "chunk_size": chunk_size,
            "timeout": timeout,
            "max_retries": max_retries,
            "receive_folder": str(Path(receive_folder).expanduser()),
        }

    def _save_settings(self):
        try:
            new_settings = self._collect_and_validate()
            old_settings = self.settings
            self.settings = new_settings

            try:
                self._write_settings()
            except OSError as exc:
                self.settings = old_settings
                messagebox.showerror(
                    "Could not save settings",
                    str(exc),
                    parent=self,
                )
                return

            self._apply_to_transfer_page()
            self.save_status.set("Settings saved.")

        except ValueError as exc:
            messagebox.showerror(
                "Invalid settings",
                str(exc),
                parent=self,
            )

    def _reset_defaults(self):
        if not messagebox.askyesno(
            "Reset settings",
            "Restore all settings to their default values?",
            parent=self,
        ):
            return

        self.peer_ip.set(str(self.DEFAULTS["peer_ip"]))
        self.port.set(str(self.DEFAULTS["port"]))
        self.chunk_size.set(str(self.DEFAULTS["chunk_size"]))
        self.timeout.set(str(self.DEFAULTS["timeout"]))
        self.max_retries.set(str(self.DEFAULTS["max_retries"]))
        self.receive_folder.set(str(self.DEFAULTS["receive_folder"]))

        self._save_settings()

    def _apply_to_transfer_page(self):
        """Apply defaults to the existing Transfer page controls."""
        pages = getattr(self.app, "pages", {})
        transfer_page = pages.get("Transfer")

        if transfer_page is None:
            return

        values = {
            "host": self.settings["peer_ip"],
            "port": str(self.settings["port"]),
            "chunk_size": str(self.settings["chunk_size"]),
            "timeout": str(self.settings["timeout"]),
            "retries": str(self.settings["max_retries"]),
            "destination": self.settings["receive_folder"],
        }

        for attribute, value in values.items():
            variable = getattr(transfer_page, attribute, None)
            if variable is not None and hasattr(variable, "set"):
                variable.set(value)

    def refresh_settings(self):
        """Reload settings from disk and update the form."""
        self.settings = self._load_settings()

        self.peer_ip.set(str(self.settings["peer_ip"]))
        self.port.set(str(self.settings["port"]))
        self.chunk_size.set(str(self.settings["chunk_size"]))
        self.timeout.set(str(self.settings["timeout"]))
        self.max_retries.set(str(self.settings["max_retries"]))
        self.receive_folder.set(str(self.settings["receive_folder"]))

        self._apply_to_transfer_page()
        self.save_status.set("Settings reloaded.")