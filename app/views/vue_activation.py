# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — vue_activation.py
First-time onboarding wizard: Wilaya -> Institution -> Serial Key -> Confirm.
Shown only when database.is_first_launch() is True.
"""

import customtkinter as ctk
from tkinter import messagebox

from app.config import WILAYAS, INSTITUTION_TYPES, APP_FLAG, APP_FULL_NAME
from app.utils.theme import get_palette, FONTS
from app.utils.serial_key import generate_serial_key
from app.utils.database import save_profile


class VueActivation(ctk.CTkFrame):
    """
    Full-window onboarding wizard. Root frame rule: place(x=0, y=0,
    relwidth=1, relheight=1) — never pack(fill='both').
    """

    def __init__(self, master, on_complete, appearance_mode: str = "Dark"):
        pal = get_palette(appearance_mode)
        super().__init__(master, fg_color=pal["bg"])
        self.place(x=0, y=0, relwidth=1, relheight=1)

        self.pal = pal
        self.on_complete = on_complete
        self.step = 0
        self.selected_wilaya = None       # (code, name)
        self.selected_institution_type = None
        self.institution_name_value = ""
        self.generated_serial = None

        self._build_shell()
        self._render_step()

    # ------------------------------------------------------------------ #
    # Shell / layout
    # ------------------------------------------------------------------ #
    def _build_shell(self):
        pal = self.pal
        header = ctk.CTkFrame(self, fg_color="transparent", height=110)
        header.place(x=0, y=0, relwidth=1, height=110)

        ctk.CTkLabel(header, text=f"{APP_FLAG} {APP_FULL_NAME}",
                      font=FONTS["title"], text_color=pal["primary"]
                      ).place(relx=0.5, y=40, anchor="center")
        ctk.CTkLabel(header, text="Configuration initiale de l'établissement",
                      font=FONTS["body"], text_color=pal["text_muted"]
                      ).place(relx=0.5, y=72, anchor="center")

        self.card = ctk.CTkFrame(self, fg_color=pal["card"], corner_radius=16,
                                  border_width=1, border_color=pal["card_border"],
                                  width=460, height=420)
        self.card.place(relx=0.5, rely=0.55, anchor="center")
        self.card.pack_propagate(False)

    def _clear_card(self):
        for child in self.card.winfo_children():
            child.destroy()

    def _render_step(self):
        self._clear_card()
        if self.step == 0:
            self._render_wilaya_step()
        elif self.step == 1:
            self._render_institution_step()
        elif self.step == 2:
            self._render_serial_step()

    # ------------------------------------------------------------------ #
    # Step 0 — Wilaya selection
    # ------------------------------------------------------------------ #
    def _render_wilaya_step(self):
        pal = self.pal
        ctk.CTkLabel(self.card, text="1️⃣  Sélectionnez votre Wilaya",
                      font=FONTS["subtitle"], text_color=pal["text"]
                      ).pack(padx=24, pady=(24, 12), anchor="w")

        names = [f"{code:02d} — {name}" for code, name in WILAYAS]
        self.wilaya_var = ctk.StringVar(value=names[30])  # default: Oran (31)

        combo = ctk.CTkComboBox(self.card, values=names, variable=self.wilaya_var,
                                 width=380, height=40, font=FONTS["body"],
                                 fg_color=pal["input_bg"], button_color=pal["primary"],
                                 dropdown_fg_color=pal["input_bg"])
        combo.pack(padx=24, pady=10)

        ctk.CTkButton(self.card, text="Suivant  →", width=380, height=44,
                       font=FONTS["button"], fg_color=pal["primary"],
                       hover_color=pal["primary_hover"],
                       command=self._confirm_wilaya
                       ).pack(padx=24, pady=(40, 12), side="bottom")

    def _confirm_wilaya(self):
        raw = self.wilaya_var.get()
        code_str = raw.split("—")[0].strip()
        code = int(code_str)
        name = dict(WILAYAS)[code]
        self.selected_wilaya = (code, name)
        self.step = 1
        self._render_step()

    # ------------------------------------------------------------------ #
    # Step 1 — Institution type & name
    # ------------------------------------------------------------------ #
    def _render_institution_step(self):
        pal = self.pal
        ctk.CTkLabel(self.card, text="2️⃣  Type & Nom de l'établissement",
                      font=FONTS["subtitle"], text_color=pal["text"]
                      ).pack(padx=24, pady=(24, 12), anchor="w")

        self.type_var = ctk.StringVar(value=INSTITUTION_TYPES[0])
        ctk.CTkLabel(self.card, text="Type d'établissement", font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(padx=24, anchor="w")
        ctk.CTkSegmentedButton(self.card, values=INSTITUTION_TYPES,
                                variable=self.type_var, height=36,
                                selected_color=pal["primary"],
                                selected_hover_color=pal["primary_hover"]
                                ).pack(padx=24, pady=(4, 16), fill="x")

        ctk.CTkLabel(self.card, text="Nom de l'établissement", font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(padx=24, anchor="w")
        self.name_entry = ctk.CTkEntry(self.card, width=380, height=40,
                                        placeholder_text="ex: EPH AADL Ain Beida",
                                        fg_color=pal["input_bg"], font=FONTS["body"])
        self.name_entry.pack(padx=24, pady=(4, 10))

        nav = ctk.CTkFrame(self.card, fg_color="transparent")
        nav.pack(padx=24, pady=(30, 12), side="bottom", fill="x")
        ctk.CTkButton(nav, text="←  Retour", width=110, height=44,
                       fg_color="transparent", border_width=1,
                       border_color=pal["card_border"], text_color=pal["text"],
                       command=self._go_back).pack(side="left")
        ctk.CTkButton(nav, text="Générer la clé  →", width=250, height=44,
                       font=FONTS["button"], fg_color=pal["primary"],
                       hover_color=pal["primary_hover"],
                       command=self._confirm_institution).pack(side="right")

    def _go_back(self):
        self.step -= 1
        self._render_step()

    def _confirm_institution(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("TASHIL", "Veuillez saisir le nom de l'établissement.")
            return
        self.selected_institution_type = self.type_var.get()
        self.institution_name_value = name
        self.generated_serial = generate_serial_key(
            self.selected_wilaya[0], self.selected_institution_type, name
        )
        self.step = 2
        self._render_step()

    # ------------------------------------------------------------------ #
    # Step 2 — Serial key confirmation
    # ------------------------------------------------------------------ #
    def _render_serial_step(self):
        pal = self.pal
        ctk.CTkLabel(self.card, text="3️⃣  Clé d'activation générée",
                      font=FONTS["subtitle"], text_color=pal["text"]
                      ).pack(padx=24, pady=(24, 12), anchor="w")

        summary = (f"Wilaya : {self.selected_wilaya[1]}\n"
                   f"Type : {self.selected_institution_type}\n"
                   f"Établissement : {self.institution_name_value}")
        ctk.CTkLabel(self.card, text=summary, font=FONTS["body"],
                      text_color=pal["text_muted"], justify="left"
                      ).pack(padx=24, pady=(0, 16), anchor="w")

        key_frame = ctk.CTkFrame(self.card, fg_color=pal["input_bg"], corner_radius=10)
        key_frame.pack(padx=24, pady=10, fill="x")
        ctk.CTkLabel(key_frame, text=self.generated_serial, font=(FONTS["body"][0], 16, "bold"),
                      text_color=pal["primary"]).pack(padx=16, pady=14)

        nav = ctk.CTkFrame(self.card, fg_color="transparent")
        nav.pack(padx=24, pady=(30, 12), side="bottom", fill="x")
        ctk.CTkButton(nav, text="←  Retour", width=110, height=44,
                       fg_color="transparent", border_width=1,
                       border_color=pal["card_border"], text_color=pal["text"],
                       command=self._go_back).pack(side="left")
        ctk.CTkButton(nav, text="✅  Activer TASHIL", width=250, height=44,
                       font=FONTS["button"], fg_color=pal["success"],
                       command=self._finalize).pack(side="right")

    def _finalize(self):
        save_profile(
            wilaya_code=self.selected_wilaya[0],
            wilaya_name=self.selected_wilaya[1],
            institution_type=self.selected_institution_type,
            institution_name=self.institution_name_value,
            serial_key=self.generated_serial,
        )
        self.destroy()
        self.on_complete()
