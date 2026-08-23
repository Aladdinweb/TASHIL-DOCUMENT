# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — main.py
Copyright ILINE TECH 2026 BY FERAK ALADDIN

Boot sequence:
  1. Install crash dump handler (tashil_boot_error.txt) BEFORE anything else.
  2. Initialize the SQLite database BEFORE ctk.CTk() is created
     (prevents the blank/black screen bug on launch).
  3. Show a splash screen (🇩🇿).
  4. Route to the onboarding wizard on first launch, otherwise straight
     to the main application shell.
"""

import os
import sys
import traceback

os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def _install_crash_handler():
    """Writes uncaught exceptions to tashil_boot_error.txt next to the exe."""
    base_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                                else os.path.abspath(__file__))
    dump_path = os.path.join(base_dir, "tashil_boot_error.txt")

    def _handle_exception(exc_type, exc_value, exc_tb):
        try:
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write("TASHIL DOCUMENT HUB — Crash Dump\n")
                f.write("=" * 50 + "\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        sys.exit(1)

    sys.excepthook = _handle_exception


_install_crash_handler()

import customtkinter as ctk  # noqa: E402  (import after crash handler is armed)

from app.config import APP_FLAG, APP_FULL_NAME  # noqa: E402
from app.utils.database import initialize_database, is_first_launch, get_profile  # noqa: E402
from app.utils.theme import get_palette, FONTS  # noqa: E402


class SplashScreen(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        pal = get_palette("Dark")
        self.overrideredirect(True)
        self.configure(fg_color=pal["bg"])
        self.attributes("-topmost", True)

        w, h = 420, 240
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        ctk.CTkLabel(self, text=APP_FLAG, font=(FONTS["title"][0], 48)
                      ).pack(pady=(40, 10))
        ctk.CTkLabel(self, text=APP_FULL_NAME, font=FONTS["title"],
                      text_color=pal["primary"]).pack()
        ctk.CTkLabel(self, text="Démarrage en cours...", font=FONTS["body"],
                      text_color=pal["text_muted"]).pack(pady=(6, 0))
        self.update()


class TashilRoot(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()  # Hide the real window until the splash finishes

        pal = get_palette("Dark")
        ctk.set_appearance_mode("Dark")
        self.title(APP_FULL_NAME)
        self.geometry("1180x720")
        self.minsize(980, 620)
        self.configure(fg_color=pal["bg"])

        try:
            icon_path = os.path.join(os.path.dirname(__file__), "app", "assets", "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        splash = SplashScreen(self)
        self.after(900, lambda: self._finish_boot(splash))

    def _finish_boot(self, splash: SplashScreen):
        splash.destroy()
        self.deiconify()

        if is_first_launch():
            self._launch_activation()
        else:
            self._launch_main_app()

    def _launch_activation(self):
        # Local import avoids a circular import with app_principale at module load time
        from app.views.vue_activation import VueActivation
        VueActivation(self, on_complete=self._launch_main_app)

    def _launch_main_app(self):
        for child in self.winfo_children():
            if hasattr(child, "destroy") and child.winfo_exists():
                child.destroy()
        from app.views.app_principale import AppPrincipale
        AppPrincipale(self)


def main():
    initialize_database()  # MUST run before ctk.CTk() is instantiated
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("green")
    app = TashilRoot()
    app.mainloop()


if __name__ == "__main__":
    main()
