# media/player.py
import subprocess, glob, os

class MediaPlayer:
    def __init__(self):
        self.proc = None

    def _kill(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def play_video(self, path):
        """Reproduce un archivo o directorio completo en bucle."""
        self._kill()
        if os.path.isdir(path):
            files = self._find(path, ['.mp4','.mkv','.avi','.mov'])
            playlist = "/tmp/playlist.m3u"
            with open(playlist, "w") as f:
                f.write("\n".join(files))
            self.proc = subprocess.Popen(["vlc", "--fullscreen",
                "--loop", playlist])
        else:
            self.proc = subprocess.Popen(["vlc", "--fullscreen", path])

    def play_audio(self, path):
        """Reproduce todas las pistas en bucle."""
        self._kill()
        files = self._find(path, ['.mp3','.flac','.ogg','.wav','.aac'])
        self.proc = subprocess.Popen(
            ["vlc", "--loop", "--no-video"] + files)

    def slideshow(self, path):
        """Presentación de imágenes cada 5 segundos."""
        self._kill()
        files = self._find(path, ['.jpg','.jpeg','.png','.bmp'])
        # feh en modo slideshow
        self.proc = subprocess.Popen(
            ["feh", "--fullscreen", "--slideshow-delay", "5",
             "--auto-zoom"] + files)

    def launch_online(self, url):
        """Chromium en modo kiosk para servicios en línea."""
        self._kill()
        self.proc = subprocess.Popen([
            "chromium-browser",
            "--kiosk", "--noerrdialogs",
            "--disable-infobars",
            "--no-first-run",
            url
        ])

    def stop(self):
        self._kill()

    def _find(self, path, exts):
        files = []
        for ext in exts:
            files += glob.glob(f"{path}/**/*{ext}", recursive=True)
        return sorted(files)