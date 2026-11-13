import tkinter as tk
from tkinter import ttk

from reliable_udp.gui.about_page import AboutPage
from reliable_udp.gui.history_page import HistoryPage
from reliable_udp.gui.logs_page import LogsPage
from reliable_udp.gui.settings_page import SettingsPage
from reliable_udp.gui.transfer_page import TransferPage


class ReliableUDPApp(tk.Tk):
    """Main application window and page navigation."""

    BG = "#F4F7F8"
    SIDEBAR = "#103C46"
    SIDEBAR_HOVER = "#1A5662"
    TEAL = "#0D9488"
    TEXT = "#172B32"
    MUTED = "#647780"
    WHITE = "#FFFFFF"

    def __init__(self):
        super().__init__()

        self.title("Reliable UDP File Transfer")
        self.geometry("1200x760")
        self.minsize(1000, 650)
        self.configure(bg=self.BG)

        self.pages = {}
        self.nav_buttons = {}

        self._configure_styles()
        self._build_layout()
        self.show_page("Transfer")

    def _configure_styles(self):
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
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=self.BG,
            foreground=self.MUTED,
            font=("Segoe UI", 10),
        )

    def _build_layout(self):
        self.sidebar = tk.Frame(
            self,
            bg=self.SIDEBAR,
            width=220,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=self.SIDEBAR)
        brand.pack(fill="x", padx=20, pady=(28, 34))

        tk.Label(
            brand,
            text="RFT",
            bg=self.SIDEBAR,
            fg="#5EEAD4",
            font=("Segoe UI", 25, "bold"),
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="Reliable File Transfer",
            bg=self.SIDEBAR,
            fg=self.WHITE,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(3, 0))

        navigation = [
            ("Transfer", "Transfer"),
            ("Logs", "Logs"),
            ("Recent Transfers", "Recent Transfers"),
            ("Settings", "Settings"),
            ("About", "About"),
        ]

        for page_name, label in navigation:
            button = tk.Button(
                self.sidebar,
                text=f"   {label}",
                anchor="w",
                padx=12,
                pady=12,
                relief="flat",
                bd=0,
                cursor="hand2",
                bg=self.SIDEBAR,
                fg=self.WHITE,
                activebackground=self.SIDEBAR_HOVER,
                activeforeground=self.WHITE,
                font=("Segoe UI", 10),
                command=lambda name=page_name: self.show_page(name),
            )
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[page_name] = button

        footer = tk.Label(
            self.sidebar,
            text="UDP • Stop-and-Wait ARQ",
            bg=self.SIDEBAR,
            fg="#A9C5CB",
            font=("Segoe UI", 9),
        )
        footer.pack(side="bottom", pady=22)

        self.content = ttk.Frame(self, style="App.TFrame")
        self.content.pack(
            side="left",
            fill="both",
            expand=True,
            padx=30,
            pady=25,
        )

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
            page.grid(row=0, column=0, sticky="nsew")

        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

    def show_page(self, name):
        page = self.pages[name]
        page.tkraise()

        for page_name, button in self.nav_buttons.items():
            selected = page_name == name
            button.configure(
                bg=self.SIDEBAR_HOVER if selected else self.SIDEBAR,
                fg="#5EEAD4" if selected else self.WHITE,
            )


def main():
    app = ReliableUDPApp()
    app.mainloop()


if __name__ == "__main__":
    main()
