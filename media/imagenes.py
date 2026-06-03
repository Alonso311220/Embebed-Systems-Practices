# media/imagenes.py
import os
import vlc  # pip install python-vlc
from media.classifier import AUDIO_FLAGS

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}


def obtener_imagenes(ruta_montaje):
    """Escanea el USB y devuelve rutas completas de imágenes ordenadas."""
    lista = []
    for root, _, files in os.walk(ruta_montaje):
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXT:
                lista.append(os.path.join(root, f))
    return sorted(lista)


class ReproductorImagenes:
    def __init__(self):
        # --image-duration: segundos por foto; plughw:0,0 evita error 524 de ALSA en RPi
        flags = ['--no-osd', '--quiet', '--image-duration=1.5'] + AUDIO_FLAGS
        self.instancia = vlc.Instance(flags)
        self.reproductor = self.instancia.media_player_new()
        self.lista_reproductor = self.instancia.media_list_player_new()
        self.lista_reproductor.set_media_player(self.reproductor)
        self._xwin = 0

    def set_ventana(self, win_id):
        """Vincula el reproductor al frame de tkinter (X11 Window ID)."""
        self._xwin = win_id
        self.reproductor.set_xwindow(win_id)

    def iniciar_presentacion(self, lista_rutas):
        """Muestra las imágenes en bucle como presentación de diapositivas."""
        self.lista_reproductor.stop()
        media_list = self.instancia.media_list_new()
        for ruta in lista_rutas:
            media_list.add_media(self.instancia.media_new(ruta))
        self.lista_reproductor.set_media_list(media_list)
        if self._xwin:
            self.reproductor.set_xwindow(self._xwin)
        self.lista_reproductor.set_playback_mode(vlc.PlaybackMode.loop)
        self.lista_reproductor.play()

    def detener(self):
        self.lista_reproductor.stop()
        self.reproductor.stop()
