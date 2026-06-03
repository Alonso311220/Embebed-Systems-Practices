# media/classifier.py
import os

VIDEO_EXT  = {'.mp4','.mkv','.avi','.mov','.m4v','.wmv',
              '.ts','.m2ts','.webm','.3gp','.flv','.mpg','.mpeg','.vob','.divx'}
AUDIO_EXT  = {'.mp3','.flac','.ogg','.wav','.aac','.m4a'}
IMAGE_EXT  = {'.jpg','.jpeg','.png','.bmp','.gif','.webp'}

AUDIO_FLAGS = ["--aout=alsa", "--alsa-audio-device=plughw:0,0"]

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