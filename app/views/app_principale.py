# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — app_principale.py
Main application window: sidebar navigation across the 4 modules
(Dashboard, Messagerie, Administration, Paramètres) plus a fixed header
showing the app title and active institution.
"""

import customtkinter as ctk

from app.config import APP_NAME, APP_FLAG, APP_FULL_NAME
from app.utils.theme import get_palette, FONTS
from app.utils.database import get_profile, update_profile_field
from app.utils.updater import check_for_update_async
from app.utils.notifications import show_toast

from app.views.vue_dashboard import VueDashboard
from app.views.vue_messagerie import VueMessagerie
from app.views.vue_administration import VueAdministration
from app.views.vue_parametres import VueParametres


class AppPrincipale(ctk.CTkFrame):
    """
    Root application shell. MUST be placed with
    place(x=0, y=0, relwidth=1, relheight=1) — never packed.
    """

    NAV_ITEMS = [
        ("dashboard", "📊  Tableau de Bord"),
        ("messagerie", "📨  Centre de Messagerie"),
        ("administration", "🗂️  Administration & Archivage"),
        ("parametres", "⚙️  Paramètres"),
    ]

    def __init__(self, master):
        profile = get_profile()
        appearance_mode = profile["appearance_mode"] if profile else "Dark"
        pal = get_palette(appearance_mode)

        super().__init__(master, fg_color=pal["bg"])
        self.place(x=0, y=0, relwidth=1, relheight=1)

        self.master_window = master
        self.pal = pal
        self.appearance_mode = appearance_mode
        self.profile = profile
        self.active_view_name = "dashboard"
        self.active_view = None
        self.nav_buttons = {}

        self._build_sidebar()
        self._build_header()
        self._build_content_area()
        self._show_view("dashboard")

        # Safety net: re-run the geometry pass once Tk has actually mapped
        # the window, in case construction happened before real width/height
        # were available (this is what caused the blank-screen-on-launch bug).
        self.after(60, lambda: (self._reposition_header(), self._reposition_content()))

        check_for_update_async(self._on_update_check_result)

    # ------------------------------------------------------------------ #
    # Sidebar
    # ------------------------------------------------------------------ #
    def _build_sidebar(self):
        pal = self.pal
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=pal["sidebar"], width=250,
                                           corner_radius=0)
        self.sidebar_frame.place(x=0, y=0, relheight=1, width=250)

        brand = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=90)
        brand.pack(fill="x", padx=20, pady=(24, 10))
        ctk.CTkLabel(brand, text=f"{APP_FLAG}  {APP_NAME}", font=FONTS["title"],
                      text_color=pal["primary"]).pack(anchor="w")
        ctk.CTkLabel(brand, text=APP_FULL_NAME, font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(anchor="w")

        # Scrollable nav — sidebar MUST use CTkScrollableFrame with pack() internally
        self.nav_scroll = ctk.CTkScrollableFrame(self.sidebar_frame, fg_color="transparent",
                                                   scrollbar_button_color=pal["card_border"])
        self.nav_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        for key, label in self.NAV_ITEMS:
            btn = ctk.CTkButton(
                self.nav_scroll, text=label, anchor="w", height=46,
                font=FONTS["body"], corner_radius=10,
                fg_color="transparent", hover_color=pal["card"],
                text_color=pal["text"],
                command=lambda k=key: self._show_view(k)
            )
            btn.pack(fill="x", pady=4)
            self.nav_buttons[key] = btn

        footer = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=50)
        footer.pack(fill="x", padx=20, pady=16, side="bottom")
        institution = self.profile["institution_name"] if self.profile else "—"
        ctk.CTkLabel(footer, text=institution, font=FONTS["small"],
                      text_color=pal["text_muted"], wraplength=210
                      ).pack(anchor="w")

    def _highlight_active_nav(self, active_key: str):
        pal = self.pal
        for key, btn in self.nav_buttons.items():
            if key == active_key:
                btn.configure(fg_color=pal["primary"], text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=pal["text"])

    # ------------------------------------------------------------------ #
    # Header
    # ------------------------------------------------------------------ #
    def _build_header(self):
        pal = self.pal
        self.header_frame = ctk.CTkFrame(self, fg_color=pal["bg"], height=60,
                                          corner_radius=0)
        self.header_frame.place(x=250, y=0, relwidth=1, height=60,
                                 relx=0)  # positioned via update below
        self._reposition_header()

        institution = self.profile["institution_name"] if self.profile else "Non configuré"
        ctk.CTkLabel(self.header_frame, text=f"TASHIL  —  {institution}",
                      font=FONTS["subtitle"], text_color=pal["text"]
                      ).place(relx=0.98, rely=0.5, anchor="e")

        self.bind("<Configure>", lambda e: self._reposition_header())

    def _reposition_header(self):
        self.header_frame.place_configure(x=250, y=0, width=self.winfo_width() - 250, height=60)

    # ------------------------------------------------------------------ #
    # Content area / view switching
    # ------------------------------------------------------------------ #
    def _build_content_area(self):
        pal = self.pal
        self.content_frame = ctk.CTkFrame(self, fg_color=pal["bg"], corner_radius=0)
        self.content_frame.place(x=250, y=60, relwidth=1, relheight=1)
        self._reposition_content()
        self.bind("<Configure>", lambda e: (self._reposition_header(), self._reposition_content()))

    def _reposition_content(self):
        w = max(self.winfo_width() - 250, 200)
        h = max(self.winfo_height() - 60, 200)
        self.content_frame.place_configure(x=250, y=60, width=w, height=h)

    def _show_view(self, view_name: str):
        if self.active_view is not None:
            self.active_view.destroy()

        self._highlight_active_nav(view_name)
        self.active_view_name = view_name

        view_classes = {
            "dashboard": VueDashboard,
            "messagerie": VueMessagerie,
            "administration": VueAdministration,
            "parametres": VueParametres,
        }
        view_cls = view_classes[view_name]

        if view_name == "parametres":
            self.active_view = view_cls(self.content_frame, self.appearance_mode,
                                         on_appearance_change=self._on_appearance_change)
        else:
            self.active_view = view_cls(self.content_frame, self.appearance_mode)

        # All main view frames must use place(), never pack(fill='both', expand=True)
        self.active_view.place(x=0, y=0, relwidth=1, relheight=1)

    # ------------------------------------------------------------------ #
    # Appearance mode live switching
    # ------------------------------------------------------------------ #
    def _on_appearance_change(self, new_mode: str):
        self.appearance_mode = new_mode
        update_profile_field("appearance_mode", new_mode)
        ctk.set_appearance_mode(new_mode)
        self.pal = get_palette(new_mode)
        self.configure(fg_color=self.pal["bg"])
        # Rebuild the whole shell so every widget picks up the new palette
        for child in self.winfo_children():
            child.destroy()
        self._build_sidebar()
        self._build_header()
        self._build_content_area()
        self._show_view(self.active_view_name)

    # ------------------------------------------------------------------ #
    # OTA update notice
    # ------------------------------------------------------------------ #
    def _on_update_check_result(self, result):
        if result is None:
            return
        show_toast(self, f"Nouvelle version disponible : {result['version']}",
                    kind="info", appearance_mode=self.appearance_mode)
