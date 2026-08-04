# COPYRIGHT ILINE TECH 2026 BY FERAK ALADDIN
"""
Administration TASHIL v1.1.38
Interface professionnelle : Messagerie inter-polycliniques
+ Rollover + Infos système
"""
import datetime
import customtkinter as ctk
from tkinter import messagebox, filedialog
from app.utils.theme import COULEURS, POLICES, DIMENSIONS
from app.utils.database import get_connection, get_config

try:
    from app.config import APP_NAME
except Exception:
    APP_NAME = "TASHIL"


class VueAdministration(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=COULEURS["bg_principal"],
            corner_radius=0, **kwargs)
        self._onglet_actif = "envoi"
        self._construire()

    def _construire(self):
        # ── En-tête ──────────────────────────
        f_head = ctk.CTkFrame(
            self, fg_color=COULEURS["bg_sidebar"],
            corner_radius=0, height=60)
        f_head.pack(fill="x")
        f_head.pack_propagate(False)

        ctk.CTkLabel(
            f_head,
            text="Administration",
            font=POLICES["titre_page"],
            text_color=COULEURS["texte_principal"]
        ).pack(side="left", padx=24,
               pady=16)

        poly = get_config("poly_nom") or "ES-SENIA"
        ctk.CTkLabel(
            f_head,
            text=f"🇩🇿  {poly}",
            font=("Segoe UI", 10, "bold"),
            text_color=COULEURS["accent_bleu"]
        ).pack(side="right", padx=24)

        # ── Onglets ──────────────────────────
        f_tabs = ctk.CTkFrame(
            self,
            fg_color=COULEURS["bg_carte"],
            corner_radius=0, height=48)
        f_tabs.pack(fill="x")
        f_tabs.pack_propagate(False)

        self._tabs_btns = {}
        tabs = [
            ("envoi",      "📤  Boîte d'envoi"),
            ("reception",  "📥  Boîte de réception"),
            ("rollover",   "🔄  Rollover & Branches"),
            ("systeme",    "ℹ️  Système"),
        ]
        for cle, lib in tabs:
            btn = ctk.CTkButton(
                f_tabs, text=lib,
                height=36,
                fg_color=(COULEURS["accent_bleu"]
                          if cle == self._onglet_actif
                          else "transparent"),
                hover_color=COULEURS["bg_hover"],
                text_color=(
                    "#FFFFFF"
                    if cle == self._onglet_actif
                    else COULEURS["texte_secondaire"]),
                font=POLICES["bouton"],
                corner_radius=6,
                command=lambda c=cle:
                    self._changer_onglet(c))
            btn.pack(side="left", padx=(8, 0),
                     pady=6)
            self._tabs_btns[cle] = btn

        # ── Zone contenu ─────────────────────
        self._frame_contenu = ctk.CTkFrame(
            self,
            fg_color=COULEURS["bg_principal"],
            corner_radius=0)
        self._frame_contenu.pack(
            fill="both", expand=True)

        self._afficher_envoi()

    def _changer_onglet(self, cle: str):
        self._onglet_actif = cle
        for k, btn in self._tabs_btns.items():
            if k == cle:
                btn.configure(
                    fg_color=COULEURS["accent_bleu"],
                    text_color="#FFFFFF")
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COULEURS["texte_secondaire"])

        for w in self._frame_contenu.winfo_children():
            w.destroy()

        {
            "envoi":     self._afficher_envoi,
            "reception": self._afficher_reception,
            "rollover":  self._afficher_rollover,
            "systeme":   self._afficher_systeme,
        }[cle]()

    # ══════════════════════════════════════════
    # ONGLET : BOÎTE D'ENVOI
    # ══════════════════════════════════════════
    def _afficher_envoi(self):
        scroll = ctk.CTkScrollableFrame(
            self._frame_contenu,
            fg_color="transparent",
            scrollbar_button_color=COULEURS["accent_bleu"])
        scroll.pack(fill="both", expand=True,
                    padx=24, pady=20)

        ctk.CTkLabel(
            scroll,
            text="Envoyer un message / document",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 16))

        # Expéditeur
        poly = get_config("poly_nom") or "ES-SENIA"
        self._champ_label(
            scroll, "Expéditeur (pré-rempli)")
        e_exp = ctk.CTkEntry(
            scroll, height=38,
            fg_color=COULEURS["bg_champ"],
            border_color=COULEURS["bordure"],
            text_color=COULEURS["texte_discret"],
            font=POLICES["corps"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            state="disabled")
        e_exp.pack(fill="x", pady=(4, 12))
        e_exp.configure(state="normal")
        e_exp.insert(0, f"SERVICE {poly}")
        e_exp.configure(state="disabled")

        # Destinataire
        self._champ_label(
            scroll, "Destinataire (Polyclinique)")
        polys = self._charger_polycliniques()
        self.m_dest = ctk.CTkOptionMenu(
            scroll, values=polys,
            height=38,
            fg_color=COULEURS["bg_champ"],
            button_color=COULEURS["accent_bleu"],
            button_hover_color=COULEURS["accent_bleu_clair"],
            dropdown_fg_color=COULEURS["bg_carte"],
            dropdown_hover_color=COULEURS["bg_hover"],
            text_color=COULEURS["texte_principal"],
            dropdown_text_color=COULEURS["texte_principal"],
            font=POLICES["corps"],
            corner_radius=DIMENSIONS["rayon_bouton"])
        self.m_dest.pack(fill="x", pady=(4, 12))
        if polys:
            self.m_dest.set(polys[0])

        # Objet
        self._champ_label(scroll, "Objet")
        self.e_objet = ctk.CTkEntry(
            scroll, height=38,
            placeholder_text="Ex : Transmission dossier",
            fg_color=COULEURS["bg_champ"],
            border_color=COULEURS["bordure"],
            text_color=COULEURS["texte_principal"],
            placeholder_text_color=COULEURS["texte_discret"],
            font=POLICES["corps"],
            corner_radius=DIMENSIONS["rayon_bouton"])
        self.e_objet.pack(fill="x",
                          pady=(4, 12))

        # Message
        self._champ_label(scroll, "Message")
        self.t_message = ctk.CTkTextbox(
            scroll, height=100,
            fg_color=COULEURS["bg_champ"],
            border_color=COULEURS["bordure"],
            text_color=COULEURS["texte_principal"],
            font=POLICES["corps"],
            corner_radius=DIMENSIONS["rayon_bouton"])
        self.t_message.pack(fill="x",
                            pady=(4, 12))
        self.t_message.insert(
            "1.0", "Corps du message…")

        # Pièce jointe
        self._champ_label(scroll, "Pièce jointe")
        f_pj = ctk.CTkFrame(
            scroll,
            fg_color=COULEURS["bg_champ"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            height=50)
        f_pj.pack(fill="x", pady=(4, 16))
        f_pj.pack_propagate(False)

        self.lbl_pj = ctk.CTkLabel(
            f_pj,
            text="Aucun fichier sélectionné",
            font=POLICES["corps"],
            text_color=COULEURS["texte_discret"])
        self.lbl_pj.pack(
            side="left", padx=14)

        ctk.CTkButton(
            f_pj, text="＋ Attacher",
            width=110, height=32,
            fg_color=COULEURS["accent_bleu"],
            hover_color=COULEURS["accent_bleu_clair"],
            text_color="#FFFFFF",
            font=POLICES["bouton"],
            corner_radius=6,
            command=self._attacher_fichier
        ).pack(side="right", padx=10)

        # Bouton envoyer
        ctk.CTkButton(
            scroll, text="📤  Envoyer",
            height=44,
            fg_color=COULEURS["accent_bleu"],
            hover_color=COULEURS["accent_bleu_clair"],
            text_color="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._envoyer_message
        ).pack(fill="x", pady=(0, 16))

        # Messages envoyés
        ctk.CTkLabel(
            scroll,
            text="Messages envoyés",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 8))

        self._afficher_messages_envoyes(scroll)

    def _attacher_fichier(self):
        chemin = filedialog.askopenfilename(
            title="Sélectionner un fichier",
            filetypes=[
                ("Documents",
                 "*.pdf *.docx *.xlsx *.jpg *.png"),
                ("Tous", "*.*")])
        if chemin:
            import os
            nom = os.path.basename(chemin)
            self.lbl_pj.configure(
                text=nom,
                text_color=COULEURS["accent_vert"])
            self._fichier_joint = chemin
        else:
            self._fichier_joint = None

    def _envoyer_message(self):
        dest  = (self.m_dest.get()
                 if hasattr(self, "m_dest") else "")
        objet = (self.e_objet.get().strip()
                 if hasattr(self, "e_objet") else "")
        msg   = (self.t_message.get("1.0", "end").strip()
                 if hasattr(self, "t_message") else "")

        if not dest or "Sélectionner" in dest:
            messagebox.showwarning(
                "Champ manquant",
                "Sélectionnez un destinataire.")
            return
        if not objet:
            messagebox.showwarning(
                "Champ manquant",
                "Entrez un objet.")
            return

        poly_src = get_config("poly_nom") or "?"
        try:
            conn = get_connection()
            conn.execute("""
                INSERT INTO messages
                    (expediteur, destinataire,
                     objet, corps, date_envoi,
                     lu)
                VALUES (?,?,?,?,?,0)
            """, (poly_src, dest, objet, msg,
                  datetime.datetime.now().isoformat()))
            conn.commit()
            conn.close()
            messagebox.showinfo(
                "✅  Message envoyé",
                f"Message envoyé à :\n{dest}")
            self.e_objet.delete(0, "end")
            self.t_message.delete("1.0", "end")
            self.t_message.insert(
                "1.0", "Corps du message…")
            if hasattr(self, "lbl_pj"):
                self.lbl_pj.configure(
                    text="Aucun fichier sélectionné",
                    text_color=COULEURS["texte_discret"])
            self._fichier_joint = None
        except Exception as ex:
            messagebox.showerror(
                "Erreur", str(ex))

    def _afficher_messages_envoyes(self, parent):
        try:
            poly = get_config("poly_nom") or ""
            conn = get_connection()
            msgs = conn.execute("""
                SELECT objet, destinataire,
                       date_envoi, lu
                FROM messages
                WHERE expediteur LIKE ?
                ORDER BY date_envoi DESC
                LIMIT 20
            """, (f"%{poly}%",)).fetchall()
            conn.close()
        except Exception:
            msgs = []

        if not msgs:
            ctk.CTkLabel(
                parent,
                text="Aucun message envoyé.",
                font=POLICES["corps"],
                text_color=COULEURS["texte_discret"]
            ).pack(pady=20)
            return

        for idx, m in enumerate(msgs):
            bg = (COULEURS["bg_carte"]
                  if idx % 2 == 0
                  else COULEURS["bg_champ"])
            f = ctk.CTkFrame(
                parent, fg_color=bg,
                corner_radius=6)
            f.pack(fill="x", pady=2)

            try:
                dt = datetime.datetime.fromisoformat(
                    m["date_envoi"]
                ).strftime("%d/%m/%Y %H:%M")
            except Exception:
                dt = m["date_envoi"]

            ctk.CTkLabel(
                f,
                text=f"📤  {m['objet']}",
                font=POLICES["corps_bold"],
                text_color=COULEURS["texte_principal"]
            ).pack(anchor="w", padx=12,
                   pady=(8, 2))
            ctk.CTkLabel(
                f,
                text=f"À : {m['destinataire']}  "
                     f"•  {dt}",
                font=POLICES["petit"],
                text_color=COULEURS["texte_secondaire"]
            ).pack(anchor="w", padx=12,
                   pady=(0, 8))

    # ══════════════════════════════════════════
    # ONGLET : BOÎTE DE RÉCEPTION
    # ══════════════════════════════════════════
    def _afficher_reception(self):
        scroll = ctk.CTkScrollableFrame(
            self._frame_contenu,
            fg_color="transparent",
            scrollbar_button_color=COULEURS["accent_bleu"])
        scroll.pack(fill="both", expand=True,
                    padx=24, pady=20)

        ctk.CTkLabel(
            scroll,
            text="Boîte de réception",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 16))

        try:
            poly = get_config("poly_nom") or ""
            conn = get_connection()
            msgs = conn.execute("""
                SELECT id, objet, expediteur,
                       date_envoi, lu, corps
                FROM messages
                WHERE destinataire LIKE ?
                ORDER BY date_envoi DESC
                LIMIT 50
            """, (f"%{poly}%",)).fetchall()
            conn.close()
        except Exception:
            msgs = []

        if not msgs:
            ctk.CTkFrame(
                scroll,
                fg_color=COULEURS["bg_carte"],
                corner_radius=12,
                height=120
            ).pack(fill="x")
            ctk.CTkLabel(
                scroll,
                text="📭  Aucun message reçu.",
                font=POLICES["sous_titre"],
                text_color=COULEURS["texte_discret"],
                justify="center"
            ).pack(pady=40)
            return

        non_lus = sum(
            1 for m in msgs if not m["lu"])
        if non_lus > 0:
            ctk.CTkLabel(
                scroll,
                text=f"🔔  {non_lus} message(s) "
                     "non lu(s)",
                font=POLICES["corps_bold"],
                text_color=COULEURS["accent_orange"]
            ).pack(anchor="w", pady=(0, 10))

        for idx, m in enumerate(msgs):
            non_lu = not m["lu"]
            bg = (COULEURS["bg_carte"]
                  if idx % 2 == 0
                  else COULEURS["bg_champ"])
            f = ctk.CTkFrame(
                scroll, fg_color=bg,
                corner_radius=8,
                border_width=1 if non_lu else 0,
                border_color=COULEURS["accent_bleu"])
            f.pack(fill="x", pady=3)

            try:
                dt = datetime.datetime.fromisoformat(
                    m["date_envoi"]
                ).strftime("%d/%m/%Y %H:%M")
            except Exception:
                dt = m["date_envoi"]

            fh = ctk.CTkFrame(
                f, fg_color="transparent")
            fh.pack(fill="x", padx=12,
                    pady=(10, 4))

            ctk.CTkLabel(
                fh,
                text=("🔵  " if non_lu else "")
                     + m["objet"],
                font=("Segoe UI", 12,
                      "bold" if non_lu else "normal"),
                text_color=COULEURS["texte_principal"]
            ).pack(side="left")

            ctk.CTkLabel(
                fh, text=dt,
                font=POLICES["petit"],
                text_color=COULEURS["texte_discret"]
            ).pack(side="right")

            ctk.CTkLabel(
                f,
                text=f"De : {m['expediteur']}",
                font=POLICES["petit"],
                text_color=COULEURS["accent_bleu"]
            ).pack(anchor="w", padx=12,
                   pady=(0, 4))

            if m["corps"] and m["corps"].strip():
                ctk.CTkLabel(
                    f,
                    text=m["corps"][:120] + (
                        "…" if len(m["corps"]) > 120
                        else ""),
                    font=POLICES["corps"],
                    text_color=COULEURS["texte_secondaire"],
                    wraplength=600, justify="left"
                ).pack(anchor="w", padx=12,
                       pady=(0, 10))

            # Marquer comme lu au clic
            mid = m["id"]
            f.bind("<Button-1>",
                   lambda e, i=mid:
                       self._marquer_lu(i))

    def _marquer_lu(self, msg_id: int):
        try:
            conn = get_connection()
            conn.execute(
                "UPDATE messages SET lu=1 WHERE id=?",
                (msg_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ══════════════════════════════════════════
    # ONGLET : ROLLOVER & BRANCHES
    # ══════════════════════════════════════════
    def _afficher_rollover(self):
        scroll = ctk.CTkScrollableFrame(
            self._frame_contenu,
            fg_color="transparent",
            scrollbar_button_color=COULEURS["accent_bleu"])
        scroll.pack(fill="both", expand=True,
                    padx=24, pady=20)

        ctk.CTkLabel(
            scroll,
            text="Rollover & Branches",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 16))

        # Info rollover
        f_info = ctk.CTkFrame(
            scroll,
            fg_color=COULEURS["bg_carte"],
            corner_radius=10)
        f_info.pack(fill="x", pady=(0, 16))

        today = datetime.date.today()
        ctk.CTkLabel(
            f_info,
            text="ℹ️  Rollover automatique",
            font=POLICES["corps_bold"],
            text_color=COULEURS["accent_bleu"]
        ).pack(anchor="w", padx=16,
               pady=(14, 4))
        ctk.CTkLabel(
            f_info,
            text="Le rollover du 1er Mai transfère "
                 "automatiquement les reliquats "
                 "non utilisés de l'année précédente "
                 "vers l'année courante.",
            font=POLICES["corps"],
            text_color=COULEURS["texte_secondaire"],
            wraplength=700, justify="left"
        ).pack(anchor="w", padx=16,
               pady=(0, 14))

        # Boutons rollover
        f_btns = ctk.CTkFrame(
            scroll, fg_color="transparent")
        f_btns.pack(fill="x", pady=(0, 16))

        ctk.CTkButton(
            f_btns,
            text="🔍  Vérifier le rollover",
            height=40,
            fg_color=COULEURS["bg_champ"],
            hover_color=COULEURS["bg_hover"],
            text_color=COULEURS["texte_principal"],
            font=POLICES["bouton"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._verifier_rollover
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            f_btns,
            text="⚡  Exécuter le rollover",
            height=40,
            fg_color=COULEURS["accent_orange"],
            hover_color="#D97706",
            text_color="#FFFFFF",
            font=POLICES["bouton"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._executer_rollover
        ).pack(side="left")

        self.lbl_rollover = ctk.CTkLabel(
            scroll, text="",
            font=POLICES["corps"],
            text_color=COULEURS["accent_vert"],
            wraplength=700)
        self.lbl_rollover.pack(
            anchor="w", pady=(0, 20))

        # 7 branches
        ctk.CTkLabel(
            scroll,
            text="Branches EPSP ES-SENIA",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 8))

        polys = [
            ("POLY_01", "POLYCLINIQUE ES SENIA"),
            ("POLY_02", "POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF"),
            ("POLY_03", "POLYCLINIQUE AIN BEIDA 1"),
            ("POLY_04", "POLYCLINIQUE AIN BEIDA 2"),
            ("POLY_05", "POLYCLINIQUE SIDI MAAROUF"),
            ("POLY_06", "POLYCLINIQUE SIDI CHAHMI"),
            ("POLY_07", "POLYCLINIQUE EL KERMA"),
        ]
        poly_active = get_config("poly_nom") or ""

        for code, nom in polys:
            est_active = poly_active in nom
            f = ctk.CTkFrame(
                scroll,
                fg_color=COULEURS["bg_carte"],
                corner_radius=8,
                border_width=2 if est_active else 0,
                border_color=COULEURS["accent_bleu"])
            f.pack(fill="x", pady=3)

            ctk.CTkLabel(
                f, text=code,
                font=POLICES["petit"],
                text_color=COULEURS["texte_discret"],
                width=70, anchor="w"
            ).pack(side="left", padx=12, pady=10)

            ctk.CTkLabel(
                f, text=nom,
                font=POLICES["corps_bold"],
                text_color=(COULEURS["accent_bleu"]
                            if est_active
                            else COULEURS["texte_principal"])
            ).pack(side="left")

            if est_active:
                ctk.CTkLabel(
                    f, text="● CE POSTE",
                    font=POLICES["petit"],
                    text_color=COULEURS["accent_vert"]
                ).pack(side="right", padx=12)

    def _verifier_rollover(self):
        try:
            from app.utils.deduction_engine import (
                verifier_rollover_necessaire)
            necessaire = verifier_rollover_necessaire()
            if necessaire:
                self.lbl_rollover.configure(
                    text="⚠️  Rollover nécessaire — "
                         "Cliquez sur "
                         "« Exécuter le rollover ».",
                    text_color=COULEURS["accent_orange"])
            else:
                self.lbl_rollover.configure(
                    text="✅  Rollover déjà effectué "
                         "pour cette année.",
                    text_color=COULEURS["accent_vert"])
        except Exception as ex:
            self.lbl_rollover.configure(
                text=f"Erreur : {ex}",
                text_color=COULEURS["accent_rouge"])

    def _executer_rollover(self):
        rep = messagebox.askyesno(
            "⚡  Rollover",
            "Exécuter le rollover du 1er Mai ?\n\n"
            "Les reliquats non utilisés seront "
            "transférés vers l'année courante.")
        if not rep:
            return
        try:
            from app.utils.deduction_engine import (
                executer_rollover_mai)
            res = executer_rollover_mai(dry_run=False)
            nb  = res.get("nb_employes", 0)
            messagebox.showinfo(
                "✅  Rollover effectué",
                f"{nb} employé(s) traité(s).")
            self.lbl_rollover.configure(
                text=f"✅  Rollover effectué — "
                     f"{nb} employé(s) traité(s).",
                text_color=COULEURS["accent_vert"])
        except Exception as ex:
            messagebox.showerror(
                "Erreur", str(ex))

    # ══════════════════════════════════════════
    # ONGLET : SYSTÈME
    # ══════════════════════════════════════════
    def _afficher_systeme(self):
        scroll = ctk.CTkScrollableFrame(
            self._frame_contenu,
            fg_color="transparent",
            scrollbar_button_color=COULEURS["accent_bleu"])
        scroll.pack(fill="both", expand=True,
                    padx=24, pady=20)

        ctk.CTkLabel(
            scroll,
            text="Informations système",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 16))

        from app.utils.version import get_version
        import sys, os, platform

        poly    = get_config("poly_nom") or "—"
        act     = get_config("activation_done") or "—"
        db_path = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)),
            "..", "..", "data", "reliquat.db")

        infos = [
            ("Application", f"TASHIL v{get_version()}"),
            ("Polyclinique", poly),
            ("Activation", "✅ Activé" if act else "❌ Non activé"),
            ("Base de données", os.path.abspath(db_path)),
            ("Système", platform.system() + " " + platform.release()),
            ("Python", sys.version.split()[0]),
            ("Date", datetime.datetime.now().strftime("%d/%m/%Y %H:%M")),
            ("Copyright", "ILINE TECH 2026 — FERAK ALADDIN"),
        ]

        f_card = ctk.CTkFrame(
            scroll,
            fg_color=COULEURS["bg_carte"],
            corner_radius=12)
        f_card.pack(fill="x", pady=(0, 16))

        for label, val in infos:
            f = ctk.CTkFrame(
                f_card, fg_color="transparent")
            f.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(
                f, text=label + " :",
                font=POLICES["corps_bold"],
                text_color=COULEURS["texte_secondaire"],
                width=160, anchor="w"
            ).pack(side="left")
            ctk.CTkLabel(
                f, text=str(val),
                font=POLICES["corps"],
                text_color=COULEURS["texte_principal"],
                wraplength=500, justify="left"
            ).pack(side="left")

        # Bouton backup
        ctk.CTkButton(
            scroll,
            text="💾  Faire une sauvegarde maintenant",
            height=42,
            fg_color=COULEURS["accent_vert"],
            hover_color="#059669",
            text_color="#FFFFFF",
            font=POLICES["bouton"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._faire_backup
        ).pack(fill="x", pady=(8, 4))

        ctk.CTkButton(
            scroll,
            text="🗑  Réinitialiser l'activation",
            height=38,
            fg_color=COULEURS["bg_champ"],
            hover_color=COULEURS["accent_rouge"],
            text_color=COULEURS["texte_secondaire"],
            font=POLICES["bouton"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._reinitialiser_activation
        ).pack(fill="x", pady=(4, 4))

    def _faire_backup(self):
        try:
            from app.utils.database import faire_backup
            chemin = faire_backup("manuel")
            messagebox.showinfo(
                "✅  Sauvegarde",
                f"Sauvegarde créée :\n{chemin}")
        except Exception as ex:
            messagebox.showerror(
                "Erreur", str(ex))

    def _reinitialiser_activation(self):
        rep = messagebox.askyesno(
            "⚠️  Réinitialisation",
            "Réinitialiser l'activation de ce poste ?\n\n"
            "L'application demandera une nouvelle "
            "activation au prochain démarrage.",
            icon="warning")
        if rep:
            try:
                conn = get_connection()
                conn.execute(
                    "DELETE FROM config "
                    "WHERE cle IN "
                    "('activation_done','poly_nom',"
                    "'poly_id','activation_code')")
                conn.commit()
                conn.close()
                messagebox.showinfo(
                    "✅  Réinitialisé",
                    "Redémarrez l'application.")
            except Exception as ex:
                messagebox.showerror(
                    "Erreur", str(ex))

    # ── Helpers ──────────────────────────────
    def _champ_label(self, parent, texte: str):
        ctk.CTkLabel(
            parent, text=texte,
            font=POLICES["corps_bold"],
            text_color=COULEURS["texte_secondaire"]
        ).pack(anchor="w")

    def _charger_polycliniques(self) -> list:
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT nom FROM polycliniques "
                "ORDER BY nom"
            ).fetchall()
            conn.close()
            return [r["nom"] for r in rows] or [
                "POLYCLINIQUE ES SENIA"]
        except Exception:
            return ["POLYCLINIQUE ES SENIA"]

    def rafraichir(self, _=None):
        try:
            self._changer_onglet(
                self._onglet_actif)
        except Exception:
            pass
