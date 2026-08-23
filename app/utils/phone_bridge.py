# -*- coding: utf-8 -*-
"""
TASHIL DOCUMENT HUB — phone_bridge.py

Embedded local HTTP server that lets a phone on the same Wi-Fi/LAN push a
photo/document straight into the PC's outgoing attachment queue, without
any cable or app install on the phone — just scan the QR code shown on
screen and use the browser page it opens.

Flow:
    1. PhoneBridgeServer starts an http.server on PHONE_BRIDGE_PORT.
    2. get_qr_image() renders a QR code pointing to http://<lan_ip>:<port>/
    3. Phone scans -> browser opens a minimal upload page (served inline).
    4. Phone POSTs a file to /upload -> server saves it into
       C:\\TASHIL\\TASHIL_ARCHIVES\\Courrier_Sortant via archive_manager,
       and inserts a row into phone_bridge_queue for the UI to pick up.
"""

import io
import json
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

import qrcode
from PIL import Image

from app.config import PHONE_BRIDGE_PORT
from app.utils.database import get_connection
from app.utils.archive_manager import save_incoming_from_phone

_UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TASHIL — Pont Téléphone</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; background:#0F1419; color:#E6EDF3;
          display:flex; flex-direction:column; align-items:center; padding:32px 20px; margin:0; }}
  h1 {{ color:#00A651; font-size:20px; }}
  .card {{ background:#1C2128; border:1px solid #2D333B; border-radius:14px; padding:24px;
           width:100%; max-width:360px; text-align:center; }}
  input[type=file] {{ margin:18px 0; color:#E6EDF3; }}
  button {{ background:#00A651; color:white; border:none; padding:14px 28px; border-radius:10px;
            font-size:16px; font-weight:bold; width:100%; }}
  #status {{ margin-top:16px; font-size:14px; color:#8B949E; }}
</style>
</head>
<body>
  <h1>🇩🇿 TASHIL — Pont Téléphone</h1>
  <div class="card">
    <p>Sélectionnez ou prenez une photo du document à transmettre au PC.</p>
    <form id="f">
      <input type="file" name="file" id="file" accept="image/*,application/pdf" capture="environment" required>
      <button type="submit">📤 Envoyer au PC</button>
    </form>
    <div id="status"></div>
  </div>
<script>
document.getElementById('f').addEventListener('submit', async function(e) {{
  e.preventDefault();
  const fileInput = document.getElementById('file');
  const status = document.getElementById('status');
  if (!fileInput.files.length) return;
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  status.textContent = 'Envoi en cours...';
  try {{
    const resp = await fetch('/upload', {{ method: 'POST', body: formData }});
    if (resp.ok) {{
      status.textContent = '✅ Document transmis avec succès !';
      fileInput.value = '';
    }} else {{
      status.textContent = '⛔ Échec de l\\'envoi.';
    }}
  }} catch (err) {{
    status.textContent = '⛔ Erreur réseau.';
  }}
}});
</script>
</body>
</html>"""


def get_lan_ip() -> str:
    """Best-effort LAN IP discovery (no external traffic actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_qr_image(url: str) -> Image.Image:
    """Generate a PIL image of the QR code pointing at the bridge URL."""
    qr = qrcode.QRCode(version=1, box_size=8, border=2,
                        error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="#00A651", back_color="white").convert("RGB")


class _BridgeHandler(BaseHTTPRequestHandler):
    server_version = "TASHILBridge/1.0"

    def log_message(self, fmt, *args):
        pass  # Silence default stderr logging

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = _UPLOAD_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/upload":
            self.send_response(404)
            self.end_headers()
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_response(400)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        boundary = content_type.split("boundary=")[-1].encode("utf-8")
        filename, file_bytes = self._extract_file(raw_body, boundary)

        if not filename or not file_bytes:
            self.send_response(400)
            self.end_headers()
            return

        saved_path = save_incoming_from_phone(filename, file_bytes)

        conn = get_connection()
        conn.execute(
            "INSERT INTO phone_bridge_queue (file_path, original_name, received_at, consumed) "
            "VALUES (?, ?, ?, 0)",
            (saved_path, filename, datetime.now().isoformat())
        )
        conn.commit()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "path": saved_path}).encode("utf-8"))

    @staticmethod
    def _extract_file(raw_body: bytes, boundary: bytes):
        """Minimal multipart/form-data parser sufficient for a single-file upload."""
        parts = raw_body.split(b"--" + boundary)
        for part in parts:
            if b'name="file"' in part:
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                headers = part[:header_end].decode("utf-8", errors="ignore")
                data = part[header_end + 4:]
                data = data.rstrip(b"\r\n--")
                filename = "scan.jpg"
                for segment in headers.split(";"):
                    if "filename=" in segment:
                        filename = segment.split("filename=")[-1].strip().strip('"')
                        if not filename:
                            filename = f"scan_{uuid.uuid4().hex[:8]}.jpg"
                return filename, data
        return None, None


class PhoneBridgeServer:
    """Wraps the ThreadingHTTPServer lifecycle so the UI can start/stop it cleanly."""

    def __init__(self, port: int = PHONE_BRIDGE_PORT):
        self.port = port
        self._httpd = None
        self._thread = None

    @property
    def url(self) -> str:
        return f"http://{get_lan_ip()}:{self.port}/"

    def start(self):
        if self._httpd is not None:
            return
        self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), _BridgeHandler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
            self._thread = None

    def is_running(self) -> bool:
        return self._httpd is not None


def poll_new_uploads() -> list[dict]:
    """Returns unconsumed phone_bridge_queue rows and marks them consumed."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM phone_bridge_queue WHERE consumed = 0 ORDER BY id ASC"
    ).fetchall()
    if rows:
        conn.execute("UPDATE phone_bridge_queue SET consumed = 1 WHERE consumed = 0")
        conn.commit()
    return [dict(r) for r in rows]
