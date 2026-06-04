#!/usr/bin/env python3
"""
services/online.py  —  Servicios en línea para SmartTV Kiosk
=============================================================
Funcionalidades:
  1. Detector de WiFi  → escanea redes, conecta con/sin contraseña
  2. Streaming Video   → Netflix, HBO Go, Blim (Chromium kiosk)
  3. Streaming Música  → Spotify, YouTube Music, Deezer (Chromium kiosk)

Dependencias del sistema:
    sudo apt install network-manager chromium-browser

Uso desde menu.py:
    from services.online import GestorOnline
    gestor = GestorOnline()
    gestor.abrir_streaming_video("netflix")
    gestor.escanear_redes()   # → lista de WifiRed
    gestor.conectar_red("MiRed", "MiPassword")
"""

from __future__ import annotations

import subprocess
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("services.online")

# ─────────────────────────────────────────────────────────────────────────────
#  Catálogo de servicios
# ─────────────────────────────────────────────────────────────────────────────

SERVICIOS_VIDEO = {
    "netflix":  {"label": "Netflix",       "url": "https://www.netflix.com",         "char": "N", "color": "#e50914"},
    "hbo":      {"label": "HBO Go",        "url": "https://www.hbomax.com/mx/es",      "char": "H", "color": "#000000"},
    "blim":     {"label": "Blim",          "url": "https://www.blim.com",            "char": "B", "color": "#ff6600"},
    "youtube":  {"label": "YouTube",       "url": "https://www.youtube.com/tv",      "char": "▶", "color": "#ff0000"},
    "disneyplus":{"label": "Disney+",      "url": "https://www.disneyplus.com",      "char": "D", "color": "#0063e5"},
    "primevideo":{"label": "Prime Video",  "url": "https://www.primevideo.com",      "char": "P", "color": "#00a8e0"},
}

SERVICIOS_MUSICA = {
    "spotify":  {"label": "Spotify",       "url": "https://open.spotify.com",        "char": "S", "color": "#1db954"},
    "ytmusic":  {"label": "YouTube Music", "url": "https://music.youtube.com",       "char": "♪", "color": "#ff0000"},
    "deezer":   {"label": "Deezer",        "url": "https://www.deezer.com",          "char": "D", "color": "#a238ff"},
    "tidal":    {"label": "Tidal",         "url": "https://listen.tidal.com",        "char": "T", "color": "#ffffff"},
}


# ─────────────────────────────────────────────────────────────────────────────
#  Modelo de datos
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WifiRed:
    ssid:        str
    señal:       int          # dBm (0 si desconocido)
    seguridad:   str          # "WPA2", "WPA3", "WEP", "Abierta"
    conectada:   bool = False

    @property
    def icono_señal(self) -> str:
        if self.señal >= -55:  return "▂▄▆█"
        if self.señal >= -67:  return "▂▄▆ "
        if self.señal >= -78:  return "▂▄  "
        return                        "▂   "

    @property
    def necesita_contraseña(self) -> bool:
        return self.seguridad not in ("Abierta", "")


# ─────────────────────────────────────────────────────────────────────────────
#  Reproductor de navegador (Chromium kiosk)
# ─────────────────────────────────────────────────────────────────────────────

class NavegadorKiosk:
    """Lanza y cierra Chromium en modo kiosk para servicios en línea."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None

    # Detectar si dbus-run-session está disponible (solo una vez al importar)
    _DBUS_RUN = bool(subprocess.run(
        ["which", "dbus-run-session"], capture_output=True
    ).returncode == 0)

    def abrir(self, url: str):
        self.cerrar()
        chromium_args = [
            "chromium-browser",
            "--kiosk",
            "--start-fullscreen",
            "--noerrdialogs",
            "--disable-infobars",
            "--no-first-run",
            "--disable-translate",
            "--disable-features=TranslateUI",
            "--autoplay-policy=no-user-gesture-required",
            "--no-sandbox",             # requerido al correr como root (sudo xinit)
            "--disable-setuid-sandbox",
            "--disable-background-networking",
            "--disable-client-side-phishing-detection",
            "--disable-gpu",            # SwiftShader: evita errores GL en RPi
            "--disable-gpu-compositing",
            "--disable-dev-shm-usage",  # /dev/shm pequeño en RPi
            url,
        ]
        # dbus-run-session crea un bus D-Bus de sesión propio para Chromium,
        # eliminando todos los errores "Failed to connect to the bus".
        cmd = (["dbus-run-session", "--"] + chromium_args
               if self._DBUS_RUN else chromium_args)
        try:
            # stderr=DEVNULL: silencia cualquier mensaje de log restante de Chromium
            self._proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
            log.info("Chromium abierto: %s", url)
        except FileNotFoundError:
            log.error("chromium-browser no encontrado. Instala con: sudo apt install chromium-browser")

    def esta_abierto(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def get_pid(self) -> int | None:
        """Devuelve el PID del proceso lanzado (dbus-run-session o chromium directo)."""
        return self._proc.pid if self._proc else None

    def cerrar(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        # Matar cualquier proceso huérfano de Chromium que haya quedado corriendo
        # (ocurre cuando dbus-run-session muere pero Chromium no)
        subprocess.run(["pkill", "-9", "-f", "chromium-browser"],
                       capture_output=True)
        log.info("Chromium cerrado")


# ─────────────────────────────────────────────────────────────────────────────
#  Gestor de WiFi (NetworkManager via nmcli)
# ─────────────────────────────────────────────────────────────────────────────

class GestorWifi:
    """
    Maneja la conexión WiFi usando nmcli (NetworkManager).
    Todos los métodos que tardan se ejecutan en hilos para no bloquear la UI.
    """

    # ── Estado actual ──────────────────────────────────────────────────────

    def hay_internet(self) -> bool:
        """Comprueba conectividad real haciendo ping a DNS de Google."""
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                capture_output=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    def wifi_activo(self) -> bool:
        """True si el adaptador WiFi está encendido."""
        try:
            r = subprocess.run(
                ["nmcli", "radio", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            return "enabled" in r.stdout
        except Exception:
            return False

    def red_conectada(self) -> str:
        """Devuelve el SSID de la red activa o '' si no hay ninguna."""
        try:
            r = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            for linea in r.stdout.splitlines():
                partes = linea.split(":")
                if len(partes) >= 2 and partes[0] == "yes":
                    return partes[1]
        except Exception:
            pass
        return ""

    # ── Escaneo ────────────────────────────────────────────────────────────

    def escanear_redes(self, callback: Callable[[list[WifiRed]], None]):
        """
        Escanea redes WiFi en un hilo aparte y llama a callback(lista).
        callback recibe lista[WifiRed] ordenada por señal descendente.
        """
        def _run():
            redes = self._scan_nmcli()
            callback(redes)

        threading.Thread(target=_run, daemon=True, name="wifi-scan").start()

    def _scan_nmcli(self) -> list[WifiRed]:
        red_actual = self.red_conectada()
        redes: list[WifiRed] = []
        try:
            # Forzar rescan
            subprocess.run(
                ["nmcli", "device", "wifi", "rescan"],
                capture_output=True, timeout=8
            )
            time.sleep(2)  # esperar que NM procese el rescan

            r = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
                capture_output=True, text=True, timeout=10
            )
            ssids_vistos: set[str] = set()
            for linea in r.stdout.splitlines():
                partes = linea.split(":")
                if len(partes) < 3:
                    continue
                ssid, señal_str, seguridad = partes[0], partes[1], partes[2]
                if not ssid or ssid in ssids_vistos:
                    continue
                ssids_vistos.add(ssid)

                try:
                    # nmcli reporta señal como porcentaje (0-100); convertir a dBm aprox.
                    pct  = int(señal_str)
                    dBm  = int(pct / 2) - 100   # aprox: 100% → -50 dBm, 0% → -100 dBm
                except ValueError:
                    dBm = -100

                seg = seguridad.strip() if seguridad.strip() else "Abierta"

                redes.append(WifiRed(
                    ssid      = ssid,
                    señal     = dBm,
                    seguridad = seg,
                    conectada = (ssid == red_actual),
                ))

        except Exception as e:
            log.error("Error escaneo WiFi: %s", e)

        return sorted(redes, key=lambda r: r.señal, reverse=True)

    # ── Conexión ───────────────────────────────────────────────────────────

    def conectar(
        self,
        ssid:       str,
        password:   str = "",
        on_exito:   Callable[[], None]       | None = None,
        on_error:   Callable[[str], None]    | None = None,
    ):
        """
        Conecta a una red WiFi en un hilo aparte.
        Llama on_exito() o on_error(mensaje) según resultado.
        """
        def _run():
            ok, msg = self._conectar_nmcli(ssid, password)
            if ok:
                if on_exito:  on_exito()
            else:
                if on_error:  on_error(msg)

        threading.Thread(target=_run, daemon=True, name="wifi-connect").start()

    def _conectar_nmcli(self, ssid: str, password: str) -> tuple[bool, str]:
        try:
            # 1. Intentar conectar a un perfil guardado primero
            r = subprocess.run(
                ["nmcli", "connection", "up", ssid],
                capture_output=True, text=True, timeout=20
            )
            if r.returncode == 0:
                log.info("Conectado a '%s' (perfil guardado)", ssid)
                return True, ""

            # 2. Nueva conexión con o sin contraseña
            if password:
                cmd = [
                    "nmcli", "device", "wifi", "connect", ssid,
                    "password", password
                ]
            else:
                cmd = ["nmcli", "device", "wifi", "connect", ssid]

            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if r.returncode == 0:
                log.info("Conectado a '%s'", ssid)
                return True, ""
            else:
                msg = r.stderr.strip() or r.stdout.strip()
                log.warning("Error conectando a '%s': %s", ssid, msg)
                return False, msg

        except subprocess.TimeoutExpired:
            return False, "Tiempo de espera agotado"
        except Exception as e:
            return False, str(e)

    def desconectar(self):
        """Desconecta la red WiFi activa."""
        try:
            subprocess.run(
                ["nmcli", "device", "disconnect", "wlan0"],
                capture_output=True, timeout=10
            )
        except Exception as e:
            log.error("Error desconectando: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
#  Gestor Online Central
# ─────────────────────────────────────────────────────────────────────────────

class GestorOnline:
    """
    Punto de entrada único para todo lo relacionado con servicios en línea.

    Uso típico desde menu.py:
        gestor_online = GestorOnline()

        # Abrir servicio de streaming
        gestor_online.abrir_streaming_video("netflix")
        gestor_online.abrir_streaming_musica("spotify")

        # WiFi
        gestor_online.escanear_redes(callback)
        gestor_online.conectar_red("MiRed", "pass123",
                                   on_exito=..., on_error=...)

        # Estado
        gestor_online.hay_internet()
        gestor_online.red_conectada()

        # Cerrar navegador
        gestor_online.cerrar_navegador()
    """

    def __init__(self):
        self.wifi      = GestorWifi()
        self.navegador = NavegadorKiosk()

    # ── Streaming ──────────────────────────────────────────────────────────

    def abrir_streaming_video(self, servicio: str):
        """
        Abre un servicio de video en Chromium kiosk.
        servicio: clave de SERVICIOS_VIDEO ('netflix', 'hbo', 'blim', ...)
        Devuelve (ok: bool, mensaje: str)
        """
        if not self.wifi.hay_internet():
            return False, "Sin conexión a internet"
        info = SERVICIOS_VIDEO.get(servicio)
        if not info:
            return False, f"Servicio desconocido: {servicio}"
        self.navegador.abrir(info["url"])
        return True, f"Abriendo {info['label']}..."

    def abrir_streaming_musica(self, servicio: str):
        """
        Abre un servicio de música en Chromium kiosk.
        servicio: clave de SERVICIOS_MUSICA ('spotify', 'ytmusic', ...)
        """
        if not self.wifi.hay_internet():
            return False, "Sin conexión a internet"
        info = SERVICIOS_MUSICA.get(servicio)
        if not info:
            return False, f"Servicio desconocido: {servicio}"
        self.navegador.abrir(info["url"])
        return True, f"Abriendo {info['label']}..."

    def cerrar_navegador(self):
        self.navegador.cerrar()

    def navegador_abierto(self) -> bool:
        return self.navegador.esta_abierto()

    def get_pid_navegador(self) -> int | None:
        return self.navegador.get_pid()

    # ── WiFi helpers (re-expuestos para simplificar imports) ───────────────

    def hay_internet(self) -> bool:
        return self.wifi.hay_internet()

    def wifi_activo(self) -> bool:
        return self.wifi.wifi_activo()

    def red_conectada(self) -> str:
        return self.wifi.red_conectada()

    def escanear_redes(self, callback: Callable[[list[WifiRed]], None]):
        """Escanea en segundo plano y llama callback(lista[WifiRed])."""
        self.wifi.escanear_redes(callback)

    def conectar_red(
        self,
        ssid:     str,
        password: str = "",
        on_exito: Callable[[], None]    | None = None,
        on_error: Callable[[str], None] | None = None,
    ):
        self.wifi.conectar(ssid, password, on_exito=on_exito, on_error=on_error)

    def desconectar_wifi(self):
        self.wifi.desconectar()

    # ── Catálogos (para que menu.py pueda construir los submenús) ──────────

    @staticmethod
    def catalogo_video() -> dict:
        return SERVICIOS_VIDEO

    @staticmethod
    def catalogo_musica() -> dict:
        return SERVICIOS_MUSICA
