#!/usr/bin/env python3
"""
media/usb_media.py
==================
Módulo central para reproducir contenido desde USB en el kiosko SmartTV.
Maneja los 4 tipos de USB:
  1. Solo video  (películas / clips)
  2. Solo audio  (música)
  3. Solo imagen (galería / slideshow)
  4. Mixto       (imágenes + videos u otra combinación)

Depende de:
  - media/classifier.py  → classify_usb(), VIDEO_EXT, AUDIO_EXT, IMAGE_EXT
  - media/videos.py      → ReproductorVideo
  - VLC (python-vlc)     → audio
  - feh                  → slideshow de imágenes
"""

import os
import glob
import subprocess

import vlc

from media.classifier import VIDEO_EXT, AUDIO_EXT, IMAGE_EXT
from media.videos import ReproductorVideo

# ──────────────────────────────────────────────────────────────────────────────
#  Helpers de escaneo
# ──────────────────────────────────────────────────────────────────────────────

def _escanear(ruta, extensiones):
    """Devuelve lista ordenada de rutas completas con las extensiones dadas."""
    resultado = []
    for raiz, _, archivos in os.walk(ruta):
        for f in archivos:
            if os.path.splitext(f)[1].lower() in extensiones:
                resultado.append(os.path.join(raiz, f))
    return sorted(resultado)


def obtener_videos(ruta):
    return _escanear(ruta, VIDEO_EXT)

def obtener_audios(ruta):
    return _escanear(ruta, AUDIO_EXT)

def obtener_imagenes(ruta):
    return _escanear(ruta, IMAGE_EXT)


# ──────────────────────────────────────────────────────────────────────────────
#  Reproductor de Audio (VLC sin video)
# ──────────────────────────────────────────────────────────────────────────────

class ReproductorAudio:
    """Reproduce pistas de audio usando VLC sin interfaz de video."""

    def __init__(self):
        flags = ['--no-video', '--quiet', '--aout=alsa']
        self.instancia = vlc.Instance(flags)
        self.reproductor = self.instancia.media_player_new()
        self.lista_reproductor = self.instancia.media_list_player_new()
        self.lista_reproductor.set_media_player(self.reproductor)

    def reproducir_lista(self, lista_rutas, loop=False):
        """Reproduce las pistas en orden. Con loop=True repite en bucle."""
        self.lista_reproductor.stop()
        media_list = self.instancia.media_list_new()
        for ruta in lista_rutas:
            media_list.add_media(self.instancia.media_new(ruta))
        self.lista_reproductor.set_media_list(media_list)
        modo = vlc.PlaybackMode.loop if loop else vlc.PlaybackMode.default
        self.lista_reproductor.set_playback_mode(modo)
        self.lista_reproductor.play()

    def pausar_reanudar(self):
        self.reproductor.pause()

    def siguiente(self):
        self.lista_reproductor.next()

    def anterior(self):
        self.lista_reproductor.previous()

    def esta_reproduciendo(self):
        return self.lista_reproductor.is_playing()

    def detener(self):
        self.lista_reproductor.stop()
        self.reproductor.stop()


# ──────────────────────────────────────────────────────────────────────────────
#  Reproductor de Imágenes (slideshow con feh)
# ──────────────────────────────────────────────────────────────────────────────

class ReproductorImagenes:
    """
    Slideshow de imágenes usando `feh`.
    Instala con: sudo apt install feh
    """

    def __init__(self, delay_seg=5):
        self.delay = delay_seg
        self._proc = None

    def reproducir_lista(self, lista_rutas, loop=True):
        """
        Muestra las imágenes en pantalla completa.
        lista_rutas: lista de rutas absolutas a imágenes.
        loop: si True, repite al llegar al final.
        """
        self.detener()
        if not lista_rutas:
            return

        cmd = [
            "feh",
            "--fullscreen",
            "--auto-zoom",
            "--slideshow-delay", str(self.delay),
            "--hide-pointer",
        ]
        if loop:
            cmd.append("--cycle-once")   # feh hace loop por defecto; cycle-once para no loop
            # Nota: feh hace loop automático. Si quieres NO loop, usa --cycle-once
            cmd = [
                "feh",
                "--fullscreen",
                "--auto-zoom",
                "--slideshow-delay", str(self.delay),
                "--hide-pointer",
            ]
        cmd += lista_rutas
        self._proc = subprocess.Popen(cmd)

    def esta_reproduciendo(self):
        return self._proc is not None and self._proc.poll() is None

    def detener(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._proc = None


# ──────────────────────────────────────────────────────────────────────────────
#  Gestor USB Central
# ──────────────────────────────────────────────────────────────────────────────

class GestorUSB:
    """
    Instancia única que agrupa los tres reproductores.
    Úsalo desde menu.py para no crear múltiples instancias de VLC.

    Ejemplo:
        gestor = GestorUSB()
        gestor.reproducir_videos(['/media/usb/pelicula.avi'])
        gestor.detener_todo()
    """

    def __init__(self):
        self.video   = ReproductorVideo()
        self.audio   = ReproductorAudio()
        self.imagen  = ReproductorImagenes(delay_seg=5)

    # ── Vídeo ──────────────────────────────────────────────────────────────
    def reproducir_videos(self, lista_rutas, loop=False):
        self.detener_todo()
        self.video.reproducir_lista(lista_rutas, loop=loop)

    # ── Audio ──────────────────────────────────────────────────────────────
    def reproducir_audios(self, lista_rutas, loop=True):
        self.detener_todo()
        self.audio.reproducir_lista(lista_rutas, loop=loop)

    # ── Imágenes ───────────────────────────────────────────────────────────
    def reproducir_imagenes(self, lista_rutas, loop=True):
        self.detener_todo()
        self.imagen.reproducir_lista(lista_rutas, loop=loop)

    # ── Mixto (video + imagen secuencial) ──────────────────────────────────
    def reproducir_mixto_videos(self, lista_rutas, loop=False):
        """Para USB mixto: reproduce solo los videos."""
        self.detener_todo()
        self.video.reproducir_lista(lista_rutas, loop=loop)

    def reproducir_mixto_imagenes(self, lista_rutas, loop=True):
        """Para USB mixto: reproduce solo las imágenes."""
        self.detener_todo()
        self.imagen.reproducir_lista(lista_rutas, loop=loop)

    # ── Estado ─────────────────────────────────────────────────────────────
    def hay_reproduccion_activa(self):
        return (
            self.video.lista_reproductor.is_playing()
            or self.video.reproductor.is_playing()
            or self.audio.esta_reproduciendo()
            or self.imagen.esta_reproduciendo()
        )

    # ── Detener todo ───────────────────────────────────────────────────────
    def detener_todo(self):
        self.video.detener()
        self.audio.detener()
        self.imagen.detener()
