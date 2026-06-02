# media/musica.py

import os
import vlc

EXT_AUDIO = (
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".aac",
    ".m4a"
)

def obtener_canciones(ruta_usb):
    canciones = []

    for root, _, files in os.walk(ruta_usb):
        for f in files:
            if f.lower().endswith(EXT_AUDIO):
                canciones.append(os.path.join(root, f))

    return sorted(canciones)


class ReproductorMusica:

    def __init__(self):
        self.instance = vlc.Instance()
        self.player = self.instance.media_list_player_new()

    def reproducir_lista(self, canciones, loop=True):

        media_list = self.instance.media_list_new()

        for archivo in canciones:
            media = self.instance.media_new(archivo)
            media_list.add_media(media)

        self.player.set_media_list(media_list)

        if loop:
            self.player.set_playback_mode(vlc.PlaybackMode.loop)
        else:
            self.player.set_playback_mode(vlc.PlaybackMode.default)

        self.player.play()

    def detener(self):
        self.player.stop()
