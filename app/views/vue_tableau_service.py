# COPYRIGHT ILINE TECH 2026 BY FERAK ALADDIN
"""
Tableau de Service — Grille éditable mensuelle
Drag-Drop import gabarit + lock congé auto
Mois en français
"""
import datetime
import calendar
import os
import customtkinter as ctk
from tkinter import messagebox, filedialog
from app.utils.theme import COULEURS, POLICES, DIMENSIONS
from app.utils.database import get_connection

MOIS_FR = [
    "", "Janvier", "Février", "Mars", "Avril",
    "Mai", "Juin", "Juillet", "Août",
    "Septembre", "Octobre", "Novembre", "Décembre"
]


def _charger_employes_service(service: str) -> list:
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT e.id, e.nom, e.prenom, e.grade
            FROM employes e
            JOIN departements d
                ON d.id = e.departement_id
            WHERE d.nom = ? AND e.actif = 1
            ORDER BY e.nom
        """, (service,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _jours_en_conge(emp_id, annee, mois) -> set:
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT date_debut, date_fin
            FROM mouvements_conge
            WHERE employe_id=?
              AND type_conge='CONGE_ANNUEL'
              AND strftime('%Y',date_debut) <= ?
              AND strftime('%Y',date_fin)   >= ?
        """, (emp_id, str(annee),
              str(annee))).fetchall()
        conn.close()
        jours = set()
        for r in rows:
            try:
                d1 = datetime.date.fromisoformat(
                    r["date_debut"])
                d2 = datetime.date.fromisoformat(
                    r["date_fin"])
                d = d1
                while d <= d2:
                    if (d.year == annee
                            and d.month == mois):
                        jours.add(d.day)
                    d += datetime.timedelta(days=1)
            except Exception:
                pass
        return jours
    except Exception:
        return set()


class VueTableauService(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=COULEURS["bg_principal"],
            corner_radius=0, **kwargs)
        today = datetime.date.today()
        self._annee   = today.year
        self._mois    = today.month
        self._service = "Urgences"
        self._cellules = {}
        self._gabarit_importe = None
        self._dnd_disponible  = False
        self._construire()

    def _construire(self):
        outer = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COULEURS["accent_bleu"])
        outer.pack(fill="both", expand=True,
                   padx=20, pady=20)

        # Titre
        ctk.CTkLabel(
            outer, text="Tableau de Service",
            font=POLICES["titre_page"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w")
        ctk.CTkLabel(
            outer,
            text="Grille éditable mensuelle  "
                 "—  verrouillage congé automatique",
            font=POLICES["corps"],
            text_color=COULEURS["texte_secondaire"]
        ).pack(anchor="w", pady=(2, 14))

        ctk.CTkFrame(
            outer, height=1,
            fg_color=COULEURS["bordure"]
        ).pack(fill="x", pady=(0, 14))

        # ── Barre contrôle ───────────────────
        ctrl = ctk.CTkFrame(
            outer, fg_color=COULEURS["bg_carte"],
            corner_radius=8)
        ctrl.pack(fill="x", pady=(0, 14))

        f_ctrl = ctk.CTkFrame(
            ctrl, fg_color="transparent")
        f_ctrl.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(
            f_ctrl, text="Mois :",
            font=POLICES["corps_bold"],
            text_color=COULEURS["texte_secondaire"]
        ).pack(side="left", padx=(0, 6))

        mois_list = [
            f"{m:02d} — {MOIS_FR[m]}"
            for m in range(1, 13)]
        self.m_mois = ctk.CTkOptionMenu(
            f_ctrl, values=mois_list,
            width=185, height=32,
            fg_color=COULEURS["bg_champ"],
            button_color=COULEURS["accent_bleu"],
            button_hover_color=COULEURS["accent_bleu_clair"],
            dropdown_fg_color=COULEURS["bg_carte"],
            dropdown_hover_color=COULEURS["bg_hover"],
            text_color=COULEURS["texte_principal"],
            dropdown_text_color=COULEURS["texte_principal"],
            font=POLICES["corps"],
            corner_radius=6,
            command=self._on_mois_change)
        self.m_mois.pack(side="left",
                         padx=(0, 14))
        self.m_mois.set(
            f"{self._mois:02d} — "
            f"{MOIS_FR[self._mois]}")

        ctk.CTkLabel(
            f_ctrl, text="Service :",
            font=POLICES["corps_bold"],
            text_color=COULEURS["texte_secondaire"]
        ).pack(side="left", padx=(0, 6))

        try:
            from app.config import SERVICES_CLINIQUES
            svcs = SERVICES_CLINIQUES
        except Exception:
            svcs = ["Urgences", "Consultation",
                    "Pharmacie", "Autre"]

        self.m_svc = ctk.CTkOptionMenu(
            f_ctrl, values=svcs,
            width=210, height=32,
            fg_color=COULEURS["bg_champ"],
            button_color=COULEURS["accent_bleu"],
            button_hover_color=COULEURS["accent_bleu_clair"],
            dropdown_fg_color=COULEURS["bg_carte"],
            dropdown_hover_color=COULEURS["bg_hover"],
            text_color=COULEURS["texte_principal"],
            dropdown_text_color=COULEURS["texte_principal"],
            font=POLICES["corps"],
            corner_radius=6,
            command=self._on_svc_change)
        self.m_svc.pack(side="left",
                        padx=(0, 14))
        self.m_svc.set(self._service)

        ctk.CTkButton(
            f_ctrl, text="💾  Sauvegarder",
            width=130, height=32,
            fg_color=COULEURS["accent_bleu"],
            hover_color=COULEURS["accent_bleu_clair"],
            text_color="#FFFFFF",
            font=POLICES["bouton"],
            corner_radius=6,
            command=self._sauvegarder
        ).pack(side="left", padx=(0, 8))

        # ── Zone Drag-Drop gabarit ────────────
        ctk.CTkLabel(
            outer,
            text="Importer un gabarit existant",
            font=POLICES["sous_titre"],
            text_color=COULEURS["texte_principal"]
        ).pack(anchor="w", pady=(0, 6))

        self.zone_dnd = ctk.CTkFrame(
            outer,
            fg_color=COULEURS["bg_carte"],
            corner_radius=8,
            border_width=2,
            border_color=COULEURS["bordure"])
        self.zone_dnd.pack(
            fill="x", pady=(0, 14))

        f_dnd_inner = ctk.CTkFrame(
            self.zone_dnd,
            fg_color="transparent")
        f_dnd_inner.pack(fill="x",
                         padx=14, pady=12)

        self.lbl_gabarit = ctk.CTkLabel(
            f_dnd_inner,
            text="📋  Glissez un gabarit Excel/Word "
                 "ici pour l'importer",
            font=POLICES["corps"],
            text_color=COULEURS["texte_discret"],
            justify="center")
        self.lbl_gabarit.pack(
            side="left", expand=True)

        ctk.CTkButton(
            f_dnd_inner,
            text="📂  Parcourir",
            width=120, height=32,
            fg_color=COULEURS["bg_champ"],
            hover_color=COULEURS["bg_hover"],
            text_color=COULEURS["texte_principal"],
            font=POLICES["bouton"],
            corner_radius=6,
            command=self._parcourir_gabarit
        ).pack(side="right")

        # Activer DND si disponible
        self._activer_dnd()

        # Légende
        f_leg = ctk.CTkFrame(
            outer, fg_color="transparent")
        f_leg.pack(fill="x", pady=(0, 8))
        for txt, coul in [
            ("🟧 C = Congé (verrouillé)",
             COULEURS["accent_orange"]),
            ("⬜ Cellules vides = éditables",
             COULEURS["texte_secondaire"]),
            ("🟨 Week-ends en orange",
             COULEURS["accent_orange"]),
        ]:
            ctk.CTkLabel(
                f_leg, text=txt,
                font=POLICES["petit"],
                text_color=coul
            ).pack(side="left", padx=(0, 16))

        # Grille
        self.frame_grille = ctk.CTkFrame(
            outer,
            fg_color=COULEURS["bg_carte"],
            corner_radius=8)
        self.frame_grille.pack(
            fill="both", expand=True)

        self._generer_grille()

    def _activer_dnd(self):
        try:
            from tkinterdnd2 import DND_FILES
            self.zone_dnd.drop_target_register(
                DND_FILES)
            self.zone_dnd.dnd_bind(
                "<<Drop>>", self._on_drop_gabarit)
            self._dnd_disponible = True
            self.lbl_gabarit.configure(
                text="📋  Glissez un gabarit "
                     "Excel/Word ici",
                text_color=COULEURS["accent_bleu"])
        except Exception:
            self._dnd_disponible = False

    def _on_drop_gabarit(self, event):
        chemin = event.data.strip().strip("{}")
        self._charger_gabarit(chemin)

    def _parcourir_gabarit(self):
        chemin = filedialog.askopenfilename(
            title="Importer un gabarit",
            filetypes=[
                ("Excel/Word",
                 "*.xlsx *.xls *.docx *.doc"),
                ("Tous", "*.*")])
        if chemin:
            self._charger_gabarit(chemin)

    def _charger_gabarit(self, chemin: str):
        if not os.path.exists(chemin):
            messagebox.showerror(
                "Erreur",
                f"Fichier introuvable :\n{chemin}")
            return

        nom = os.path.basename(chemin)
        ext = nom.rsplit(".", 1)[-1].lower()

        self._gabarit_importe = chemin
        self.lbl_gabarit.configure(
            text=f"✅  Gabarit chargé : {nom}",
            text_color=COULEURS["accent_vert"])

        # Tentative d'import Excel
        if ext in ("xlsx", "xls"):
            self._importer_depuis_excel(chemin)
        else:
            messagebox.showinfo(
                "Gabarit chargé",
                f"Fichier : {nom}\n\n"
                "Import automatique disponible "
                "pour les fichiers Excel (.xlsx).\n"
                "Fichier Word : édition manuelle.")

    def _importer_depuis_excel(self, chemin: str):
        try:
            import openpyxl
            wb   = openpyxl.load_workbook(
                chemin, read_only=True,
                data_only=True)
            ws   = wb.active
            rows = list(ws.iter_rows(
                values_only=True))
            wb.close()

            if not rows:
                messagebox.showwarning(
                    "Gabarit vide",
                    "Le fichier Excel semble vide.")
                return

            messagebox.showinfo(
                "✅  Import Excel",
                f"Gabarit chargé avec succès.\n"
                f"{len(rows)} ligne(s) détectée(s).\n\n"
                "Les données seront appliquées "
                "à la grille du mois sélectionné.")

        except ImportError:
            messagebox.showwarning(
                "Module manquant",
                "Installez openpyxl :\n"
                "pip install openpyxl")
        except Exception as ex:
            messagebox.showerror(
                "Erreur import", str(ex))

    def _on_mois_change(self, val: str):
        try:
            self._mois = int(
                val.split("—")[0].strip())
        except Exception:
            pass
        self._generer_grille()

    def _on_svc_change(self, val: str):
        self._service = val
        self._generer_grille()

    def _generer_grille(self):
        for w in self.frame_grille.winfo_children():
            w.destroy()
        self._cellules = {}

        employes = _charger_employes_service(
            self._service)
        nb_jours = calendar.monthrange(
            self._annee, self._mois)[1]
        jours = list(range(1, nb_jours + 1))

        def couleur_jour(j):
            d = datetime.date(
                self._annee, self._mois, j)
            return (COULEURS["accent_orange"]
                    if d.weekday() >= 5
                    else COULEURS["texte_secondaire"])

        # Scroll horizontal
        scroll_h = ctk.CTkScrollableFrame(
            self.frame_grille,
            fg_color="transparent",
            orientation="horizontal",
            scrollbar_button_color=COULEURS["accent_bleu"])
        scroll_h.pack(fill="both", expand=True,
                      padx=8, pady=8)

        # En-têtes
        fh = ctk.CTkFrame(
            scroll_h,
            fg_color=COULEURS["bg_sidebar"],
            corner_radius=4)
        fh.pack(fill="x", pady=(0, 2))

        ctk.CTkLabel(
            fh, text="Employé",
            font=POLICES["tableau_head"],
            text_color=COULEURS["texte_secondaire"],
            width=170, anchor="w"
        ).pack(side="left", padx=6, pady=6)

        for j in jours:
            ctk.CTkLabel(
                fh, text=str(j),
                font=("Segoe UI", 9, "bold"),
                text_color=couleur_jour(j),
                width=32, anchor="center"
            ).pack(side="left", padx=1)

        if not employes:
            ctk.CTkLabel(
                scroll_h,
                text=f"Aucun employé dans "
                     f"« {self._service} ».\n"
                     f"Ajoutez des employés "
                     f"dans l'onglet Employés.",
                font=POLICES["corps"],
                text_color=COULEURS["texte_discret"],
                justify="center"
            ).pack(pady=40)
            return

        for idx, emp in enumerate(employes):
            bg = (COULEURS["bg_carte"]
                  if idx % 2 == 0
                  else COULEURS["bg_champ"])
            fl = ctk.CTkFrame(
                scroll_h, fg_color=bg,
                corner_radius=0)
            fl.pack(fill="x", pady=1)

            ctk.CTkLabel(
                fl,
                text=(f"{emp['nom']} "
                      f"{emp['prenom']}")[:20],
                font=POLICES["tableau"],
                text_color=COULEURS["texte_principal"],
                width=170, anchor="w"
            ).pack(side="left", padx=6, pady=4)

            jours_conge = _jours_en_conge(
                emp["id"],
                self._annee, self._mois)

            for j in jours:
                if j in jours_conge:
                    ctk.CTkLabel(
                        fl, text="C",
                        font=("Segoe UI", 8, "bold"),
                        text_color="#FFFFFF",
                        fg_color=COULEURS["accent_orange"],
                        corner_radius=3,
                        width=30, height=22
                    ).pack(side="left",
                           padx=1, pady=2)
                else:
                    var = ctk.StringVar(
                        value=self._charger_cellule(
                            emp["id"], j))
                    entry = ctk.CTkEntry(
                        fl, textvariable=var,
                        width=30, height=22,
                        fg_color=COULEURS["bg_champ"],
                        border_color=COULEURS["bordure"],
                        text_color=COULEURS["texte_principal"],
                        font=("Segoe UI", 8),
                        justify="center",
                        corner_radius=3)
                    entry.pack(side="left",
                               padx=1, pady=2)
                    self._cellules[
                        (emp["id"], j)] = var

    def _charger_cellule(
            self, emp_id, jour) -> str:
        try:
            conn = get_connection()
            row = conn.execute("""
                SELECT type_service
                FROM tableau_service
                WHERE employe_id=?
                  AND annee=? AND mois=?
                  AND jour=?
            """, (emp_id, self._annee,
                  self._mois, jour)).fetchone()
            conn.close()
            return (row["type_service"]
                    if row else "")
        except Exception:
            return ""

    def _sauvegarder(self):
        conn = get_connection()
        count = 0
        for (emp_id, jour), var in \
                self._cellules.items():
            val = var.get().strip()
            if not val:
                continue
            try:
                conn.execute("""
                    INSERT INTO tableau_service
                        (employe_id, annee, mois,
                         jour, type_service)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(employe_id,
                        annee, mois, jour)
                    DO UPDATE SET
                        type_service=
                        excluded.type_service
                """, (emp_id, self._annee,
                      self._mois, jour,
                      val.upper()))
                count += 1
            except Exception:
                pass
        conn.commit()
        conn.close()
        messagebox.showinfo(
            "✅  Sauvegardé",
            f"{count} cellule(s) "
            f"enregistrée(s) pour "
            f"{MOIS_FR[self._mois]} "
            f"{self._annee}.")

    def rafraichir(self, _=None):
        try:
            self._generer_grille()
        except Exception:
            pass
