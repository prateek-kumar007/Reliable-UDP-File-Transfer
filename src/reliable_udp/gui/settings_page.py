
from tkinter import ttk


class SettingsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="App.TFrame")
        ttk.Label(self, text="Settings", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(self, text="Default transfer settings will go here.",
                  style="Muted.TLabel").pack(anchor="w", pady=8)
