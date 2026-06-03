# media/videos.py
import os
import vlc  # pip install python-vlc
from media.classifier import AUDIO_FLAGS, VIDEO_EXT

def obtener_videos(ruta_montaje):
    """Escanea el USB y devuelve una lista con las rutas de los videos."""
    lista_videos = []
    for root, _, files in os.walk(ruta_montaje):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXT:
                lista_videos.append(os.path.join(root, f))
    return lista_videos

class ReproductorVideo:
    def __init__(self):
        # Sin --fullscreen: el video se embebe dentro de un frame de tkinter.
        # plughw:0,0 en lugar de "default" — en RPi OS Lite con sudo xinit,
        # "default" da error 524 (ESTRPIPE); plughw maneja conversión de formato.
        flags = ['--no-video-title-show', '--no-osd', '--quiet'] + AUDIO_FLAGS
        self.instancia = vlc.Instance(flags)
        self.reproductor = self.instancia.media_player_new()
        self.lista_reproductor = self.instancia.media_list_player_new()
        self.lista_reproductor.set_media_player(self.reproductor)
        self._xwin = 0  # X11 Window ID del frame de tkinter

    def set_ventana(self, win_id):
        """Vincula el reproductor a un frame de tkinter (X11 Window ID).
        Llamar una vez despues de que la ventana tkinter este visible.
        """
        self._xwin = win_id
        self.reproductor.set_xwindow(win_id)

    def reproducir_lista(self, lista_rutas, loop=False):
        """Reproduce los videos dentro del frame tkinter vinculado."""
        self.lista_reproductor.stop()
        media_list = self.instancia.media_list_new()
        for ruta in lista_rutas:
            media_list.add_media(self.instancia.media_new(ruta))

        self.lista_reproductor.set_media_list(media_list)
        # Re-vincular la ventana antes de reproducir (necesario tras stop)
        if self._xwin:
            self.reproductor.set_xwindow(self._xwin)
        if loop:
            self.lista_reproductor.set_playback_mode(vlc.PlaybackMode.loop)
        else:
            self.lista_reproductor.set_playback_mode(vlc.PlaybackMode.default)
        self.lista_reproductor.play()

    def detener(self):
        self.lista_reproductor.stop()
        self.reproductor.stop()