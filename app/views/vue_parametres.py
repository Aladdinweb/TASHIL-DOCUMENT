# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — vue_parametres.py
Profile display, language selector, notification toggles, appearance mode,
and GitHub Release updater section.
"""

import customtkinter as ctk

from app.config import LANGUAGES
from app.utils.theme import get_palette, FONTS
from app.utils.database import get_profile, update_profile_field
from app.utils.updater import check_for_update, download_update, launch_updater_and_exit
from app.utils.notifications import show_toast


class VueParametres(ctk.CTkFrame):
    def __init__(self, master, appearance_mode: str = "Dark", on_appearance_change=None):
        pal = get_palette(appearance_mode)
        super().__init__(master, fg_color=pal["bg"])
        self.pal = pal
        self.appearance_mode = appearance_mode
        self.on_appearance_change = on_appearance_change
        self.profile = get_profile()

        ctk.CTkLabel(self, text="Paramètres", font=FONTS["title"],
                      text_color=pal["text"]).place(x=32, y=24)

        self._build_profile_card()
        self._build_preferences_card()
        self._build_updater_card()

    # ------------------------------------------------------------------ #
    def _card(self, x, y, w, h, title):
        pal = self.pal
        card = ctk.CTkFrame(self, fg_color=pal["card"], corner_radius=14,
                             border_width=1, border_color=pal["card_border"],
                             width=w, height=h)
        card.place(x=x, y=y)
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=title, font=FONTS["subtitle"], text_color=pal["text"]
                      ).pack(anchor="w", padx=20, pady=(16, 6))
        return card

    def _build_profile_card(self):
        pal = self.pal
        card = self._card(32, 80, 420, 220, "🏥  Profil de l'établissement")
        p = self.profile
        info = (f"Wilaya : {p['wilaya_name'] if p else '—'}\n"
                f"Type : {p['institution_type'] if p else '—'}\n"
                f"Nom : {p['institution_name'] if p else '—'}")
        ctk.CTkLabel(card, text=info, font=FONTS["body"], text_color=pal["text_muted"],
                      justify="left").pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(card, text="Clé de licence", font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(anchor="w", padx=20)
        key_box = ctk.CTkFrame(card, fg_color=pal["input_bg"], corner_radius=8)
        key_box.pack(anchor="w", padx=20, pady=(4, 10), fill="x")
        ctk.CTkLabel(key_box, text=p["serial_key"] if p else "—",
                      font=(FONTS["body"][0], 13, "bold"), text_color=pal["primary"]
                      ).pack(padx=12, pady=8)

    def _build_preferences_card(self):
        pal = self.pal
        card = self._card(472, 80, 428, 220, "🌐  Préférences")

        ctk.CTkLabel(card, text="Langue", font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(anchor="w", padx=20)
        self.lang_var = ctk.StringVar(
            value=self.profile["language"] if self.profile else LANGUAGES[0])
        ctk.CTkSegmentedButton(card, values=LANGUAGES, variable=self.lang_var,
                                selected_color=pal["primary"],
                                command=self._on_language_change
                                ).pack(anchor="w", padx=20, pady=(4, 12), fill="x")

        ctk.CTkLabel(card, text="Apparence", font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(anchor="w", padx=20)
        self.appearance_var = ctk.StringVar(value=self.appearance_mode)
        ctk.CTkSegmentedButton(card, values=["Dark", "Light"], variable=self.appearance_var,
                                selected_color=pal["primary"],
                                command=self._on_appearance_toggle
                                ).pack(anchor="w", padx=20, pady=(4, 12), fill="x")

        self.toast_var = ctk.BooleanVar(value=bool(self.profile["notif_toast"]) if self.profile else True)
        self.sound_var = ctk.BooleanVar(value=bool(self.profile["notif_sound"]) if self.profile else True)
        ctk.CTkSwitch(card, text="Notifications visuelles (toast)", variable=self.toast_var,
                       progress_color=pal["primary"],
                       command=lambda: update_profile_field("notif_toast", int(self.toast_var.get()))
                       ).pack(anchor="w", padx=20, pady=(2, 4))
        ctk.CTkSwitch(card, text="Notifications sonores", variable=self.sound_var,
                       progress_color=pal["primary"],
                       command=lambda: update_profile_field("notif_sound", int(self.sound_var.get()))
                       ).pack(anchor="w", padx=20, pady=(2, 4))

    def _build_updater_card(self):
        pal = self.pal
        card = self._card(32, 320, 868, 160, "🔄  Mises à jour (GitHub Releases)")

        self.update_status_label = ctk.CTkLabel(card, text="Statut : inconnu",
                                                  font=FONTS["body"], text_color=pal["text_muted"])
        self.update_status_label.pack(anchor="w", padx=20)

        self.update_progress = ctk.CTkProgressBar(card, width=400, progress_color=pal["primary"])
        self.update_progress.set(0)
        self.update_progress.pack(anchor="w", padx=20, pady=10)

        ctk.CTkButton(card, text="🔍  Vérifier les mises à jour", width=240, height=38,
                       fg_color=pal["primary"], command=self._check_updates
                       ).pack(anchor="w", padx=20)

    # ------------------------------------------------------------------ #
    def _on_language_change(self, value):
        update_profile_field("language", value)
        show_toast(self, "Langue mise à jour (redémarrage recommandé)",
                    kind="info", appearance_mode=self.appearance_mode)

    def _on_appearance_toggle(self, value):
        if self.on_appearance_change:
            self.on_appearance_change(value)

    def _check_updates(self):
        self.update_status_label.configure(text="Recherche en cours...")
        self.after(100, self._do_check_updates)

    def _do_check_updates(self):
        result = check_for_update()
        if result is None:
            self.update_status_label.configure(text="✅ TASHIL est à jour.")
            return
        self.update_status_label.configure(
            text=f"⬆️  Version {result['version']} disponible — téléchargement...")

        def progress_cb(pct):
            self.update_progress.set(pct / 100)

        try:
            path = download_update(result["download_url"], on_progress=progress_cb)
            self.update_status_label.configure(text="✅ Téléchargé — redémarrage pour installer...")
            self.after(1200, lambda: launch_updater_and_exit(path))
        except Exception as exc:
            self.update_status_label.configure(text=f"⛔ Échec du téléchargement : {exc}")
