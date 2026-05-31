# media/videos.py
import os
import vlc  # pip install python-vlc

VIDEO_EXT = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv'}

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
        # Flags optimizados para RPi con fix de audio
        flags = ['--fullscreen', '--no-video-title-show', '--no-osd', '--quiet', '--aout=alsa']
        self.instancia = vlc.Instance(flags)
        self.reproductor = self.instancia.media_player_new()
        self.lista_reproductor = self.instancia.media_list_player_new()
        self.lista_reproductor.set_media_player(self.reproductor)

    def reproducir_lista(self, lista_rutas, loop=False):
        """Reproduce los videos uno tras otro. Con loop=True repite en bucle."""
        self.lista_reproductor.stop()
        media_list = self.instancia.media_list_new()
        for ruta in lista_rutas:
            media_list.add_media(self.instancia.media_new(ruta))

        self.lista_reproductor.set_media_list(media_list)
        if loop:
            self.lista_reproductor.set_playback_mode(vlc.PlaybackMode.loop)
        else:
            self.lista_reproductor.set_playback_mode(vlc.PlaybackMode.default)
        self.lista_reproductor.play()

    def detener(self):
        self.lista_reproductor.stop()
        self.reproductor.stop()