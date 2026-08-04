# COPYRIGHT ILINE TECH 2026 BY FERAK ALADDIN
"""
AppPrincipale TASHIL v1.1.38
2 onglets : Tableau de bord + Administration
Interface professionnelle épurée
"""
import customtkinter as ctk
from tkinter import messagebox
import traceback
from app.utils.theme import COULEURS, POLICES, DIMENSIONS
from app.utils.database import get_config
from app.utils.version import get_version

try:
    from app.config import APP_NAME, APP_TAGLINE
except Exception:
    APP_NAME    = "TASHIL"
    APP_TAGLINE = "Smart Health Management System"

_SW = 240  # Largeur sidebar


class AppPrincipale(ctk.CTkFrame):
    ONGLETS = [
        ("dashboard", "Tableau de bord", "◉"),
        ("admin",     "Administration",  "⚙"),
    ]

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=COULEURS["bg_principal"],
            corner_radius=0, **kwargs)
        self._vue_active  = ""
        self._boutons_nav = {}
        self._vues_cache  = {}
        self._sb = None
        self._ct = None
        self._construire()
        self._verifier_rollover_auto()
        self._naviguer("dashboard")
        self.bind("<Configure>", self._resize)

    def _construire(self):
        self._sb = ctk.CTkFrame(
            self, width=_SW,
            fg_color=COULEURS["bg_sidebar"],
            corner_radius=0)
        self._sb.place(x=0, y=0, relheight=1)
        self._sb.pack_propagate(False)

        self._ct = ctk.CTkFrame(
            self,
            fg_color=COULEURS["bg_principal"],
            corner_radius=0)
        self._ct.place(
            x=_SW, y=0,
            relwidth=1, relheight=1)

        self._remplir_sidebar()

    def _resize(self, _=None):
        try:
            self._ct.place(
                x=_SW, y=0,
                relwidth=1, relheight=1)
        except Exception:
            pass

    def _remplir_sidebar(self):
        sb = self._sb
        sc = ctk.CTkScrollableFrame(
            sb, fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COULEURS["bg_sidebar"],
            scrollbar_button_hover_color=COULEURS["bg_hover"])
        sc.pack(fill="both", expand=True)

        # ── Logo / En-tête ───────────────────
        f_head = ctk.CTkFrame(
            sc, fg_color="transparent")
        f_head.pack(fill="x", padx=14,
                    pady=(22, 0))

        # Badge drapeau 🇩🇿
        badge = ctk.CTkFrame(
            f_head, width=52, height=52,
            fg_color=COULEURS["accent_bleu"],
            corner_radius=12)
        badge.pack(side="left")
        badge.pack_propagate(False)
        ctk.CTkLabel(
            badge, text="🇩🇿",
            font=("Segoe UI Emoji", 26)
        ).pack(expand=True)

        f_txt = ctk.CTkFrame(
            f_head, fg_color="transparent")
        f_txt.pack(
            side="left", padx=(12, 0),
            fill="both", expand=True)

        ctk.CTkLabel(
            f_txt, text=APP_NAME,
            font=("Segoe UI", 18, "bold"),
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            f_txt, text=APP_TAGLINE,
            font=("Segoe UI", 8),
            text_color=COULEURS["texte_discret"],
            wraplength=140, justify="left"
        ).pack(anchor="w")

        # Polyclinique active
        poly = get_config("poly_nom") or "ES-SENIA"
        short = (poly[:18] + "…"
                 if len(poly) > 18 else poly)
        ctk.CTkLabel(
            sc, text=short,
            font=("Segoe UI", 9, "bold"),
            text_color=COULEURS["accent_bleu"],
            wraplength=200, justify="left"
        ).pack(anchor="w", padx=14,
               pady=(8, 0))

        # ── Séparateur ───────────────────────
        ctk.CTkFrame(
            sc, height=1,
            fg_color=COULEURS["bordure"]
        ).pack(fill="x", padx=14,
               pady=(16, 10))

        ctk.CTkLabel(
            sc, text="NAVIGATION",
            font=("Segoe UI", 9, "bold"),
            text_color=COULEURS["texte_discret"]
        ).pack(anchor="w", padx=18,
               pady=(0, 10))

        # ── Boutons navigation ────────────────
        for cle, lib, ico in self.ONGLETS:
            btn = ctk.CTkButton(
                sc, height=44,
                text=f"  {ico}   {lib}",
                anchor="w",
                fg_color="transparent",
                hover_color=COULEURS["bg_hover"],
                text_color=COULEURS["sidebar_inact_txt"],
                font=("Segoe UI", 13),
                corner_radius=10,
                command=lambda c=cle:
                    self._naviguer(c))
            btn.pack(fill="x", padx=10,
                     pady=3)
            self._boutons_nav[cle] = btn

        # ── Infos système ─────────────────────
        ctk.CTkFrame(
            sc, height=1,
            fg_color=COULEURS["bordure"]
        ).pack(fill="x", padx=14,
               pady=(24, 10))

        # Bouton MAJ
        self.btn_maj = ctk.CTkButton(
            sc, height=30,
            text="🔄  Vérifier les mises à jour",
            fg_color="transparent",
            hover_color=COULEURS["bg_hover"],
            text_color=COULEURS["texte_discret"],
            font=("Segoe UI", 9),
            corner_radius=6,
            command=self._verifier_maj)
        self.btn_maj.pack(
            fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(
            sc,
            text=f"v{get_version()}\n"
                 "ILINE TECH 2026\n"
                 "BY FERAK ALADDIN",
            font=("Segoe UI", 8),
            text_color=COULEURS["texte_discret"],
            justify="center"
        ).pack(pady=(0, 20))

    # ── Navigation ───────────────────────────
    def _naviguer(self, cle: str):
        if cle == self._vue_active:
            return

        for k, b in self._boutons_nav.items():
            if k == cle:
                b.configure(
                    fg_color=COULEURS["sidebar_active_bg"],
                    text_color=COULEURS["sidebar_active_txt"])
            elif "⚠" not in b.cget("text"):
                b.configure(
                    fg_color="transparent",
                    text_color=COULEURS["sidebar_inact_txt"])

        if (self._vue_active and
                self._vue_active in self._vues_cache):
            try:
                self._vues_cache[
                    self._vue_active].place_forget()
            except Exception:
                pass

        if cle not in self._vues_cache:
            try:
                vue = self._creer_vue(cle)
                vue.place(x=0, y=0,
                          relwidth=1, relheight=1)
                self._vues_cache[cle] = vue
            except Exception:
                print(f"[ERR {cle}]\n"
                      f"{traceback.format_exc()}")
                return
        else:
            self._vues_cache[cle].place(
                x=0, y=0,
                relwidth=1, relheight=1)
            try:
                self._vues_cache[cle].rafraichir()
            except Exception:
                pass

        self._vue_active = cle
        try:
            self._ct.update_idletasks()
        except Exception:
            pass

    def _creer_vue(self, cle: str):
        from app.views.vue_dashboard import (
            VueDashboard)
        from app.views.vue_administration import (
            VueAdministration)

        vues = {
            "dashboard": VueDashboard,
            "admin":     VueAdministration,
        }
        cls = vues.get(cle)
        if not cls:
            raise ValueError(
                f"Vue inconnue: {cle}")
        return cls(self._ct)

    def _verifier_rollover_auto(self):
        try:
            from app.utils.deduction_engine import (
                verifier_rollover_necessaire)
            if verifier_rollover_necessaire():
                b = self._boutons_nav.get("admin")
                if b:
                    b.configure(
                        text="  ⚙   Administration ⚠",
                        text_color=COULEURS["accent_orange"])
        except Exception:
            pass

    def _verifier_maj(self):
        self.btn_maj.configure(
            state="disabled",
            text="⏳  Vérification…")
        from app.utils.updater import (
            verifier_en_arriere_plan,
            version_plus_recente)

        def _cb(info):
            self.after(0, lambda:
                self.btn_maj.configure(
                    state="normal",
                    text="🔄  Vérifier les mises à jour"))
            if not info:
                self.after(0, lambda:
                    messagebox.showwarning(
                        "Mise à jour",
                        "Pas de connexion."))
                return
            tag = info.get("tag", "")
            if version_plus_recente(tag):
                self.after(0, lambda:
                    self._proposer_maj(info))
            else:
                self.after(0, lambda:
                    messagebox.showinfo(
                        "✅  À jour",
                        f"v{get_version()}\n"
                        f"Distante : {tag}"))

        verifier_en_arriere_plan(_cb)

    def _proposer_maj(self, info: dict):
        from app.utils.updater import (
            telecharger_et_remplacer)
        tag     = info.get("tag", "")
        url_exe = info.get("url_exe", "")
        taille  = round(
            info.get("taille", 0) / 1024 / 1024, 1)
        if not url_exe:
            messagebox.showerror(
                "Erreur", "Aucun .exe trouvé.")
            return
        if not messagebox.askyesno(
                f"🆕  {tag}",
                f"Version : {tag}\n"
                f"Taille : {taille} MB\n\n"
                "Installer maintenant ?"):
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Mise à jour…")
        dlg.configure(
            fg_color=COULEURS["bg_principal"])
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.attributes("-topmost", True)
        dlg.protocol(
            "WM_DELETE_WINDOW", lambda: None)
        dlg.geometry("400x140")

        ctk.CTkLabel(
            dlg,
            text=f"Téléchargement {tag}…",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(pady=(20, 10))

        barre = ctk.CTkProgressBar(
            dlg, height=12,
            mode="determinate",
            fg_color=COULEURS["bg_champ"],
            progress_color=COULEURS["accent_bleu"],
            corner_radius=6)
        barre.pack(fill="x", padx=30,
                   pady=(0, 6))
        barre.set(0)

        lbl = ctk.CTkLabel(
            dlg, text="0 %",
            font=POLICES["corps_bold"],
            text_color=COULEURS["accent_bleu"])
        lbl.pack()

        def _p(pct):
            self.after(0, lambda p=pct: (
                barre.set(p / 100),
                lbl.configure(text=f"{p} %")))

        def _f(ok, err):
            self.after(0, lambda:
                self._fin_maj(dlg, ok, err))

        telecharger_et_remplacer(
            url_exe, _p, _f)

    def _fin_maj(self, dlg, ok, err):
        try:
            dlg.destroy()
        except Exception:
            pass
        if ok:
            messagebox.showinfo(
                "✅", "Redémarrage en cours…")
            self.after(600, self._quitter_maj)
        else:
            messagebox.showerror(
                "❌  Échec", str(err))

    def _quitter_maj(self):
        try:
            from app.utils.database import (
                faire_backup)
            faire_backup("avant_maj")
        except Exception:
            pass
        import os
        os._exit(0)

    def rafraichir(self):
        pass
