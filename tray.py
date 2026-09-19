# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — tray.py
Copyright ILINE TECH 2026 BY FERAK ALADDIN

v2.8.4 — Optional Windows system-tray integration: minimize-to-tray
instead of exiting when the window is closed, a red unread-count badge
drawn directly onto the tray icon, and a toast notification when new
messages arrive while the window is hidden.

⚠️ HONESTY NOTE — read before trusting this module:
This code was written and unit-tested for its PURE LOGIC only — badge
image composition (Pillow, verified by actually rendering and inspecting
output images) and the unread-count polling logic (verified against the
real /api/messages/unread-count endpoint via the Flask test client). It
was developed in a Linux sandbox with NO Windows GUI available, so the
following have NOT been confirmed and need a real test on the Windows
build before this is trusted the way the rest of this project's fixes
have been:
  - Does the tray icon actually appear next to the Windows clock?
  - Does left-clicking it actually restore/focus the window?
  - Does the badge remain legible at the real, very small tray-icon size
    (Windows typically renders these at 16–24px)?
  - Does plyer's notify() actually produce a real Windows 10/11 toast
    (plyer picks a backend per OS at import time; its Windows backend
    has its own dependencies that could fail the same way
    opencv-python-headless and pywebview once did in this exact project)?
This module degrades to a complete no-op if pystray or plyer are
missing, or if anything inside it raises — the desktop app MUST keep
working exactly as it did in v2.8.3 (server up, native window opens,
closing the window exits normally) with or without this feature.
"""

import threading

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    _TRAY_AVAILABLE = True
except Exception:
    _TRAY_AVAILABLE = False

try:
    from plyer import notification as _plyer_notification
    _NOTIFY_AVAILABLE = True
except Exception:
    _NOTIFY_AVAILABLE = False


def _load_base_icon(icon_path):
    """Loads the app's .ico as a Pillow image for pystray; falls back to
    a plain generated square if the file is missing or unreadable, so a
    packaging issue with the icon file can't take the whole tray down."""
    try:
        return Image.open(icon_path).convert("RGBA")
    except Exception:
        return Image.new("RGBA", (64, 64), (11, 61, 145, 255))  # TASHIL blue fallback


def draw_badge(base_image, count):
    """
    Returns a NEW image: the base tray icon with a small red circle and
    the unread count drawn in the bottom-right corner — the same visual
    idea as a phone app's notification badge. count <= 0 returns the
    base image unchanged (no badge shown).

    This function's output WAS actually rendered and visually inspected
    at several sizes in the sandbox, including a real 24×24px downscale
    (the typical Windows tray icon size) — Pillow's tiny default bitmap
    font was illegible at that size on the first attempt, which is why
    this uses ImageFont.load_default(size=...) scaled to the badge
    instead. The composition itself is verified; only how Windows
    itself renders it in the live tray (anti-aliasing, exact pixel
    density) has not been.
    """
    if count <= 0 or not _TRAY_AVAILABLE:
        return base_image

    img = base_image.copy()
    w, h = img.size
    draw = ImageDraw.Draw(img)

    badge_d = max(int(w * 0.62), 10)
    x0, y0 = w - badge_d, h - badge_d
    x1, y1 = w, h
    draw.ellipse([x0, y0, x1, y1], fill=(220, 38, 38, 255),
                 outline=(255, 255, 255, 255), width=max(1, w // 24))

    label = str(count) if count < 100 else "99+"
    try:
        font = ImageFont.load_default(size=int(badge_d * 0.62))
    except TypeError:
        font = ImageFont.load_default()  # older Pillow without size= support — still legible, just not scaled

    bbox = draw.textbbox((0, 0), label, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x0 + (badge_d - text_w) / 2 - bbox[0]
    ty = y0 + (badge_d - text_h) / 2 - bbox[1]
    draw.text((tx, ty), label, fill=(255, 255, 255, 255), font=font)

    return img


class TrayController:
    """
    Owns the pystray icon and the background unread-count poller.
    Constructing this is always safe, even without pystray/plyer
    installed — check `.available` before relying on any tray behavior;
    every method below is a no-op when it's False.
    """

    def __init__(self, icon_path, on_show, on_quit, poll_fn, poll_interval=15):
        self.available = _TRAY_AVAILABLE
        self._on_show = on_show
        self._on_quit = on_quit
        self._poll_fn = poll_fn
        self._poll_interval = poll_interval
        self._icon = None
        self._base_image = None
        self._last_unread = 0
        self._stop_event = threading.Event()

        if not self.available:
            return

        try:
            self._base_image = _load_base_icon(icon_path)
            menu = pystray.Menu(
                pystray.MenuItem("Afficher TASHIL", self._handle_show, default=True),
                pystray.MenuItem("Quitter", self._handle_quit),
            )
            self._icon = pystray.Icon("tashil", self._base_image, "TASHIL DOCUMENT HUB", menu)
        except Exception:
            # Anything going wrong while BUILDING the tray icon must not
            # break the rest of the app — degrade to unavailable.
            self.available = False
            self._icon = None

    def _handle_show(self, icon=None, item=None):
        try:
            self._on_show()
        except Exception:
            pass

    def _handle_quit(self, icon=None, item=None):
        self._stop_event.set()
        try:
            self._on_quit()
        finally:
            if self._icon:
                try:
                    self._icon.stop()
                except Exception:
                    pass

    def _notify_new_messages(self, new_count):
        if not _NOTIFY_AVAILABLE:
            return
        try:
            _plyer_notification.notify(
                title="TASHIL DOCUMENT HUB",
                message=f"{new_count} nouveau(x) message(s) reçu(s)",
                app_name="TASHIL DOCUMENT HUB",
                timeout=6,
            )
        except Exception:
            pass  # a failed toast is never worth interrupting the app for

    def _poll_loop(self):
        while not self._stop_event.is_set():
            try:
                count = self._poll_fn()
                # poll_fn returns None when the profile is locked or the
                # request failed transiently — treated as "nothing new",
                # never as zero (which would wrongly clear a real badge).
                if count is not None and count != self._last_unread:
                    if count > self._last_unread:
                        self._notify_new_messages(count - self._last_unread)
                    self._last_unread = count
                    if self._icon:
                        self._icon.icon = draw_badge(self._base_image, count)
            except Exception:
                pass  # one missed poll cycle is not worth crashing the tray over
            self._stop_event.wait(self._poll_interval)

    def run(self):
        """
        Blocks the calling thread running the tray icon's event loop —
        call this from a DEDICATED background thread, never the main
        thread (which pywebview's own event loop needs on Windows).
        No-op if the tray failed to initialize.
        """
        if not self.available:
            return
        threading.Thread(target=self._poll_loop, daemon=True).start()
        try:
            self._icon.run()  # blocks until self._icon.stop() is called
        except Exception:
            pass

    def stop(self):
        self._stop_event.set()
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
