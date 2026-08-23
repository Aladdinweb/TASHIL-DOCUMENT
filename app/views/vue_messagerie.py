# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — vue_messagerie.py
Centre de Messagerie: Boîte d'envoi / Boîte de réception / Pont Téléphone (QR).
"""

import os
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from app.utils.theme import get_palette, FONTS
from app.utils.database import get_connection, next_tracking_number, get_profile
from app.utils.archive_manager import archive_outgoing_file, list_archive
from app.utils.notifications import show_toast
from app.utils.phone_bridge import PhoneBridgeServer, get_qr_image, poll_new_uploads


class VueMessagerie(ctk.CTkFrame):
    def __init__(self, master, appearance_mode: str = "Dark"):
        pal = get_palette(appearance_mode)
        super().__init__(master, fg_color=pal["bg"])
        self.pal = pal
        self.appearance_mode = appearance_mode
        self.selected_file_path = None
        self.bridge_server = PhoneBridgeServer()
        self._qr_ctk_image = None

        ctk.CTkLabel(self, text="Centre de Messagerie", font=FONTS["title"],
                      text_color=pal["text"]).place(x=32, y=24)

        self.tabs = ctk.CTkTabview(self, width=880, height=560,
                                    fg_color=pal["card"], segmented_button_fg_color=pal["bg"],
                                    segmented_button_selected_color=pal["primary"])
        self.tabs.place(x=32, y=80)
        self.tabs.add("Boîte d'envoi")
        self.tabs.add("Boîte de réception")
        self.tabs.add("Pont Téléphone")

        self._build_envoi_tab()
        self._build_reception_tab()
        self._build_telephone_tab()

        self.bind("<Destroy>", lambda e: self._on_destroy())

    # ------------------------------------------------------------------ #
    # Envoi
    # ------------------------------------------------------------------ #
    def _build_envoi_tab(self):
        pal = self.pal
        tab = self.tabs.tab("Boîte d'envoi")

        drop_zone = ctk.CTkFrame(tab, fg_color=pal["input_bg"], corner_radius=12,
                                  border_width=2, border_color=pal["card_border"],
                                  height=100)
        drop_zone.pack(fill="x", padx=20, pady=(20, 10))
        self.file_label = ctk.CTkLabel(drop_zone, text="📎  Aucun fichier sélectionné",
                                        font=FONTS["body"], text_color=pal["text_muted"])
        self.file_label.pack(pady=30)
        drop_zone.bind("<Button-1>", lambda e: self._pick_file())
        self.file_label.bind("<Button-1>", lambda e: self._pick_file())

        ctk.CTkButton(tab, text="📁  Choisir un fichier", width=200, height=38,
                       fg_color=pal["primary"], command=self._pick_file
                       ).pack(padx=20, pady=(0, 16), anchor="w")

        ctk.CTkLabel(tab, text="Institution destinataire", font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(padx=20, anchor="w")
        self.recipient_entry = ctk.CTkEntry(tab, width=400, height=38,
                                             placeholder_text="ex: EPH AADL Ain Beida",
                                             fg_color=pal["input_bg"])
        self.recipient_entry.pack(padx=20, pady=(4, 12), anchor="w")

        ctk.CTkLabel(tab, text="Objet", font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(padx=20, anchor="w")
        self.subject_entry = ctk.CTkEntry(tab, width=400, height=38,
                                           fg_color=pal["input_bg"])
        self.subject_entry.pack(padx=20, pady=(4, 12), anchor="w")

        ctk.CTkLabel(tab, text="Message", font=FONTS["small"],
                      text_color=pal["text_muted"]).pack(padx=20, anchor="w")
        self.body_text = ctk.CTkTextbox(tab, width=800, height=100,
                                         fg_color=pal["input_bg"])
        self.body_text.pack(padx=20, pady=(4, 16), anchor="w")

        ctk.CTkButton(tab, text="📤  Envoyer", width=200, height=42,
                       font=FONTS["button"], fg_color=pal["success"],
                       command=self._send_message).pack(padx=20, anchor="w")

    def _pick_file(self):
        path = filedialog.askopenfilename(title="Sélectionner un document")
        if path:
            self.selected_file_path = path
            self.file_label.configure(text=f"📎  {os.path.basename(path)}")

    def _send_message(self):
        if not self.selected_file_path:
            messagebox.showwarning("TASHIL", "Veuillez sélectionner un fichier à transmettre.")
            return
        recipient = self.recipient_entry.get().strip()
        if not recipient:
            messagebox.showwarning("TASHIL", "Veuillez indiquer l'institution destinataire.")
            return

        archived_path = archive_outgoing_file(self.selected_file_path)
        profile = get_profile()
        sender = profile["institution_name"] if profile else "TASHIL"
        tracking = next_tracking_number("sortant")

        conn = get_connection()
        conn.execute("""
            INSERT INTO messages (direction, tracking_number, sender_institution,
                                   recipient_institution, subject, body, file_path,
                                   file_original_name, status, created_at)
            VALUES ('sortant', ?, ?, ?, ?, ?, ?, ?, 'envoye', ?)
        """, (tracking, sender, recipient, self.subject_entry.get().strip(),
              self.body_text.get("1.0", "end").strip(), archived_path,
              os.path.basename(self.selected_file_path), datetime.now().isoformat()))
        conn.execute("""
            INSERT INTO registre_courrier (tracking_number, type_courrier,
                                            institution_partenaire, objet, date_enregistrement)
            VALUES (?, 'sortant', ?, ?, ?)
        """, (tracking, recipient, self.subject_entry.get().strip(),
              datetime.now().isoformat()))
        conn.commit()

        show_toast(self, f"Document transmis — {tracking}", kind="success",
                    appearance_mode=self.appearance_mode)
        self.selected_file_path = None
        self.file_label.configure(text="📎  Aucun fichier sélectionné")
        self.recipient_entry.delete(0, "end")
        self.subject_entry.delete(0, "end")
        self.body_text.delete("1.0", "end")

    # ------------------------------------------------------------------ #
    # Réception
    # ------------------------------------------------------------------ #
    def _build_reception_tab(self):
        pal = self.pal
        tab = self.tabs.tab("Boîte de réception")

        self.inbox_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent",
                                                     width=840, height=480)
        self.inbox_scroll.pack(padx=10, pady=10, fill="both", expand=True)
        self._refresh_inbox()

        ctk.CTkButton(tab, text="🔄  Actualiser", width=160, height=34,
                       fg_color=pal["primary"], command=self._refresh_inbox
                       ).pack(pady=(0, 10))

    def _refresh_inbox(self):
        pal = self.pal
        for child in self.inbox_scroll.winfo_children():
            child.destroy()

        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM messages WHERE direction = 'entrant' ORDER BY created_at DESC"
        ).fetchall()

        if not rows:
            ctk.CTkLabel(self.inbox_scroll, text="Boîte de réception vide.",
                          font=FONTS["body"], text_color=pal["text_muted"]
                          ).pack(pady=20)
            return

        for row in rows:
            item = ctk.CTkFrame(self.inbox_scroll, fg_color=pal["card"], corner_radius=10,
                                 border_width=1, border_color=pal["card_border"])
            item.pack(fill="x", pady=6, padx=4)
            ctk.CTkLabel(item, text=f"📥 {row['tracking_number']} — {row['subject'] or '(sans objet)'}",
                          font=FONTS["body"], text_color=pal["text"]
                          ).pack(anchor="w", padx=14, pady=(10, 0))
            ctk.CTkLabel(item, text=f"De : {row['sender_institution']}",
                          font=FONTS["small"], text_color=pal["text_muted"]
                          ).pack(anchor="w", padx=14, pady=(0, 10))

    # ------------------------------------------------------------------ #
    # Pont Téléphone (QR Bridge)
    # ------------------------------------------------------------------ #
    def _build_telephone_tab(self):
        pal = self.pal
        tab = self.tabs.tab("Pont Téléphone")

        ctk.CTkLabel(tab, text="Scannez ce QR code avec votre téléphone pour transférer\n"
                                "un document sans câble (même réseau Wi-Fi requis).",
                      font=FONTS["body"], text_color=pal["text_muted"], justify="center"
                      ).pack(pady=(20, 10))

        self.qr_image_label = ctk.CTkLabel(tab, text="")
        self.qr_image_label.pack(pady=10)

        self.bridge_status_label = ctk.CTkLabel(tab, text="Pont désactivé",
                                                  font=FONTS["small"], text_color=pal["text_muted"])
        self.bridge_status_label.pack()

        self.bridge_toggle_btn = ctk.CTkButton(tab, text="▶️  Démarrer le Pont", width=220,
                                                height=40, fg_color=pal["primary"],
                                                command=self._toggle_bridge)
        self.bridge_toggle_btn.pack(pady=16)

        self._poll_queue_loop()

    def _toggle_bridge(self):
        pal = self.pal
        if self.bridge_server.is_running():
            self.bridge_server.stop()
            self.bridge_toggle_btn.configure(text="▶️  Démarrer le Pont")
            self.bridge_status_label.configure(text="Pont désactivé")
            self.qr_image_label.configure(image=None, text="")
            return

        self.bridge_server.start()
        url = self.bridge_server.url
        pil_img = get_qr_image(url).resize((220, 220), Image.NEAREST)
        self._qr_ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img,
                                           size=(220, 220))
        self.qr_image_label.configure(image=self._qr_ctk_image, text="")
        self.bridge_toggle_btn.configure(text="⏹️  Arrêter le Pont")
        self.bridge_status_label.configure(text=f"Pont actif : {url}", text_color=pal["success"])

    def _poll_queue_loop(self):
        if not self.winfo_exists():
            return
        if self.bridge_server.is_running():
            uploads = poll_new_uploads()
            for upload in uploads:
                show_toast(self, f"Reçu du téléphone : {upload['original_name']}",
                            kind="success", appearance_mode=self.appearance_mode)
        self.after(2500, self._poll_queue_loop)

    def _on_destroy(self):
        if self.bridge_server.is_running():
            self.bridge_server.stop()
