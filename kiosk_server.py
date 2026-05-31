"""
kiosk_server.py  —  Backend Flask + Pygame para Raspberry Pi Kiosk
Ejecutar:  python3 kiosk_server.py
Requiere:  pip install flask pygame pillow
"""

import os
import glob
import threading
import subprocess
import logging
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

# ── Pygame (solo display de imágenes; mpv/vlc manejan video/audio) ─────────
import pygame
from PIL import Image

# ── Config ─────────────────────────────────────────────────────────────────
USB_MOUNT_ROOT = "/media"          # raíz donde se montan los USB en Raspberry
ALLOWED_VIDEO   = {"mp4","mkv","avi","mov","webm","ts","m4v"}
ALLOWED_AUDIO   = {"mp3","flac","ogg","wav","aac","m4a","opus"}
ALLOWED_IMAGE   = {"jpg","jpeg","png","heic","gif","webp","bmp"}
ALL_MEDIA       = ALLOWED_VIDEO | ALLOWED_AUDIO | ALLOWED_IMAGE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kiosk")

app  = Flask(__name__)
CORS(app)  # permite peticiones desde el HTML local

# ── Estado global ───────────────────────────────────────────────────────────
_player_proc: subprocess.Popen | None = None   # proceso mpv/vlc activo
_pygame_thread: threading.Thread | None = None
_pygame_running = False

# ── Inicializar Pygame (modo framebuffer para Pi sin X11) ───────────────────
def _init_pygame():
    os.environ.setdefault("SDL_VIDEODRIVER", "fbcon")   # framebuffer
    os.environ.setdefault("SDL_FBDEV",       "/dev/fb0")
    pygame.init()
    info = pygame.display.Info()
    log.info(f"Pygame: resolución detectada {info.current_w}x{info.current_h}")
    return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

# ╔══════════════════════════════════════════════════════════╗
# ║  RUTAS API                                               ║
# ╚══════════════════════════════════════════════════════════╝

@app.route("/list")
def list_files():
    """
    GET /list?ext=mp4,mkv,avi
    Devuelve JSON: {"files":[{"name":"...","size":"...","path":"..."},...]}
    Busca en todos los puntos de montaje bajo USB_MOUNT_ROOT.
    """
    exts_param = request.args.get("ext", "")
    wanted = {e.lower().strip() for e in exts_param.split(",") if e.strip()}
    if not wanted:
        wanted = ALL_MEDIA

    results = []
    usb_dirs = _find_usb_mounts()
    for mount in usb_dirs:
        for fpath in Path(mount).rglob("*"):
            if fpath.is_file() and fpath.suffix.lstrip(".").lower() in wanted:
                size_bytes = fpath.stat().st_size
                results.append({
                    "name": fpath.name,
                    "size": _human_size(size_bytes),
                    "path": str(fpath)
                })

    log.info(f"Listando {len(results)} archivos (exts={wanted})")
    return jsonify({"files": results, "count": len(results)})


@app.route("/usb/status")
def usb_status():
    """
    GET /usb/status
    Devuelve los puntos de montaje USB activos.
    """
    mounts = _find_usb_mounts()
    slots = []
    for i, m in enumerate(mounts[:4]):
        label = Path(m).name
        slots.append({"port": i, "label": label, "path": m, "connected": True})
    # Rellenar hasta 4 slots
    for i in range(len(slots), 4):
        slots.append({"port": i, "label": "", "path": "", "connected": False})
    return jsonify({"slots": slots})


@app.route("/play", methods=["POST"])
def play_media():
    """
    POST /play   body: file=<ruta_absoluta>
    Reproduce video o audio con mpv (fullscreen).
    """
    fpath = request.form.get("file", "").strip()
    if not fpath or not os.path.isfile(fpath):
        return jsonify({"ok": False, "error": "Archivo no encontrado"}), 404

    ext = Path(fpath).suffix.lstrip(".").lower()
    if ext not in (ALLOWED_VIDEO | ALLOWED_AUDIO):
        return jsonify({"ok": False, "error": "Tipo de archivo no soportado"}), 400

    _stop_player()
    _play_with_mpv(fpath)
    return jsonify({"ok": True, "file": fpath})


@app.route("/view", methods=["POST"])
def view_image():
    """
    POST /view   body: file=<ruta_absoluta>
    Muestra imagen en pantalla usando Pygame (fullscreen).
    """
    global _pygame_thread, _pygame_running

    fpath = request.form.get("file", "").strip()
    if not fpath or not os.path.isfile(fpath):
        return jsonify({"ok": False, "error": "Archivo no encontrado"}), 404

    ext = Path(fpath).suffix.lstrip(".").lower()
    if ext not in ALLOWED_IMAGE:
        return jsonify({"ok": False, "error": "No es una imagen válida"}), 400

    _stop_player()
    _pygame_running = True
    _pygame_thread = threading.Thread(target=_show_image_pygame, args=(fpath,), daemon=True)
    _pygame_thread.start()
    return jsonify({"ok": True, "file": fpath})


@app.route("/stop", methods=["POST"])
def stop_media():
    """
    POST /stop
    Detiene cualquier reproducción activa.
    """
    _stop_player()
    _stop_pygame()
    return jsonify({"ok": True})


# ╔══════════════════════════════════════════════════════════╗
# ║  LÓGICA INTERNA                                          ║
# ╚══════════════════════════════════════════════════════════╝

def _find_usb_mounts() -> list[str]:
    """Devuelve lista de directorios montados bajo USB_MOUNT_ROOT."""
    try:
        mounts = []
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mountpoint = parts[1]
                    if mountpoint.startswith(USB_MOUNT_ROOT) and mountpoint != USB_MOUNT_ROOT:
                        mounts.append(mountpoint)
        return mounts
    except Exception:
        # Fallback: buscar subdirectorios directamente
        try:
            return [str(p) for p in Path(USB_MOUNT_ROOT).iterdir() if p.is_dir()]
        except Exception:
            return []


def _play_with_mpv(fpath: str):
    """Lanza mpv en fullscreen. Alternativa: vlc --fullscreen."""
    global _player_proc
    cmd = [
        "mpv",
        "--fullscreen",
        "--no-terminal",
        "--quiet",
        fpath
    ]
    try:
        _player_proc = subprocess.Popen(cmd)
        log.info(f"mpv PID={_player_proc.pid}  →  {fpath}")
    except FileNotFoundError:
        # Si mpv no está, intentar con cvlc
        cmd[0] = "cvlc"
        try:
            _player_proc = subprocess.Popen(cmd + ["--play-and-exit"])
            log.info(f"cvlc PID={_player_proc.pid}  →  {fpath}")
        except FileNotFoundError:
            log.error("No se encontró mpv ni cvlc. Instala: sudo apt install mpv")


def _stop_player():
    global _player_proc
    if _player_proc and _player_proc.poll() is None:
        _player_proc.terminate()
        try:
            _player_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _player_proc.kill()
        log.info(f"Player detenido (PID={_player_proc.pid})")
    _player_proc = None


def _show_image_pygame(fpath: str):
    """Corre en hilo: muestra la imagen en fullscreen con Pygame."""
    global _pygame_running
    try:
        screen = _init_pygame()
        pil_img = Image.open(fpath).convert("RGB")
        sw, sh = screen.get_size()
        pil_img.thumbnail((sw, sh), Image.LANCZOS)
        pg_img = pygame.image.fromstring(pil_img.tobytes(), pil_img.size, "RGB")
        x = (sw - pg_img.get_width())  // 2
        y = (sh - pg_img.get_height()) // 2
        screen.fill((0, 0, 0))
        screen.blit(pg_img, (x, y))
        pygame.display.flip()

        clock = pygame.time.Clock()
        while _pygame_running:
            for ev in pygame.event.get():
                if ev.type in (pygame.QUIT, pygame.KEYDOWN):
                    _pygame_running = False
            clock.tick(30)
    except Exception as e:
        log.error(f"Pygame error: {e}")
    finally:
        pygame.quit()


def _stop_pygame():
    global _pygame_running
    _pygame_running = False


def _human_size(b: int) -> str:
    for unit in ("B","KB","MB","GB","TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


# ── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=== Raspberry Kiosk Server iniciado en http://localhost:5000 ===")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
