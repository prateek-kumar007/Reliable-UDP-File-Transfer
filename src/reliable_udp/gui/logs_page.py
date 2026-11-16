
"""Searchable, filterable, and exportable application logs."""

import csv
from datetime import datetime
from tkinter import StringVar, filedialog, messagebox, ttk

from .components import UI


class LogsPage(ttk.Frame):
    """Display shared application log entries."""

    def __init__(self, parent, app):
        super().__init__(parent, style="App.TFrame")
        self.app = app

        self.search_var = StringVar()
        self.level_var = StringVar(value="ALL")
        self.count_var = StringVar(value="0 events")

        self._build_ui()
        self.search_var.trace_add("write", self._on_filter_changed)
        self.level_var.trace_add("write", self._on_filter_changed)

        self.refresh_logs()

    def _build_ui(self):
        UI.page_header(
            self,
            "Transfer Logs",
            "Inspect transfer activity, troubleshoot failures, and export "
            "diagnostic records.",
        ).pack(fill="x", pady=(0, 16))

        toolbar = UI.card(self, padding=14)
        toolbar.pack(fill="x", pady=(0, 12))

        toolbar.columnconfigure(1, weight=1)

        ttk.Label(
            toolbar,
            text="Search",
            style="App.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        search_entry = ttk.Entry(
            toolbar,
            textvariable=self.search_var,
            style="App.TEntry",
        )
        search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))

        ttk.Label(
            toolbar,
            text="Level",
            style="App.TLabel",
        ).grid(row=0, column=2, sticky="w", padx=(0, 8))

        level_picker = ttk.Combobox(
            toolbar,
            textvariable=self.level_var,
            values=("ALL", "INFO", "SUCCESS", "WARNING", "ERROR"),
            state="readonly",
            width=12,
        )
        level_picker.grid(row=0, column=3, sticky="w", padx=(0, 12))

        ttk.Button(
            toolbar,
            text="Refresh",
            command=self.refresh_logs,
        ).grid(row=0, column=4, padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Export CSV",
            command=self.export_csv,
            style="Accent.TButton",
        ).grid(row=0, column=5)

        table_card = UI.card(self, padding=12)
        table_card.pack(fill="both", expand=True)

        table_header = ttk.Frame(table_card, style="App.TFrame")
        table_header.pack(fill="x", pady=(0, 10))

        UI.section_title(
            table_header,
            "Event history",
            "Newest events appear first.",
        ).pack(side="left", anchor="w")

        ttk.Label(
            table_header,
            textvariable=self.count_var,
            style="Muted.TLabel",
        ).pack(side="right")

        table_frame = ttk.Frame(table_card, style="App.TFrame")
        table_frame.pack(fill="both", expand=True)

        columns = ("timestamp", "level", "message")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )

        self.tree.heading("timestamp", text="TIMESTAMP")
        self.tree.heading("level", text="LEVEL")
        self.tree.heading("message", text="EVENT")

        self.tree.column("timestamp", width=175, minwidth=150, stretch=False)
        self.tree.column("level", width=100, minwidth=85, stretch=False)
        self.tree.column("message", width=500, minwidth=200, stretch=True)

        scrollbar_y = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview,
        )
        scrollbar_x = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("ERROR", foreground=UI.ERROR)
        self.tree.tag_configure("WARNING", foreground=UI.WARNING)
        self.tree.tag_configure("SUCCESS", foreground=UI.SUCCESS)

        footer = ttk.Frame(self, style="App.TFrame")
        footer.pack(fill="x", pady=(10, 0))

        ttk.Button(
            footer,
            text="Clear all logs",
            command=self.clear_logs,
        ).pack(side="left")

        ttk.Label(
            footer,
            text="Export before clearing if you need to retain diagnostics.",
            style="Muted.TLabel",
        ).pack(side="right")

    @staticmethod
    def _normalize_entry(entry):
        """Accept dictionaries or plain strings from shared app logs."""
        if isinstance(entry, dict):
            timestamp = entry.get("timestamp", "")
            level = str(entry.get("level", "INFO")).upper()
            message = str(entry.get("message", entry.get("text", "")))
        else:
            timestamp = ""
            level = "INFO"
            message = str(entry)

        if isinstance(timestamp, datetime):
            timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        elif not timestamp:
            timestamp = "—"
        else:
            timestamp = str(timestamp)

        if level not in {"INFO", "SUCCESS", "WARNING", "ERROR"}:
            level = "INFO"

        return {
            "timestamp": timestamp,
            "level": level,
            "message": message,
        }

    def _get_entries(self):
        entries = getattr(self.app, "log_entries", [])
        return [self._normalize_entry(entry) for entry in entries]

    def _filtered_entries(self):
        query = self.search_var.get().strip().casefold()
        selected_level = self.level_var.get().upper()

        result = []
        for entry in self._get_entries():
            if selected_level != "ALL" and entry["level"] != selected_level:
                continue

            searchable = (
                f'{entry["timestamp"]} {entry["level"]} {entry["message"]}'
            ).casefold()

            if query and query not in searchable:
                continue

            result.append(entry)

        return result

    def refresh_logs(self):
        """Reload the table from the app's shared log collection."""
        if not hasattr(self, "tree"):
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        entries = self._filtered_entries()

        # Newest events first.
        for entry in reversed(entries):
            self.tree.insert(
                "",
                "end",
                values=(
                    entry["timestamp"],
                    entry["level"],
                    entry["message"],
                ),
                tags=(entry["level"],),
            )

        total = len(self._get_entries())
        self.count_var.set(f'{len(entries)} shown · {total} total')

    def _on_filter_changed(self, *_):
        self.refresh_logs()

    def export_csv(self):
        entries = self._filtered_entries()
        if not entries:
            messagebox.showinfo(
                "No logs to export",
                "There are no log entries matching the current filters.",
                parent=self,
            )
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export transfer logs",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="reliable_udp_logs.csv",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=("timestamp", "level", "message"),
                )
                writer.writeheader()
                writer.writerows(entries)
        except OSError as exc:
            messagebox.showerror(
                "Export failed",
                f"Could not save the log file:\n{exc}",
                parent=self,
            )
            return

        messagebox.showinfo(
            "Export complete",
            f"Exported {len(entries)} log entries.",
            parent=self,
        )

    def clear_logs(self):
        if not self._get_entries():
            return

        confirm = messagebox.askyesno(
            "Clear logs",
            "Delete all application log entries? This cannot be undone.",
            parent=self,
        )
        if not confirm:
            return

        clear_method = getattr(self.app, "clear_logs", None)
        if callable(clear_method):
            clear_method()
        else:
            entries = getattr(self.app, "log_entries", None)
            if isinstance(entries, list):
                entries.clear()

        self.refresh_logs()