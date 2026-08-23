# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — vue_dashboard.py
Modern uncluttered dashboard: Total Sent, Total Received, Pending Bridge
Transfers, and Recent Activity.
"""

import customtkinter as ctk

from app.utils.theme import get_palette, FONTS
from app.utils.database import get_connection
from app.utils.archive_manager import get_archive_stats


class VueDashboard(ctk.CTkFrame):
    def __init__(self, master, appearance_mode: str = "Dark"):
        pal = get_palette(appearance_mode)
        super().__init__(master, fg_color=pal["bg"])
        self.pal = pal

        ctk.CTkLabel(self, text="Tableau de Bord", font=FONTS["title"],
                      text_color=pal["text"]).place(x=32, y=24)

        self._build_stat_cards()
        self._build_recent_activity()

    def _build_stat_cards(self):
        pal = self.pal
        stats = get_archive_stats()
        conn = get_connection()
        pending = conn.execute(
            "SELECT COUNT(*) as c FROM messages WHERE status = 'en_attente'"
        ).fetchone()["c"]

        cards = [
            ("📤", "Total Envoyés", stats["total_sortant"], pal["primary"]),
            ("📥", "Total Reçus", stats["total_entrant"], pal["success"]),
            ("⏳", "Transferts en Attente", pending, pal["warning"]),
        ]

        for i, (icon, label, value, color) in enumerate(cards):
            card = ctk.CTkFrame(self, fg_color=pal["card"], corner_radius=14,
                                 border_width=1, border_color=pal["card_border"],
                                 width=260, height=120)
            card.place(x=32 + i * 280, y=90)
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=icon, font=(FONTS["title"][0], 28)
                          ).pack(anchor="w", padx=20, pady=(16, 0))
            ctk.CTkLabel(card, text=str(value), font=(FONTS["title"][0], 26, "bold"),
                          text_color=color).pack(anchor="w", padx=20)
            ctk.CTkLabel(card, text=label, font=FONTS["small"],
                          text_color=pal["text_muted"]).pack(anchor="w", padx=20)

    def _build_recent_activity(self):
        pal = self.pal
        ctk.CTkLabel(self, text="Activité Récente", font=FONTS["subtitle"],
                      text_color=pal["text"]).place(x=32, y=240)

        panel = ctk.CTkScrollableFrame(self, fg_color=pal["card"], corner_radius=14,
                                        border_width=1, border_color=pal["card_border"],
                                        width=828, height=280)
        panel.place(x=32, y=280)

        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT 25"
        ).fetchall()

        if not rows:
            ctk.CTkLabel(panel, text="Aucune activité pour le moment.",
                          font=FONTS["body"], text_color=pal["text_muted"]
                          ).pack(padx=16, pady=20)
            return

        for row in rows:
            direction_icon = "📤" if row["direction"] == "sortant" else "📥"
            line = ctk.CTkFrame(panel, fg_color="transparent")
            line.pack(fill="x", padx=12, pady=6)
            ctk.CTkLabel(line, text=f"{direction_icon} {row['tracking_number']}",
                          font=FONTS["body"], text_color=pal["text"], width=200,
                          anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=row["subject"] or "(sans objet)",
                          font=FONTS["body"], text_color=pal["text_muted"],
                          anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(line, text=row["status"], font=FONTS["small"],
                          text_color=pal["primary"], anchor="e"
                          ).pack(side="right")
