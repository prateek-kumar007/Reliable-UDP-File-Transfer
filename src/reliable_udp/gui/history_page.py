
"""Recent transfer history page for Reliable UDP File Transfer."""

import csv
from tkinter import StringVar, filedialog, messagebox, ttk

from .components import UI


class HistoryPage(ttk.Frame):
    """Display, search, filter, and export transfer history."""

    COLUMNS = (
        "timestamp",
        "filename",
        "direction",
        "size",
        "duration",
        "status",
        "integrity",
    )

    def __init__(self, parent, app):
        super().__init__(parent, style="App.TFrame")
        self.app = app

        self.search_var = StringVar()
        self.status_var = StringVar(value="ALL")
        self.count_var = StringVar(value="0 transfers")

        self.metrics = {}
        self.tree = None

        self._build_ui()
        self.search_var.trace_add("write", self._on_filter_changed)
        self.status_var.trace_add("write", self._on_filter_changed)
        self.refresh_history()

    def _build_ui(self):
        UI.page_header(
            self,
            "Recent Transfers",
            "Review completed and failed file transfers.",
        ).pack(fill="x", pady=(0, 16))

        metrics_frame = ttk.Frame(self, style="App.TFrame")
        metrics_frame.pack(fill="x", pady=(0, 14))

        metric_specs = (
            ("total", "TOTAL TRANSFERS", "0"),
            ("success", "COMPLETED", "0"),
            ("failed", "FAILED", "0"),
            ("bytes", "DATA TRANSFERRED", "0 B"),
        )

        for column, (key, title, value) in enumerate(metric_specs):
            metrics_frame.columnconfigure(column, weight=1)

            metric = UI.metric_card(metrics_frame, title, value)
            metric["frame"].grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 6, 0 if column == 3 else 6),
            )
            self.metrics[key] = metric

        toolbar = UI.card(self, padding=14)
        toolbar.pack(fill="x", pady=(0, 12))
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(
            toolbar,
            text="Search",
            style="App.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        ttk.Entry(
            toolbar,
            textvariable=self.search_var,
            style="App.TEntry",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 12))

        ttk.Label(
            toolbar,
            text="Status",
            style="App.TLabel",
        ).grid(row=0, column=2, sticky="w", padx=(0, 8))

        ttk.Combobox(
            toolbar,
            textvariable=self.status_var,
            values=("ALL", "COMPLETED", "FAILED", "IN PROGRESS"),
            state="readonly",
            width=14,
        ).grid(row=0, column=3, sticky="w", padx=(0, 12))

        ttk.Button(
            toolbar,
            text="Refresh",
            command=self.refresh_history,
        ).grid(row=0, column=4, padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Export CSV",
            style="Accent.TButton",
            command=self.export_csv,
        ).grid(row=0, column=5)

        table_card = UI.card(self, padding=12)
        table_card.pack(fill="both", expand=True)

        header = ttk.Frame(table_card, style="App.TFrame")
        header.pack(fill="x", pady=(0, 10))

        UI.section_title(
            header,
            "Transfer history",
            "Select a row to inspect its transfer details.",
        ).pack(side="left", anchor="w")

        ttk.Label(
            header,
            textvariable=self.count_var,
            style="Muted.TLabel",
        ).pack(side="right")

        table_frame = ttk.Frame(table_card, style="App.TFrame")
        table_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_frame,
            columns=self.COLUMNS,
            show="headings",
            selectmode="browse",
        )

        headings = {
            "timestamp": "DATE / TIME",
            "filename": "FILE NAME",
            "direction": "DIRECTION",
            "size": "SIZE",
            "duration": "DURATION",
            "status": "STATUS",
            "integrity": "INTEGRITY",
        }

        widths = {
            "timestamp": 155,
            "filename": 230,
            "direction": 105,
            "size": 100,
            "duration": 95,
            "status": 115,
            "integrity": 110,
        }

        for column in self.COLUMNS:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=75,
                stretch=column == "filename",
                anchor="w",
            )

        y_scroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview,
        )
        x_scroll = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("COMPLETED", foreground=UI.SUCCESS)
        self.tree.tag_configure("FAILED", foreground=UI.ERROR)
        self.tree.tag_configure("IN PROGRESS", foreground=UI.WARNING)

        self.tree.bind("<<TreeviewSelect>>", self._show_selected_details)

        details = UI.card(self, padding=12)
        details.pack(fill="x", pady=(12, 0))

        UI.section_title(
            details,
            "Selected transfer",
            "Choose a row above to view its details.",
        ).pack(anchor="w")

        self.details_var = StringVar(value="No transfer selected.")
        ttk.Label(
            details,
            textvariable=self.details_var,
            style="Muted.TLabel",
            wraplength=1000,
        ).pack(anchor="w", pady=(8, 0))

    @staticmethod
    def _format_bytes(value):
        try:
            amount = max(0, float(value))
        except (TypeError, ValueError):
            return str(value or "—")

        for unit in ("B", "KB", "MB", "GB", "TB"):
            if amount < 1024 or unit == "TB":
                return (
                    f"{int(amount)} {unit}"
                    if unit == "B"
                    else f"{amount:.1f} {unit}"
                )
            amount /= 1024

        return f"{amount:.1f} TB"

    @staticmethod
    def _normalize_entry(entry):
        """Normalize supported history dictionaries for display."""
        if not isinstance(entry, dict):
            entry = {"filename": str(entry)}

        timestamp = entry.get("timestamp", entry.get("date", "—"))
        filename = entry.get("filename", entry.get("file_name", "Unknown file"))
        direction = entry.get("direction", entry.get("mode", "—"))
        size = entry.get(
            "bytes_transferred",
            entry.get("size_bytes", entry.get("bytes_sent", 0)),
        )
        duration = entry.get("duration_seconds", entry.get("duration", "—"))
        status = str(entry.get("status", "COMPLETED")).upper().replace("_", " ")
        integrity = entry.get("integrity", entry.get("verification", "—"))

        if status in {"SUCCESS", "SUCCEEDED", "COMPLETE"}:
            status = "COMPLETED"
        elif status in {"ERROR", "FAILURE", "FAILED"}:
            status = "FAILED"
        elif status in {"ACTIVE", "RUNNING", "IN PROGRESS"}:
            status = "IN PROGRESS"
        else:
            status = (
                status
                if status in {"COMPLETED", "FAILED", "IN PROGRESS"}
                else "COMPLETED"
            )

        if isinstance(size, str):
            size_display = size
            try:
                size_numeric = float(size.split()[0])
            except (ValueError, IndexError):
                size_numeric = 0
        else:
            size_numeric = max(0, float(size or 0))
            size_display = HistoryPage._format_bytes(size_numeric)

        try:
            duration_display = (
                f"{float(duration):.1f} s"
                if duration not in ("—", None, "")
                else "—"
            )
        except (TypeError, ValueError):
            duration_display = str(duration)

        return {
            **entry,
            "timestamp": str(timestamp),
            "filename": str(filename),
            "direction": str(direction).title(),
            "size": size_display,
            "size_numeric": size_numeric,
            "duration": duration_display,
            "status": status,
            "integrity": str(integrity),
        }

    def _get_entries(self):
        history = getattr(self.app, "transfer_history", None)
        if history is None:
            history = getattr(self.app, "history_entries", [])
        if not isinstance(history, (list, tuple)):
            return []
        return [self._normalize_entry(item) for item in history]

    def _filtered_entries(self):
        query = self.search_var.get().strip().casefold()
        status_filter = self.status_var.get().upper()

        entries = self._get_entries()
        result = []

        for entry in entries:
            if status_filter != "ALL" and entry["status"] != status_filter:
                continue

            searchable = " ".join(
                str(entry.get(key, ""))
                for key in (
                    "timestamp",
                    "filename",
                    "direction",
                    "status",
                    "integrity",
                )
            ).casefold()

            if query and query not in searchable:
                continue

            result.append(entry)

        return result

    def refresh_history(self):
        if self.tree is None:
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        entries = self._filtered_entries()

        for entry in reversed(entries):
            self.tree.insert(
                "",
                "end",
                values=tuple(entry[column] for column in self.COLUMNS),
                tags=(entry["status"],),
            )

        all_entries = self._get_entries()
        completed = sum(e["status"] == "COMPLETED" for e in all_entries)
        failed = sum(e["status"] == "FAILED" for e in all_entries)
        total_bytes = sum(e["size_numeric"] for e in all_entries)

        self.metrics["total"]["value"].configure(text=str(len(all_entries)))
        self.metrics["success"]["value"].configure(text=str(completed))
        self.metrics["failed"]["value"].configure(text=str(failed))
        self.metrics["bytes"]["value"].configure(
            text=self._format_bytes(total_bytes)
        )

        self.count_var.set(
            f"{len(entries)} shown · {len(all_entries)} total"
        )

        self.details_var.set("No transfer selected.")

    def _on_filter_changed(self, *_):
        self.refresh_history()

    def _show_selected_details(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return

        values = self.tree.item(selected[0], "values")
        if not values:
            return

        timestamp, filename, direction, size, duration, status, integrity = values

        self.details_var.set(
            f"File: {filename}  |  Direction: {direction}  |  "
            f"Size: {size}  |  Duration: {duration}  |  "
            f"Status: {status}  |  Integrity: {integrity}  |  "
            f"Date: {timestamp}"
        )

    def export_csv(self):
        entries = self._filtered_entries()

        if not entries:
            messagebox.showinfo(
                "No transfers",
                "There are no transfer records matching the current filters.",
                parent=self,
            )
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export transfer history",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="reliable_udp_transfer_history.csv",
        )

        if not path:
            return

        fieldnames = (
            "timestamp",
            "filename",
            "direction",
            "size",
            "duration",
            "status",
            "integrity",
        )

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for entry in entries:
                    writer.writerow({
                        field: entry.get(field, "")
                        for field in fieldnames
                    })
        except OSError as exc:
            messagebox.showerror(
                "Export failed",
                f"Could not export transfer history:\n{exc}",
                parent=self,
            )
            return

        messagebox.showinfo(
            "Export complete",
            f"Exported {len(entries)} transfer records.",
            parent=self,
        )