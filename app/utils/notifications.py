# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — notifications.py
Lightweight in-app toast overlay + optional system sound.
"""

import threading
import winsound  # Windows-only; guarded for non-Windows dev/test environments
import customtkinter as ctk

from app.utils.theme import get_palette, FONTS


class Toast(ctk.CTkToplevel):
    """A transient, auto-dismissing toast notification anchored to bottom-right."""

    def __init__(self, master, message: str, kind: str = "info",
                 appearance_mode: str = "Dark", duration_ms: int = 3200,
                 play_sound: bool = True):
        super().__init__(master)
        pal = get_palette(appearance_mode)
        colors = {
            "success": pal["success"],
            "warning": pal["warning"],
            "danger": pal["danger"],
            "info": pal["primary"],
        }
        border = colors.get(kind, pal["primary"])

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=pal["card"])

        frame = ctk.CTkFrame(self, fg_color=pal["card"], border_color=border,
                              border_width=2, corner_radius=10)
        frame.pack(fill="both", expand=True)

        icon = {"success": "✅", "warning": "⚠️", "danger": "⛔", "info": "ℹ️"}.get(kind, "ℹ️")
        label = ctk.CTkLabel(frame, text=f"{icon}  {message}", font=FONTS["body"],
                              text_color=pal["text"], wraplength=320, justify="left")
        label.pack(padx=16, pady=12)

        self.update_idletasks()
        self._position_bottom_right()

        if play_sound:
            threading.Thread(target=self._play_sound, args=(kind,), daemon=True).start()

        self.after(duration_ms, self.destroy)

    def _position_bottom_right(self):
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = sw - w - 24
        y = sh - h - 70
        self.geometry(f"{w}x{h}+{x}+{y}")

    @staticmethod
    def _play_sound(kind: str):
        try:
            sound_map = {
                "success": winsound.MB_ICONASTERISK,
                "warning": winsound.MB_ICONEXCLAMATION,
                "danger": winsound.MB_ICONHAND,
                "info": winsound.MB_OK,
            }
            winsound.MessageBeep(sound_map.get(kind, winsound.MB_OK))
        except Exception:
            pass  # Non-Windows environment or audio device unavailable


def show_toast(master, message: str, kind: str = "info",
                appearance_mode: str = "Dark", play_sound: bool = True):
    """Convenience wrapper to spawn a Toast on the Tk main thread."""
    master.after(0, lambda: Toast(master, message, kind, appearance_mode,
                                   play_sound=play_sound))
