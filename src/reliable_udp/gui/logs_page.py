
from tkinter import ttk


class LogsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="App.TFrame")
        ttk.Label(self, text="Transfer Logs", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(self, text="Transfer events will appear here.",
                  style="Muted.TLabel").pack(anchor="w", pady=8)
