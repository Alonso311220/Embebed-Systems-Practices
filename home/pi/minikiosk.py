#!/usr/bin/env python3
"""
Kiosco Multimedia - Practica 8 Actividad 5
Reproduce un video inicial y luego un slideshow de imagenes en bucle
usando ffmpeg (sin VLC).
Se ejecuta en paralelo con actividad4.py (LCD marquesina + temperatura).
"""

import subprocess
import time
import os
import signal
import sys

# Directorio base: donde esta este script
BASE = os.path.dirname(os.path.abspath(__file__))

os.system('clear')
os.system('tput civis')  # Ocultar cursor

proc = None  # Proceso ffmpeg activo

def terminar(sig=None, frame=None):
    """Mata ffmpeg y restaura el cursor al salir."""
    if proc and proc.poll() is None:
        proc.terminate()
    os.system('tput cnorm')
    sys.exit(0)

signal.signal(signal.SIGTERM, terminar)
signal.signal(signal.SIGINT,  terminar)


def reproducir(ruta, duracion=None):
    """
    Lanza ffplay para mostrar un archivo (video o imagen).
    duracion: segundos maximos; None = espera a que termine solo.
    """
    global proc

    cmd = [
        'ffplay',
        '-fs',                  # Pantalla completa
        '-autoexit',            # Sale al terminar el archivo
        '-nostats',             # Sin estadisticas en consola
        '-loglevel', 'quiet',   # Sin mensajes de ffmpeg
        '-an',                  # Sin audio (opcional, quita si quieres sonido)
    ]

    if duracion:
        cmd += ['-t', str(duracion)]  # Limitar duracion

    cmd.append(ruta)

    proc = subprocess.Popen(cmd)

    if duracion:
        try:
            proc.wait(timeout=duracion + 2)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait()
    else:
        proc.wait()


# ------------------------------------------------------------------
# 1. VIDEO INICIAL
# ------------------------------------------------------------------
video_path = os.path.join(BASE, 'videos', 'video.mp4')

if os.path.exists(video_path):
    print("Reproduciendo video inicial...")
    reproducir(video_path)  # Espera a que el video termine solo
else:
    print(f"Advertencia: no se encontro {video_path}, saltando video.")

# ------------------------------------------------------------------
# 2. SLIDESHOW DE IMAGENES EN BUCLE (3 segundos cada una)
# ------------------------------------------------------------------
imagenes = []
for i in range(1, 5):
    ruta = os.path.join(BASE, 'pictures', f'pic0{i}.jpg')
    if os.path.exists(ruta):
        imagenes.append(ruta)
    else:
        print(f"Advertencia: no se encontro {ruta}")

if not imagenes:
    print("Error: no hay imagenes en pictures/. Saliendo.")
    terminar()

print(f"Iniciando slideshow con {len(imagenes)} imagen(es). Ctrl+C para salir.")

try:
    while True:
        for img in imagenes:
            reproducir(img, duracion=3)
except KeyboardInterrupt:
    terminar()
