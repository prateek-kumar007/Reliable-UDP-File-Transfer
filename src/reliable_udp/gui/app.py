
"""Main window, navigation, styling, and shared application state."""

# Configure Windows DPI awareness before creating the Tkinter window.
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass

import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from reliable_udp.gui.about_page import AboutPage
from reliable_udp.gui.components import UI
from reliable_udp.gui.history_page import HistoryPage
from reliable_udp.gui.logs_page import LogsPage
from reliable_udp.gui.settings_page import SettingsPage
from reliable_udp.gui.transfer_page import TransferPage


class ReliableUDPApp(tk.Tk):
    """Main application window for Reliable UDP File Transfer."""

    BG = "#F4F7F8"
    SIDEBAR = "#123B43"
    SIDEBAR_HOVER = "#1B5059"
    TEAL = "#0D9488"
    TEAL_DARK = "#0F766E"
    TEAL_LIGHT = "#CCFBF1"
    WHITE = "#FFFFFF"
    TEXT = "#172B32"
    MUTED = "#647780"
    BORDER = "#DCE5E8"
    SUCCESS = "#15803D"
    WARNING = "#B45309"
    ERROR = "#B91C1C"

    MAX_LOG_ENTRIES = 2000
    MAX_HISTORY_ENTRIES = 1000

    def __init__(self):
        super().__init__()

        self.title("Reliable UDP File Transfer")
        self.geometry("1240x800")
        self.minsize(1050, 680)
        self.configure(bg=self.BG)

        # Shared state used by application pages.
        self.log_entries = []
        self.transfer_history = []
        self.history_file = Path.home() / ".reliable_udp" / "transfer_history.json"
        self._load_transfer_history()
        self.pages = {}
        self.nav_buttons = {}
        self.current_page = "Transfer"

        self._configure_styles()
        self._build_layout()
        self.show_page("Transfer")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------
    # Persistent transfer history
    # ---------------------------------------------------------

    def _load_transfer_history(self):
        """Load saved transfer history without preventing the app from opening."""
        try:
            if not self.history_file.exists():
                self.transfer_history = []
                return

            with self.history_file.open("r", encoding="utf-8") as file:
                saved_history = json.load(file)

            if not isinstance(saved_history, list):
                raise ValueError("Transfer history must contain a JSON list.")

            self.transfer_history = [
                dict(item) for item in saved_history if isinstance(item, dict)
            ][-self.MAX_HISTORY_ENTRIES:]

        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.transfer_history = []
            # At this point the GUI pages are not built yet, so keep this
            # warning in the in-memory log and allow startup to continue.
            self.log_entries.append({
                "timestamp": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "level": "WARNING",
                "message": f"Could not load transfer history: {exc}",
            })

    def _save_transfer_history(self):
        """Persist history using a temporary file to reduce corruption risk."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self.history_file.with_suffix(".json.tmp")

        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(
                self.transfer_history,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.flush()

        temporary_file.replace(self.history_file)

    # ---------------------------------------------------------
    # Styling
    # ---------------------------------------------------------

    def _configure_styles(self):
        """Configure application-wide ttk styles."""
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "App.TFrame",
            background=self.BG,
        )
        style.configure(
            "Card.TFrame",
            background=self.WHITE,
            relief="flat",
            borderwidth=0,
        )
        style.configure(
            "App.TLabel",
            background=self.BG,
            foreground=self.TEXT,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Title.TLabel",
            background=self.BG,
            foreground=self.TEXT,
            font=("Segoe UI", 23, "bold"),
        )
        style.configure(
            "Section.TLabel",
            background=self.WHITE,
            foreground=self.TEXT,
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=self.BG,
            foreground=self.MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "CardMuted.TLabel",
            background=self.WHITE,
            foreground=self.MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "App.TButton",
            font=("Segoe UI", 10),
            padding=(12, 8),
            background=self.WHITE,
            foreground=self.TEXT,
            bordercolor=self.BORDER,
        )
        style.map(
            "App.TButton",
            background=[
                ("active", "#EAF1F3"),
                ("disabled", "#EEF2F3"),
            ],
            foreground=[
                ("disabled", "#94A3A8"),
            ],
        )
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(14, 9),
            background=self.TEAL,
            foreground=self.WHITE,
            bordercolor=self.TEAL,
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", self.TEAL_DARK),
                ("disabled", "#A7DAD4"),
            ],
            foreground=[
                ("disabled", self.WHITE),
            ],
        )
        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10),
            padding=(12, 8),
            background=self.TEAL_LIGHT,
            foreground=self.TEAL_DARK,
            bordercolor=self.TEAL_LIGHT,
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("active", "#B5F3E7"),
            ],
        )
        style.configure(
            "App.TRadiobutton",
            background=self.BG,
            foreground=self.TEXT,
            font=("Segoe UI", 10),
        )
        style.map(
            "App.TRadiobutton",
            background=[
                ("active", self.BG),
            ],
            foreground=[
                ("disabled", self.MUTED),
            ],
        )
        style.configure(
            "TLabelframe",
            background=self.WHITE,
            bordercolor=self.BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=self.WHITE,
            foreground=self.TEXT,
            font=("Segoe UI", 10, "bold"),
        )

        # Shared styles for reusable GUI components.
        UI.configure_styles(self)

    # ---------------------------------------------------------
    # Main layout
    # ---------------------------------------------------------

    def _build_layout(self):
        self._build_sidebar()

        self.main_area = tk.Frame(self, bg=self.BG)
        self.main_area.pack(
            side="left",
            fill="both",
            expand=True,
        )

        self.content = ttk.Frame(
            self.main_area,
            style="App.TFrame",
        )
        self.content.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=26,
        )

        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        page_classes = {
            "Transfer": TransferPage,
            "Logs": LogsPage,
            "Recent Transfers": HistoryPage,
            "Settings": SettingsPage,
            "About": AboutPage,
        }

        for name, page_class in page_classes.items():
            page = page_class(self.content, self)
            self.pages[name] = page
            page.grid(
                row=0,
                column=0,
                sticky="nsew",
            )

    # ---------------------------------------------------------
    # Sidebar
    # ---------------------------------------------------------

    def _build_sidebar(self):
        self.sidebar = tk.Frame(
            self,
            bg=self.SIDEBAR,
            width=230,
        )
        self.sidebar.pack(
            side="left",
            fill="y",
        )
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=self.SIDEBAR)
        brand.pack(
            fill="x",
            padx=22,
            pady=(28, 34),
        )

        tk.Label(
            brand,
            text="RFT",
            bg=self.SIDEBAR,
            fg="#5EEAD4",
            font=("Segoe UI", 27, "bold"),
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="RELIABLE FILE TRANSFER",
            bg=self.SIDEBAR,
            fg="#D5E7E9",
            font=("Segoe UI", 8, "bold"),
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

        tk.Frame(
            self.sidebar,
            bg="#315A61",
            height=1,
        ).pack(
            fill="x",
            padx=18,
            pady=(0, 22),
        )

        tk.Label(
            self.sidebar,
            text="WORKSPACE",
            bg=self.SIDEBAR,
            fg="#94B7BD",
            font=("Segoe UI", 8, "bold"),
        ).pack(
            anchor="w",
            padx=24,
            pady=(0, 9),
        )

        navigation = [
            ("Transfer", "⇄", "Send and receive files"),
            ("Logs", "≡", "Protocol activity"),
            ("Recent Transfers", "◷", "Transfer history"),
            ("Settings", "⚙", "Application preferences"),
            ("About", "ⓘ", "Project information"),
        ]

        for page_name, icon, description in navigation:
            self._create_nav_button(
                page_name,
                icon,
                description,
            )

        footer = tk.Frame(self.sidebar, bg=self.SIDEBAR)
        footer.pack(
            side="bottom",
            fill="x",
            padx=20,
            pady=22,
        )

        tk.Frame(
            footer,
            bg="#315A61",
            height=1,
        ).pack(
            fill="x",
            pady=(0, 13),
        )

        tk.Label(
            footer,
            text="UDP  •  Stop-and-Wait ARQ",
            bg=self.SIDEBAR,
            fg="#C0D7DB",
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        tk.Label(
            footer,
            text="Reliable transfer with integrity checks",
            bg=self.SIDEBAR,
            fg="#8FAEB4",
            font=("Segoe UI", 8),
            wraplength=190,
            justify="left",
        ).pack(
            anchor="w",
            pady=(5, 0),
        )

    def _create_nav_button(self, name, icon, description):
        """Create one sidebar navigation button."""
        button = tk.Button(
            self.sidebar,
            text=f"  {icon}    {name}",
            anchor="w",
            padx=14,
            pady=12,
            relief="flat",
            bd=0,
            cursor="hand2",
            bg=self.SIDEBAR,
            fg="#E7F0F1",
            activebackground=self.SIDEBAR_HOVER,
            activeforeground=self.WHITE,
            font=("Segoe UI", 10),
            command=lambda page=name: self.show_page(page),
        )

        button.pack(
            fill="x",
            padx=12,
            pady=3,
        )

        button.description = description
        self.nav_buttons[name] = button

    # ---------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------

    def show_page(self, name):
        """Display a page and update sidebar styling."""
        if name not in self.pages:
            raise ValueError(f"Unknown page: {name}")

        self.current_page = name
        self.pages[name].tkraise()

        if name == "Recent Transfers":
            self._refresh_history_page()

        for page_name, button in self.nav_buttons.items():
            selected = page_name == name

            button.configure(
                bg=(
                    self.SIDEBAR_HOVER
                    if selected
                    else self.SIDEBAR
                ),
                fg=(
                    "#5EEAD4"
                    if selected
                    else "#E7F0F1"
                ),
                font=(
                    "Segoe UI",
                    10,
                    "bold" if selected else "normal",
                ),
            )

    # ---------------------------------------------------------
    # Shared application logging
    # ---------------------------------------------------------

    def record_log(self, message, level="INFO"):
        """Store a timestamped log entry."""
        entry = {
            "timestamp": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "level": str(level).upper(),
            "message": str(message),
        }

        self.log_entries.append(entry)

        if len(self.log_entries) > self.MAX_LOG_ENTRIES:
            del self.log_entries[
                : len(self.log_entries) - self.MAX_LOG_ENTRIES
            ]

        logs_page = self.pages.get("Logs")

        if logs_page is not None and hasattr(
            logs_page,
            "refresh_logs",
        ):
            logs_page.refresh_logs()

        return entry

    def clear_logs(self):
        """Clear current-session logs."""
        self.log_entries.clear()

        logs_page = self.pages.get("Logs")

        if logs_page is not None and hasattr(
            logs_page,
            "refresh_logs",
        ):
            logs_page.refresh_logs()

    # ---------------------------------------------------------
    # Transfer history
    # ---------------------------------------------------------

    def record_transfer(self, record):
        """Store a transfer result and refresh the history page."""
        if not isinstance(record, dict):
            raise TypeError("Transfer history record must be a dictionary.")

        # Copy the record so later modifications by a page do not
        # silently change the stored history.
        entry = dict(record)

        entry.setdefault(
            "timestamp",
            datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        entry.setdefault("filename", "Unknown file")
        entry.setdefault("direction", "Unknown")
        entry.setdefault("bytes_transferred", 0)
        entry.setdefault("duration_seconds", 0.0)
        entry.setdefault("status", "COMPLETED")
        entry.setdefault("integrity", "Unknown")

        try:
            entry["bytes_transferred"] = max(
                0,
                int(entry["bytes_transferred"] or 0),
            )
        except (TypeError, ValueError):
            entry["bytes_transferred"] = 0

        try:
            entry["duration_seconds"] = max(
                0.0,
                float(entry["duration_seconds"] or 0),
            )
        except (TypeError, ValueError):
            entry["duration_seconds"] = 0.0

        entry["filename"] = str(entry["filename"])
        entry["direction"] = str(entry["direction"])
        entry["status"] = str(entry["status"]).upper()
        entry["integrity"] = str(entry["integrity"])

        self.transfer_history.append(entry)

        # Bound memory use for long-running sessions.
        if len(self.transfer_history) > self.MAX_HISTORY_ENTRIES:
            del self.transfer_history[
                : len(self.transfer_history) - self.MAX_HISTORY_ENTRIES
            ]

        try:
            self._save_transfer_history()
        except OSError as exc:
            self.record_log(
                f"Could not save transfer history: {exc}",
                level="ERROR",
            )

        self._refresh_history_page()
        return entry

    def _refresh_history_page(self):
        """Refresh history if the page has already been created."""
        history_page = self.pages.get("Recent Transfers")

        if history_page is not None and hasattr(
            history_page,
            "refresh_history",
        ):
            history_page.refresh_history()

    # ---------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------

    def _on_close(self):
        """Stop an active receiver before closing the application."""
        transfer_page = self.pages.get("Transfer")

        if transfer_page is not None:
            stop_receiver = getattr(
                transfer_page,
                "_stop_receiver",
                None,
            )

            if callable(stop_receiver):
                try:
                    stop_receiver()
                except Exception:
                    # Cleanup errors must not block window closure.
                    pass

        self.destroy()


def main():
    app = ReliableUDPApp()
    app.mainloop()


if __name__ == "__main__":
    main()