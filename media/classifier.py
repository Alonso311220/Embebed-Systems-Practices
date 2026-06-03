# media/classifier.py
import os
import subprocess as _sp

VIDEO_EXT  = {'.mp4','.mkv','.avi','.mov','.m4v','.wmv',
              '.ts','.m2ts','.webm','.3gp','.flv','.mpg','.mpeg','.vob','.divx'}
AUDIO_EXT  = {'.mp3','.flac','.ogg','.wav','.aac','.m4a'}
IMAGE_EXT  = {'.jpg','.jpeg','.png','.bmp','.gif','.webp'}

def _detectar_audio_flags() -> list:
    """Detecta la salida de audio óptima para VLC en RPi bajo xinit.
    Prioridad: PulseAudio (si corre) → card HDMI ALSA → plughw:0,0 (jack 3.5mm).
    """
    try:
        if _sp.run(["pulseaudio", "--check"], capture_output=True).returncode == 0:
            return ["--aout=pulse"]
    except FileNotFoundError:
        pass
    try:
        out = _sp.run(["aplay", "-l"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            ll = line.lower()
            if ll.startswith("card") and ("hdmi" in ll or "vc4" in ll):
                card = line.split(":")[0].split()[-1]
                return ["--aout=alsa", f"--alsa-audio-device=plughw:{card},0"]
    except Exception:
        pass
    return ["--aout=alsa", "--alsa-audio-device=plughw:0,0"]

AUDIO_FLAGS = _detectar_audio_flags()

def classify_usb(path):
    counts = {'video': 0, 'audio': 0, 'image': 0}
    for root, _, files in os.walk(path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXT:  counts['video'] += 1
            elif ext in AUDIO_EXT: counts['audio'] += 1
            elif ext in IMAGE_EXT: counts['image'] += 1
    # Determinar tipo dominante
    total = sum(counts.values())
    if total == 0:
        return 'empty'
    dominant = max(counts, key=counts.get)
    others = total - counts[dominant]
    if others > 0:
        return 'mixed'      # Contenido mixto → preguntar
    return dominant         # 'video', 'audio' o 'image'