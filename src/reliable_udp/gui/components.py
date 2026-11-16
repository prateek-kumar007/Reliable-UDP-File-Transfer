"""Reusable Tkinter components for the Reliable UDP dashboard."""

import tkinter as tk
from tkinter import ttk


class UI:
    """Shared colors, typography, and reusable widget builders."""

    # Backgrounds
    BG = "#F4F7F8"
    WHITE = "#FFFFFF"
    NEUTRAL_BG = "#E8EEF0"

    # Brand colors
    TEAL = "#0D9488"
    TEAL_DARK = "#0F766E"
    TEAL_LIGHT = "#CCFBF1"

    # Text colors
    TEXT = "#172B32"
    MUTED = "#647780"
    BORDER = "#DCE5E8"

    # Semantic colors
    SUCCESS = "#15803D"
    SUCCESS_BG = "#DCFCE7"
    WARNING = "#B45309"
    WARNING_BG = "#FEF3C7"
    ERROR = "#B91C1C"
    ERROR_BG = "#FEE2E2"

    # Typography
    FONT = "Segoe UI"
    FONT_SMALL = 9
    FONT_NORMAL = 10
    FONT_SECTION = 12
    FONT_HEADING = 23

    # Consistent spacing units
    SPACE_XS = 4
    SPACE_SM = 8
    SPACE_MD = 12
    SPACE_LG = 16
    SPACE_XL = 24

    @staticmethod
    def configure_styles(root):
        """Configure reusable ttk styles once for the application."""
        style = ttk.Style(root)

        style.configure(
            "App.TFrame",
            background=UI.BG,
        )

        style.configure(
            "App.TLabel",
            background=UI.BG,
            foreground=UI.TEXT,
            font=(UI.FONT, UI.FONT_NORMAL),
        )

        style.configure(
            "Muted.TLabel",
            background=UI.BG,
            foreground=UI.MUTED,
            font=(UI.FONT, UI.FONT_NORMAL),
        )

        style.configure(
            "App.TEntry",
            padding=(8, 6),
            font=(UI.FONT, UI.FONT_NORMAL),
            fieldbackground=UI.WHITE,
            foreground=UI.TEXT,
        )

        style.configure(
            "Accent.TButton",
            padding=(12, 7),
            font=(UI.FONT, UI.FONT_NORMAL, "bold"),
            background=UI.TEAL,
            foreground=UI.WHITE,
        )

        style.map(
            "Accent.TButton",
            background=[
                ("disabled", UI.BORDER),
                ("pressed", UI.TEAL_DARK),
                ("active", UI.TEAL_DARK),
            ],
            foreground=[
                ("disabled", UI.MUTED),
                ("!disabled", UI.WHITE),
            ],
        )

        style.configure(
            "App.TButton",
            padding=(10, 6),
            font=(UI.FONT, UI.FONT_NORMAL),
        )

        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=UI.NEUTRAL_BG,
            background=UI.TEAL,
            thickness=10,
            borderwidth=0,
        )

        return style

    @staticmethod
    def card(parent, padding=18):
        """Create a white card container."""
        return tk.Frame(
            parent,
            bg=UI.WHITE,
            highlightbackground=UI.BORDER,
            highlightthickness=1,
            bd=0,
            padx=padding,
            pady=padding,
        )

    @staticmethod
    def page_header(parent, title, subtitle=None):
        """Create a page heading and optional subtitle."""
        header = tk.Frame(parent, bg=UI.BG)

        tk.Label(
            header,
            text=title,
            bg=UI.BG,
            fg=UI.TEXT,
            font=(UI.FONT, UI.FONT_HEADING, "bold"),
            anchor="w",
        ).pack(anchor="w")

        if subtitle:
            tk.Label(
                header,
                text=subtitle,
                bg=UI.BG,
                fg=UI.MUTED,
                font=(UI.FONT, UI.FONT_NORMAL),
                anchor="w",
                justify="left",
                wraplength=850,
            ).pack(anchor="w", pady=(5, 0))

        return header

    @staticmethod
    def section_title(parent, title, subtitle=None):
        """Create a section heading inside a card."""
        section = tk.Frame(parent, bg=UI.WHITE)

        tk.Label(
            section,
            text=title,
            bg=UI.WHITE,
            fg=UI.TEXT,
            font=(UI.FONT, UI.FONT_SECTION, "bold"),
            anchor="w",
        ).pack(anchor="w")

        if subtitle:
            tk.Label(
                section,
                text=subtitle,
                bg=UI.WHITE,
                fg=UI.MUTED,
                font=(UI.FONT, UI.FONT_SMALL),
                anchor="w",
                justify="left",
                wraplength=700,
            ).pack(anchor="w", pady=(4, 0))

        return section

    @staticmethod
    def metric_card(parent, title, value="—", detail=None):
        """Create a metric card with updateable value and detail."""
        card = UI.card(parent, padding=UI.SPACE_MD)

        tk.Label(
            card,
            text=title.upper(),
            bg=UI.WHITE,
            fg=UI.MUTED,
            font=(UI.FONT, UI.FONT_SMALL, "bold"),
            anchor="w",
        ).pack(fill="x")

        value_label = tk.Label(
            card,
            text=str(value),
            bg=UI.WHITE,
            fg=UI.TEXT,
            font=(UI.FONT, 19, "bold"),
            anchor="w",
        )
        value_label.pack(fill="x", pady=(6, 3))

        detail_label = tk.Label(
            card,
            text=detail or "",
            bg=UI.WHITE,
            fg=UI.MUTED,
            font=(UI.FONT, UI.FONT_NORMAL),
            anchor="w",
        )
        detail_label.pack(fill="x")

        return {
            "frame": card,
            "value": value_label,
            "detail": detail_label,
        }

    @staticmethod
    def status_badge(parent, text="Idle", status="neutral"):
        """Create a status label with semantic colors."""
        palette = {
            "success": (UI.SUCCESS, UI.SUCCESS_BG),
            "warning": (UI.WARNING, UI.WARNING_BG),
            "error": (UI.ERROR, UI.ERROR_BG),
            "active": (UI.TEAL_DARK, UI.TEAL_LIGHT),
            "neutral": (UI.MUTED, UI.NEUTRAL_BG),
        }

        foreground, background = palette.get(
            status.lower(),
            palette["neutral"],
        )

        return tk.Label(
            parent,
            text=f"  {text}  ",
            bg=background,
            fg=foreground,
            font=(UI.FONT, UI.FONT_SMALL, "bold"),
            padx=5,
            pady=4,
        )

    @staticmethod
    def labeled_entry(parent, label, variable, width=24):
        """Create a label and a consistently styled entry field."""
        field = tk.Frame(parent, bg=UI.WHITE)

        tk.Label(
            field,
            text=label,
            bg=UI.WHITE,
            fg=UI.TEXT,
            font=(UI.FONT, UI.FONT_NORMAL, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))

        entry = ttk.Entry(
            field,
            textvariable=variable,
            width=width,
            style="App.TEntry",
        )
        entry.pack(fill="x")

        return field, entry

    @staticmethod
    def progress_bar(parent, variable, maximum=100):
        """Create a consistently styled progress bar."""
        return ttk.Progressbar(
            parent,
            variable=variable,
            maximum=maximum,
            mode="determinate",
            style="Horizontal.TProgressbar",
        )