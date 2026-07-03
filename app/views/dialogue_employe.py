# COPYRIGHT ILINE TECH 2026 BY FERAK ALADDIN
"""
Formulaire Employé TASHIL
Champs obligatoires : Nom, Prénom, Grade, Polyclinique
Soldes : sélecteur année explicite (pas auto année courante)
"""
import datetime
import customtkinter as ctk
from app.utils.theme import COULEURS, POLICES, DIMENSIONS
from app.utils.database import get_connection
from app.utils import employes_dao
from app.utils.polycliniques_dao import lister_polycliniques

try:
    from app.config import (
        SERVICES_CLINIQUES,
        HIERARCHIE_GRADES as GRADES,
        POSTES_PAR_GRADE,
    )
except Exception:
    SERVICES_CLINIQUES = ["Urgences", "Consultation", "Autre"]
    GRADES = ["Médecin", "Infirmier", "Ambulancier (OP)", "Autre"]
    POSTES_PAR_GRADE = {}


class DialogueEmploye(ctk.CTkToplevel):
    def __init__(self, parent, emp_id=None,
                 callback_succes=None):
        super().__init__(parent)
        self._emp_id   = emp_id
        self._callback = callback_succes
        self._polys    = lister_polycliniques()
        self._soldes_rows = []
        self._donnees  = (
            employes_dao.obtenir_employe(emp_id)
            if emp_id else None)

        titre = ("✏  Modifier employé"
                 if emp_id else
                 "＋  Nouvel employé")
        self.title(titre)
        self.configure(
            fg_color=COULEURS["bg_principal"])
        self.resizable(False, True)
        self.grab_set()
        self.focus_set()

        w = 580
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = 60
        self.geometry(f"{w}x780+{x}+{y}")

        self._construire()

    def _construire(self):
        # Scroll global
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COULEURS["accent_bleu"])
        scroll.pack(fill="both", expand=True)

        pad = 20

        def sep(texte, couleur=None):
            c = couleur or COULEURS["accent_bleu"]
            f = ctk.CTkFrame(
                scroll, fg_color="transparent")
            f.pack(fill="x", padx=pad,
                   pady=(16, 4))
            ctk.CTkLabel(
                f, text=texte,
                font=POLICES["sous_titre"],
                text_color=c
            ).pack(side="left")
            ctk.CTkFrame(
                f, height=1,
                fg_color=COULEURS["bordure"]
            ).pack(side="left", fill="x",
                   expand=True, padx=(8, 0))

        def champ(label, ph="", req=False):
            f = ctk.CTkFrame(
                scroll, fg_color="transparent")
            f.pack(fill="x", padx=pad,
                   pady=(0, 8))
            ctk.CTkLabel(
                f,
                text=label + (" *" if req else ""),
                font=POLICES["corps_bold"],
                text_color=COULEURS["texte_secondaire"]
            ).pack(anchor="w")
            e = ctk.CTkEntry(
                f, placeholder_text=ph,
                fg_color=COULEURS["bg_champ"],
                border_color=COULEURS["bordure"],
                text_color=COULEURS["texte_principal"],
                placeholder_text_color=COULEURS["texte_discret"],
                font=POLICES["corps"],
                height=36,
                corner_radius=DIMENSIONS["rayon_bouton"])
            e.pack(fill="x", pady=(4, 0))
            return e

        def menu_opt(label, vals, req=False,
                     cmd=None, w=None):
            f = ctk.CTkFrame(
                scroll, fg_color="transparent")
            f.pack(fill="x", padx=pad,
                   pady=(0, 8))
            ctk.CTkLabel(
                f,
                text=label + (" *" if req else ""),
                font=POLICES["corps_bold"],
                text_color=COULEURS["texte_secondaire"]
            ).pack(anchor="w")
            kw = dict(
                fg_color=COULEURS["bg_champ"],
                button_color=COULEURS["accent_bleu"],
                button_hover_color=COULEURS["accent_bleu_clair"],
                dropdown_fg_color=COULEURS["bg_carte"],
                dropdown_hover_color=COULEURS["bg_hover"],
                text_color=COULEURS["texte_principal"],
                dropdown_text_color=COULEURS["texte_principal"],
                font=POLICES["corps"],
                dropdown_font=POLICES["corps"],
                corner_radius=DIMENSIONS["rayon_bouton"],
                height=36)
            if w:
                kw["width"] = w
            if cmd:
                kw["command"] = cmd
            m = ctk.CTkOptionMenu(f, values=vals, **kw)
            m.pack(fill="x", pady=(4, 0))
            return m

        # ── Section 1 : Identification ────────
        sep("① Identification")
        self.e_nom      = champ(
            "Nom", "BENSALEM", req=True)
        self.e_prenom   = champ(
            "Prénom", "Kamel", req=True)
        self.e_matricule = champ(
            "Matricule", "Ex : MR-001  (optionnel)")

        # ── Section 2 : Affectation ───────────
        sep("② Affectation")
        noms_polys = (
            ["— Sélectionner —"] +
            [p["nom"] for p in self._polys])
        self.m_poly = menu_opt(
            "Polyclinique", noms_polys, req=True)

        self.m_service = menu_opt(
            "Service clinique",
            SERVICES_CLINIQUES)

        # ── Section 3 : Grade & Poste ─────────
        sep("③ Grade & Poste")
        self.m_grade = menu_opt(
            "Grade / Corps", GRADES, req=True,
            cmd=self._on_grade_change)

        # Poste dynamique
        f_poste = ctk.CTkFrame(
            scroll, fg_color="transparent")
        f_poste.pack(fill="x", padx=pad,
                     pady=(0, 8))
        ctk.CTkLabel(
            f_poste, text="Poste occupé",
            font=POLICES["corps_bold"],
            text_color=COULEURS["texte_secondaire"]
        ).pack(anchor="w")
        self._frame_poste = ctk.CTkFrame(
            f_poste, fg_color="transparent")
        self._frame_poste.pack(
            fill="x", pady=(4, 0))

        self.m_poste = ctk.CTkOptionMenu(
            self._frame_poste,
            values=["Poste principal"],
            fg_color=COULEURS["bg_champ"],
            button_color=COULEURS["accent_bleu"],
            button_hover_color=COULEURS["accent_bleu_clair"],
            dropdown_fg_color=COULEURS["bg_carte"],
            dropdown_hover_color=COULEURS["bg_hover"],
            text_color=COULEURS["texte_principal"],
            dropdown_text_color=COULEURS["texte_principal"],
            font=POLICES["corps"],
            corner_radius=DIMENSIONS["rayon_bouton"],
            height=36)
        self.m_poste.pack(fill="x")

        self.e_poste_libre = ctk.CTkEntry(
            self._frame_poste,
            placeholder_text="Saisir le poste…",
            fg_color=COULEURS["bg_champ"],
            border_color=COULEURS["bordure"],
            text_color=COULEURS["texte_principal"],
            placeholder_text_color=COULEURS["texte_discret"],
            font=POLICES["corps"], height=36,
            corner_radius=DIMENSIONS["rayon_bouton"])

        self._poste_mode = "menu"
        self._on_grade_change(GRADES[0])

        # ── Section 4 : Soldes initiaux ───────
        if not self._emp_id:
            sep("④ Soldes de congé initiaux",
                couleur=COULEURS["accent_vert"])

            ctk.CTkLabel(
                scroll,
                text="Saisissez uniquement le nombre "
                     "de jours RESTANTS par année.\n"
                     "Choisissez l'année dans le "
                     "menu déroulant.",
                font=POLICES["petit"],
                text_color=COULEURS["texte_secondaire"],
                wraplength=520, justify="left"
            ).pack(anchor="w", padx=pad,
                   pady=(0, 8))

            self._frame_soldes = ctk.CTkFrame(
                scroll,
                fg_color=COULEURS["bg_carte"],
                corner_radius=8)
            self._frame_soldes.pack(
                fill="x", padx=pad,
                pady=(0, 6))

            ctk.CTkLabel(
                self._frame_soldes,
                text="Aucune année ajoutée.",
                font=POLICES["corps"],
                text_color=COULEURS["texte_discret"]
            ).pack(pady=16)

            # Bouton ajouter une année
            # avec SÉLECTEUR d'année explicite
            f_add = ctk.CTkFrame(
                scroll, fg_color="transparent")
            f_add.pack(fill="x", padx=pad,
                       pady=(0, 12))

            annee_cour = datetime.date.today().year
            self._annees_dispo = [
                str(a) for a in range(
                    annee_cour, annee_cour - 15, -1)]
            self._annee_select = ctk.CTkOptionMenu(
                f_add,
                values=self._annees_dispo,
                width=120, height=32,
                fg_color=COULEURS["bg_champ"],
                button_color=COULEURS["accent_bleu"],
                button_hover_color=COULEURS["accent_bleu_clair"],
                dropdown_fg_color=COULEURS["bg_carte"],
                dropdown_hover_color=COULEURS["bg_hover"],
                text_color=COULEURS["texte_principal"],
                dropdown_text_color=COULEURS["texte_principal"],
                font=POLICES["corps"],
                corner_radius=6)
            self._annee_select.pack(
                side="left", padx=(0, 8))
            self._annee_select.set(
                str(annee_cour))

            ctk.CTkButton(
                f_add,
                text="＋  Ajouter cette année",
                height=32,
                fg_color=COULEURS["bg_champ"],
                hover_color=COULEURS["bg_hover"],
                text_color=COULEURS["texte_secondaire"],
                font=POLICES["corps"],
                corner_radius=DIMENSIONS["rayon_bouton"],
                command=self._ajouter_annee_selectee
            ).pack(side="left")

        # Label erreur
        self.lbl_err = ctk.CTkLabel(
            scroll, text="",
            font=POLICES["corps"],
            text_color=COULEURS["accent_rouge"])
        self.lbl_err.pack(padx=pad,
                          pady=(4, 4))

        # Pied boutons
        f_pied = ctk.CTkFrame(
            self,
            fg_color=COULEURS["bg_sidebar"],
            corner_radius=0, height=58)
        f_pied.pack(fill="x", side="bottom")
        f_pied.pack_propagate(False)

        ctk.CTkButton(
            f_pied, text="✕  Annuler",
            fg_color=COULEURS["bg_champ"],
            hover_color=COULEURS["accent_rouge"],
            text_color=COULEURS["texte_secondaire"],
            font=POLICES["bouton"],
            height=36, width=120,
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self.destroy
        ).pack(side="right", padx=(6, 16),
               pady=11)

        ctk.CTkButton(
            f_pied, text="💾  Enregistrer",
            fg_color=COULEURS["accent_bleu"],
            hover_color=COULEURS["accent_bleu_clair"],
            text_color="#FFFFFF",
            font=POLICES["bouton"],
            height=36, width=160,
            corner_radius=DIMENSIONS["rayon_bouton"],
            command=self._valider
        ).pack(side="right", padx=4, pady=11)

        if self._donnees:
            self._preremplir()

    def _ajouter_annee_selectee(self):
        """Ajoute la ligne solde pour l'année choisie."""
        annee_str = self._annee_select.get()
        try:
            annee = int(annee_str)
        except ValueError:
            return

        # Vérifier si déjà ajoutée
        for row in self._soldes_rows:
            if row[0] == annee:
                self.lbl_err.configure(
                    text=f"L'année {annee} "
                         "est déjà ajoutée.")
                return
        self.lbl_err.configure(text="")

        # Supprimer label "Aucune année"
        for w in self._frame_soldes.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        annee_cour = datetime.date.today().year
        is_old = annee < annee_cour

        f = ctk.CTkFrame(
            self._frame_soldes,
            fg_color="transparent")
        f.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(
            f,
            text=f"{'🔴' if is_old else '✅'} "
                 f"{annee} :",
            font=POLICES["corps_bold"],
            text_color=(COULEURS["accent_orange"]
                        if is_old
                        else COULEURS["accent_vert"]),
            width=80, anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            f, text="Jours restants :",
            font=POLICES["petit"],
            text_color=COULEURS["texte_secondaire"]
        ).pack(side="left", padx=(8, 4))

        e = ctk.CTkEntry(
            f, width=80,
            fg_color=COULEURS["bg_champ"],
            border_color=COULEURS["bordure"],
            text_color=COULEURS["texte_principal"],
            font=POLICES["corps"],
            height=30,
            corner_radius=DIMENSIONS["rayon_bouton"])
        e.insert(0, "30")
        e.pack(side="left")

        row_ref = [annee, e]
        self._soldes_rows.append(row_ref)

        def _suppr(frame=f, row=row_ref):
            frame.destroy()
            if row in self._soldes_rows:
                self._soldes_rows.remove(row)
            if not self._soldes_rows:
                ctk.CTkLabel(
                    self._frame_soldes,
                    text="Aucune année ajoutée.",
                    font=POLICES["corps"],
                    text_color=COULEURS["texte_discret"]
                ).pack(pady=16)

        ctk.CTkButton(
            f, text="✕",
            fg_color="transparent",
            hover_color=COULEURS["accent_rouge"],
            text_color=COULEURS["texte_discret"],
            width=26, height=26,
            corner_radius=4,
            command=_suppr
        ).pack(side="left", padx=(6, 0))

    def _on_grade_change(self, grade: str):
        for w in self._frame_poste.winfo_children():
            w.pack_forget()
        postes = POSTES_PAR_GRADE.get(grade)
        if postes:
            self.m_poste.configure(values=postes)
            self.m_poste.set(postes[0])
            self.m_poste.pack(fill="x")
            self._poste_mode = "menu"
        else:
            self.e_poste_libre.pack(fill="x")
            self._poste_mode = "libre"

    def _get_poste(self) -> str:
        if self._poste_mode == "menu":
            return self.m_poste.get()
        return self.e_poste_libre.get().strip()

    def _preremplir(self):
        d = self._donnees
        self.e_nom.insert(0, d.get("nom", ""))
        self.e_prenom.insert(0, d.get("prenom", ""))
        if d.get("matricule"):
            self.e_matricule.insert(
                0, d["matricule"])
        for p in self._polys:
            if p["id"] == d.get("polyclinique_id"):
                self.m_poly.set(p["nom"])
                break
        if d.get("grade") in GRADES:
            self.m_grade.set(d["grade"])
            self._on_grade_change(d["grade"])

    def _resoudre_dept(self, service: str) -> int:
        conn = get_connection()
        code = (service[:12].upper()
                .replace(" ", "_")
                .replace("/", "_"))
        row = conn.execute(
            "SELECT id FROM departements "
            "WHERE code=?", (code,)).fetchone()
        if row:
            conn.close()
            return row["id"]
        cur = conn.execute(
            "INSERT OR IGNORE INTO departements "
            "(code, nom) VALUES (?,?)",
            (code, service))
        conn.commit()
        rid = (cur.lastrowid or conn.execute(
            "SELECT id FROM departements "
            "WHERE code=?",
            (code,)).fetchone()["id"])
        conn.close()
        return rid

    def _valider(self):
        self.lbl_err.configure(text="")

        nom    = self.e_nom.get().strip().upper()
        prenom = self.e_prenom.get().strip()
        grade  = self.m_grade.get()
        poly_s = self.m_poly.get()

        if not nom:
            self.lbl_err.configure(
                text="Nom obligatoire.")
            return
        if not prenom:
            self.lbl_err.configure(
                text="Prénom obligatoire.")
            return
        if "Sélectionner" in poly_s:
            self.lbl_err.configure(
                text="Polyclinique obligatoire.")
            return

        mat = (self.e_matricule.get()
               .strip().upper())
        if (mat and
                employes_dao.matricule_existe(
                    mat,
                    exclure_id=self._emp_id)):
            self.lbl_err.configure(
                text=f"Matricule «{mat}» "
                     "déjà utilisé.")
            return

        poly_id = next(
            (p["id"] for p in self._polys
             if p["nom"] == poly_s), None)

        svc = (self.m_service.get()
               if hasattr(self, "m_service")
               else "Autre")
        dept_id = self._resoudre_dept(svc)

        data = {
            "matricule":       mat or "",
            "nom":             nom,
            "prenom":          prenom,
            "grade":           grade,
            "poste":           self._get_poste(),
            "departement_id":  dept_id,
            "polyclinique_id": poly_id,
            "est_manip_radio": (
                1 if "Radio" in grade else 0),
            "actif": True,
        }

        try:
            if self._emp_id:
                employes_dao.modifier_employe(
                    self._emp_id, data)
                res = {"action": "modifie"}
            else:
                nid = self._creer_avec_soldes(data)
                res = {"action": "cree",
                       "id": nid}

            if self._callback:
                self._callback(res)
            self.destroy()

        except Exception as ex:
            self.lbl_err.configure(
                text=f"Erreur : {ex}")

    def _creer_avec_soldes(self, data) -> int:
        conn = get_connection()
        cur = conn.execute("""
            INSERT INTO employes
                (matricule, nom, prenom, grade,
                 poste, departement_id,
                 polyclinique_id, est_manip_radio,
                 actif)
            VALUES (?,?,?,?,?,?,?,?,1)
        """, (
            data["matricule"], data["nom"],
            data["prenom"], data["grade"],
            data["poste"], data["departement_id"],
            data.get("polyclinique_id"),
            data.get("est_manip_radio", 0),
        ))
        emp_id = cur.lastrowid

        for row in self._soldes_rows:
            annee, e_restant = row
            try:
                restant = max(0.0, float(
                    e_restant.get().strip() or "0"))
            except ValueError:
                restant = 0.0
            if restant > 0:
                conn.execute("""
                    INSERT OR IGNORE INTO
                    conges_annuels
                        (employe_id, annee,
                         jours_initiaux,
                         jours_utilises)
                    VALUES (?,?,?,0)
                """, (emp_id, annee, restant))

        if not self._soldes_rows:
            annee = datetime.date.today().year
            conn.execute("""
                INSERT OR IGNORE INTO
                conges_annuels
                    (employe_id, annee,
                     jours_initiaux,
                     jours_utilises)
                VALUES (?,?,30,0)
            """, (emp_id, annee))

        conn.commit()
        conn.close()
        return emp_id
