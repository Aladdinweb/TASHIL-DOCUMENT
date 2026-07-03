# COPYRIGHT ILINE TECH 2026 BY FERAK ALADDIN
"""
Bordereau d'envoi — Drag & Drop + FIFO automatique
Dépendance : pip install tkinterdnd2
"""
import datetime
import os
import customtkinter as ctk
from tkinter import messagebox, filedialog
from app.utils.theme import COULEURS, POLICES, DIMENSIONS
from app.utils.database import get_connection


def _charger_mouvements() -> list:
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT m.id, m.employe_id,
                   m.date_debut, m.date_fin,
                   m.nb_jours, m.type_conge,
                   e.nom, e.prenom, e.grade,
                   d.nom as service,
                   ca.annee
            FROM mouvements_conge m
            JOIN employes e ON e.id = m.employe_id
            JOIN departements d ON d.id = e.departement_id
            JOIN conges_annuels ca ON ca.id = m.conge_id
            WHERE m.type_conge = 'CONGE_ANNUEL'
              AND e.actif = 1
            ORDER BY m.date_debut DESC
            LIMIT 200
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as ex:
        print(f"[Bordereau] {ex}")
        return []


class VueBordereau(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=COULEURS["bg_principal"],
            corner_radius=0, **kwargs)
        self._mouvements    = []
        self._fichiers_dnd  = []
        self._dnd_disponible = False
        self._construire()

    def _construire(self):
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COULEURS["accent_bleu"])
        scroll.pack(fill="both", expand=True,
                    padx=20, pady=20)

        # ── Titre ────────────────────────────
        ctk.CTkLabel(
            scroll, text="Bordereau d'envoi",
            font=POLICES["titre_page"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w")
        ctk.CTkLabel(
            scroll,
            text="Déduction FIFO automatique "
                 "des congés annuels",
            font=POLICES["corps"],
            text_color=COULEURS["texte_secondaire"]
        ).pack(anchor="w", pady=(2, 14))

        ctk.CTkFrame(
            scroll, height=1,
            fg_color=COULEURS["bordure"]
        ).pack(fill="x", pady=(0, 16))

        # ── Actions ──────────────────────────
        f_act = ctk.CTkFrame(
            scroll, fg_color=COULEURS["bg_carte"],
            corner_radius=8)
        f_act.pack(fill="x", pady=(0, 16))

        f_btns = ctk.CTkFrame(
            f_act, fg_color="transparent")
        f_btns.pack(fill="x", padx=16, pady=12)

        ctk.CTkButton(
            f_btns, height=38,
            text="🔍  Scanner & Vérifier FIFO",
            fg_color=COULEURS["accent_bleu"],
            hover_color=COULEURS["accent_bleu_clair"],
            text_color="#FFFFFF",
            font=POLICES["bouton"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._scanner_fifo
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            f_btns, height=38,
            text="📥  Exporter Excel",
            fg_color=COULEURS["accent_vert"],
            hover_color="#059669",
            text_color="#FFFFFF",
            font=POLICES["bouton"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._exporter_excel
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            f_btns, height=38,
            text="📂  Parcourir fichier",
            fg_color=COULEURS["bg_champ"],
            hover_color=COULEURS["bg_hover"],
            text_color=COULEURS["texte_principal"],
            font=POLICES["bouton"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._parcourir_fichier
        ).pack(side="left")

        self.lbl_resultat = ctk.CTkLabel(
            f_act, text="",
            font=POLICES["corps"],
            text_color=COULEURS["accent_vert"],
            wraplength=700, justify="left")
        self.lbl_resultat.pack(
            anchor="w", padx=16, pady=(0, 10))

        # ── Zone Drag & Drop ─────────────────
        ctk.CTkLabel(
            scroll,
            text="Documents joints",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 6))

        self.zone_dnd = ctk.CTkFrame(
            scroll,
            fg_color=COULEURS["bg_carte"],
            corner_radius=8,
            border_width=2,
            border_color=COULEURS["bordure"])
        self.zone_dnd.pack(
            fill="x", pady=(0, 16))

        self.lbl_dnd = ctk.CTkLabel(
            self.zone_dnd,
            text="📎  Glissez un fichier ici\n"
                 "ou cliquez sur « Parcourir »\n"
                 "(PDF, Word, Excel acceptés)",
            font=POLICES["corps"],
            text_color=COULEURS["texte_discret"],
            justify="center")
        self.lbl_dnd.pack(pady=30)

        # Activer drag-drop si tkinterdnd2 dispo
        self._activer_dnd()

        # ── Liste fichiers attachés ───────────
        self._frame_fichiers = ctk.CTkFrame(
            scroll, fg_color="transparent")
        self._frame_fichiers.pack(
            fill="x", pady=(0, 16))

        # ── Mouvements actifs ─────────────────
        ctk.CTkLabel(
            scroll,
            text="Congés Annuels — Mouvements actifs",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 8))

        self.liste_f = ctk.CTkFrame(
            scroll, fg_color=COULEURS["bg_carte"],
            corner_radius=8)
        self.liste_f.pack(fill="x")

        self._charger_liste()

    def _activer_dnd(self):
        """Tente d'activer tkinterdnd2."""
        try:
            from tkinterdnd2 import DND_FILES
            self.zone_dnd.drop_target_register(
                DND_FILES)
            self.zone_dnd.dnd_bind(
                "<<Drop>>", self._on_drop)
            self._dnd_disponible = True
            self.lbl_dnd.configure(
                text="📎  Glissez un fichier ici\n"
                     "(PDF, Word, Excel acceptés)",
                text_color=COULEURS["accent_bleu"])
        except Exception:
            # tkinterdnd2 non installé — fallback
            self._dnd_disponible = False
            self.lbl_dnd.configure(
                text="📎  Cliquez sur « Parcourir »\n"
                     "pour attacher un document\n"
                     "(installez tkinterdnd2 pour "
                     "le drag-drop)")

    def _on_drop(self, event):
        """Appelé quand un fichier est glissé."""
        chemin = event.data.strip().strip("{}")
        self._ajouter_fichier(chemin)

    def _parcourir_fichier(self):
        chemin = filedialog.askopenfilename(
            title="Sélectionner un document",
            filetypes=[
                ("Documents",
                 "*.pdf *.docx *.xlsx *.xls "
                 "*.doc *.txt *.png *.jpg"),
                ("Tous", "*.*"),
            ])
        if chemin:
            self._ajouter_fichier(chemin)

    def _ajouter_fichier(self, chemin: str):
        """Ajoute un fichier à la liste."""
        if not os.path.exists(chemin):
            messagebox.showerror(
                "Erreur",
                f"Fichier introuvable :\n{chemin}")
            return

        nom     = os.path.basename(chemin)
        taille  = os.path.getsize(chemin)
        taille_s = (f"{taille // 1024} KB"
                    if taille > 1024
                    else f"{taille} B")

        self._fichiers_dnd.append({
            "nom":    nom,
            "chemin": chemin,
            "taille": taille_s,
        })

        # Mise à jour label zone DND
        nb = len(self._fichiers_dnd)
        self.lbl_dnd.configure(
            text=f"📎  {nb} fichier(s) attaché(s)",
            text_color=COULEURS["accent_vert"])

        self._afficher_fichiers()

    def _afficher_fichiers(self):
        for w in self._frame_fichiers.winfo_children():
            w.destroy()

        for idx, fic in enumerate(
                self._fichiers_dnd):
            f = ctk.CTkFrame(
                self._frame_fichiers,
                fg_color=COULEURS["bg_champ"],
                corner_radius=6)
            f.pack(fill="x", pady=2)

            ext = fic["nom"].rsplit(".", 1)[-1].lower()
            icone = {
                "pdf":  "📕",
                "docx": "📘", "doc": "📘",
                "xlsx": "📗", "xls": "📗",
                "png":  "🖼", "jpg": "🖼",
            }.get(ext, "📄")

            ctk.CTkLabel(
                f,
                text=f"{icone}  {fic['nom']}",
                font=POLICES["corps_bold"],
                text_color=COULEURS["texte_principal"]
            ).pack(side="left", padx=12, pady=8)

            ctk.CTkLabel(
                f, text=fic["taille"],
                font=POLICES["petit"],
                text_color=COULEURS["texte_discret"]
            ).pack(side="left")

            def _suppr(i=idx):
                self._fichiers_dnd.pop(i)
                self._afficher_fichiers()
                nb = len(self._fichiers_dnd)
                self.lbl_dnd.configure(
                    text=(
                        f"📎  {nb} fichier(s) "
                        "attaché(s)"
                        if nb > 0
                        else "📎  Glissez un "
                             "fichier ici\nou "
                             "cliquez « Parcourir »"),
                    text_color=(
                        COULEURS["accent_vert"]
                        if nb > 0
                        else COULEURS["texte_discret"]))

            ctk.CTkButton(
                f, text="✕",
                width=28, height=28,
                fg_color="transparent",
                hover_color=COULEURS["accent_rouge"],
                text_color=COULEURS["texte_discret"],
                font=("Segoe UI", 11),
                corner_radius=4,
                command=_suppr
            ).pack(side="right", padx=10)

    def _charger_liste(self):
        for w in self.liste_f.winfo_children():
            w.destroy()

        self._mouvements = _charger_mouvements()

        if not self._mouvements:
            ctk.CTkLabel(
                self.liste_f,
                text="Aucun congé annuel "
                     "enregistré pour l'instant.",
                font=POLICES["corps"],
                text_color=COULEURS["texte_discret"]
            ).pack(pady=40)
            return

        # En-têtes
        fh = ctk.CTkFrame(
            self.liste_f,
            fg_color=COULEURS["bg_sidebar"],
            corner_radius=4)
        fh.pack(fill="x")
        for txt, w in [
            ("Employé", 180), ("Service", 140),
            ("Du", 100), ("Au", 100),
            ("Jours", 60), ("Année", 60),
        ]:
            ctk.CTkLabel(
                fh, text=txt,
                font=POLICES["tableau_head"],
                text_color=COULEURS["texte_secondaire"],
                width=w, anchor="w"
            ).pack(side="left", padx=8, pady=8)

        for idx, m in enumerate(self._mouvements):
            bg = (COULEURS["bg_carte"]
                  if idx % 2 == 0
                  else COULEURS["bg_champ"])
            fl = ctk.CTkFrame(
                self.liste_f, fg_color=bg,
                corner_radius=0)
            fl.pack(fill="x")

            try:
                d1 = datetime.date.fromisoformat(
                    m["date_debut"]
                ).strftime("%d/%m/%Y")
                d2 = datetime.date.fromisoformat(
                    m["date_fin"]
                ).strftime("%d/%m/%Y")
            except Exception:
                d1, d2 = (m["date_debut"],
                          m["date_fin"])

            for val, w in [
                (f"{m['nom']} {m['prenom']}", 180),
                (m["service"][:18], 140),
                (d1, 100), (d2, 100),
                (f"{m['nb_jours']:.0f} j", 60),
                (str(m["annee"]), 60),
            ]:
                ctk.CTkLabel(
                    fl, text=val,
                    font=POLICES["tableau"],
                    text_color=COULEURS["texte_principal"],
                    width=w, anchor="w"
                ).pack(side="left",
                       padx=8, pady=6)

    def _scanner_fifo(self):
        if not self._mouvements:
            messagebox.showinfo(
                "Info",
                "Aucun mouvement à analyser.")
            return

        conn = get_connection()
        traites = 0
        for m in self._mouvements:
            try:
                row = conn.execute("""
                    SELECT jours_initiaux
                         - jours_utilises AS restant
                    FROM conges_annuels
                    WHERE employe_id=? AND annee=?
                """, (m["employe_id"],
                      m["annee"])).fetchone()
                if row and row["restant"] >= 0:
                    traites += 1
            except Exception:
                pass
        conn.close()

        msg = (f"✅ Scan FIFO terminé.\n\n"
               f"{len(self._mouvements)} "
               f"mouvement(s) analysé(s).\n"
               f"{traites} solde(s) vérifié(s).")
        self.lbl_resultat.configure(text=msg)
        messagebox.showinfo("Scan terminé", msg)
        self._charger_liste()

    def _exporter_excel(self):
        try:
            import openpyxl
            chemin = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                title="Enregistrer le Bordereau",
                initialfile=(
                    f"Bordereau_"
                    f"{datetime.date.today()}.xlsx"))
            if not chemin:
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Bordereau"
            ws.append([
                "N°", "Nom & Prénom", "Grade",
                "Service", "Date Début",
                "Date Fin", "Jours", "Année"])
            for i, m in enumerate(
                    self._mouvements, 1):
                ws.append([
                    i,
                    f"{m['nom']} {m['prenom']}",
                    m.get("grade", ""),
                    m.get("service", ""),
                    m["date_debut"],
                    m["date_fin"],
                    m["nb_jours"], m["annee"]])
            wb.save(chemin)
            messagebox.showinfo(
                "✅  Export réussi",
                f"Fichier :\n{chemin}")
        except Exception as ex:
            messagebox.showerror(
                "Erreur export", str(ex))

    def rafraichir(self, _=None):
        try:
            self._charger_liste()
        except Exception:
            pass
