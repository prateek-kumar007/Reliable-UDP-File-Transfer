
from tkinter import ttk


class AboutPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="App.TFrame")
        ttk.Label(self, text="About", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            self,
            text=(
                "Reliable UDP File Transfer\n"
                "UDP Stop-and-Wait ARQ with acknowledgements,\n"
                "retransmissions, and receiver-side integrity verification."
            ),
            style="Muted.TLabel",
            justify="left",
        ).pack(anchor="w", pady=8)