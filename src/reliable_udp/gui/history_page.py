
from tkinter import ttk


class HistoryPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="App.TFrame")
        ttk.Label(self, text="Recent Transfers", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(self, text="Completed transfers will appear here.",
                  style="Muted.TLabel").pack(anchor="w", pady=8)
