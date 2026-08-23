# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — vue_administration.py
Registre Officiel: Digital official mail registry (Entrant/Sortant) with
automatically generated tracking numbers, logging every transaction.
"""

import customtkinter as ctk

from app.utils.theme import get_palette, FONTS
from app.utils.database import get_connection


class VueAdministration(ctk.CTkFrame):
    def __init__(self, master, appearance_mode: str = "Dark"):
        pal = get_palette(appearance_mode)
        super().__init__(master, fg_color=pal["bg"])
        self.pal = pal

        ctk.CTkLabel(self, text="Administration & Archivage", font=FONTS["title"],
                      text_color=pal["text"]).place(x=32, y=24)
        ctk.CTkLabel(self, text="Registre Officiel des Courriers", font=FONTS["body"],
                      text_color=pal["text_muted"]).place(x=32, y=64)

        self.filter_var = ctk.StringVar(value="Tous")
        segmented = ctk.CTkSegmentedButton(self, values=["Tous", "Entrant", "Sortant"],
                                            variable=self.filter_var,
                                            selected_color=pal["primary"],
                                            command=lambda _: self._refresh_table())
        segmented.place(x=32, y=100)

        ctk.CTkButton(self, text="🔄  Actualiser", width=140, height=32,
                       fg_color=pal["primary"], command=self._refresh_table
                       ).place(x=650, y=100)

        self.table_container = ctk.CTkScrollableFrame(self, fg_color=pal["card"],
                                                        corner_radius=12,
                                                        border_width=1,
                                                        border_color=pal["card_border"],
                                                        width=870, height=470)
        self.table_container.place(x=32, y=150)

        self._render_header_row()
        self._refresh_table()

    def _render_header_row(self):
        pal = self.pal
        row = ctk.CTkFrame(self.table_container, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        for text, w in [("N° Suivi", 220), ("Type", 90), ("Partenaire", 260),
                         ("Objet", 220), ("Date", 140)]:
            ctk.CTkLabel(row, text=text, font=FONTS["small"], text_color=pal["text_muted"],
                          width=w, anchor="w").pack(side="left")

    def _refresh_table(self):
        pal = self.pal
        for child in list(self.table_container.winfo_children())[1:]:
            child.destroy()

        conn = get_connection()
        filt = self.filter_var.get()
        if filt == "Tous":
            rows = conn.execute(
                "SELECT * FROM registre_courrier ORDER BY date_enregistrement DESC"
            ).fetchall()
        else:
            type_val = "entrant" if filt == "Entrant" else "sortant"
            rows = conn.execute(
                "SELECT * FROM registre_courrier WHERE type_courrier = ? "
                "ORDER BY date_enregistrement DESC", (type_val,)
            ).fetchall()

        if not rows:
            ctk.CTkLabel(self.table_container, text="Aucun enregistrement.",
                          font=FONTS["body"], text_color=pal["text_muted"]
                          ).pack(pady=20)
            return

        for row in rows:
            icon = "📥" if row["type_courrier"] == "entrant" else "📤"
            line = ctk.CTkFrame(self.table_container, fg_color="transparent")
            line.pack(fill="x", pady=3)
            ctk.CTkLabel(line, text=f"{icon} {row['tracking_number']}",
                          font=FONTS["small"], text_color=pal["text"], width=220,
                          anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=row["type_courrier"].capitalize(),
                          font=FONTS["small"], text_color=pal["text_muted"], width=90,
                          anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=row["institution_partenaire"] or "—",
                          font=FONTS["small"], text_color=pal["text_muted"], width=260,
                          anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=row["objet"] or "—", font=FONTS["small"],
                          text_color=pal["text_muted"], width=220,
                          anchor="w").pack(side="left")
            date_display = row["date_enregistrement"][:16].replace("T", " ")
            ctk.CTkLabel(line, text=date_display, font=FONTS["small"],
                          text_color=pal["text_muted"], width=140,
                          anchor="w").pack(side="left")
