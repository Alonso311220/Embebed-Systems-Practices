# remote/teclado_virtual.py
"""
Teclado virtual usando Linux uinput (kernel-level).
Los eventos generados son INDISTINGUIBLES de un teclado físico real,
lo que los hace compatibles con Netflix, HBO y cualquier servicio
que rechace eventos sintéticos de X11 (xdotool XTestFakeKeyEvent).

Requiere:
    sudo apt install python3-evdev
    sudo modprobe uinput
    echo 'uinput' | sudo tee -a /etc/modules
"""

import logging
log = logging.getLogger("teclado_virtual")

try:
    from evdev import UInput, ecodes as e

    # Mapa: nombre de tecla → código Linux
    MAPA_TECLAS = {
        "Up":     e.KEY_UP,
        "Down":   e.KEY_DOWN,
        "Left":   e.KEY_LEFT,
        "Right":  e.KEY_RIGHT,
        "Return": e.KEY_ENTER,
        "Escape": e.KEY_ESC,
        "space":  e.KEY_SPACE,
        "F11":    e.KEY_F11,
        "Tab":    e.KEY_TAB,
    }
    _EVDEV_OK = True

except ImportError:
    _EVDEV_OK = False
    MAPA_TECLAS = {}
    log.warning("python3-evdev no disponible — instalar: sudo apt install python3-evdev")


class TecladoVirtual:
    """Simula un teclado físico a nivel de kernel mediante /dev/uinput."""

    def __init__(self):
        self._ui = None
        if not _EVDEV_OK:
            return
        try:
            self._ui = UInput(name="smarttv-remote-keyboard")
            log.info("TecladoVirtual iniciado (uinput)")
        except Exception as ex:
            log.error("No se pudo crear UInput: %s", ex)
            log.error("Asegúrate de ejecutar: sudo modprobe uinput")

    @property
    def disponible(self) -> bool:
        return self._ui is not None

    def tecla(self, nombre: str):
        """Presiona y suelta una tecla. nombre debe coincidir con MAPA_TECLAS."""
        if self._ui is None:
            return
        codigo = MAPA_TECLAS.get(nombre)
        if codigo is None:
            log.warning("Tecla desconocida: '%s'", nombre)
            return
        try:
            self._ui.write(e.EV_KEY, codigo, 1)  # key down
            self._ui.write(e.EV_KEY, codigo, 0)  # key up
            self._ui.syn()
        except Exception as ex:
            log.error("Error enviando tecla '%s': %s", nombre, ex)

    def cerrar(self):
        if self._ui:
            self._ui.close()
            self._ui = None
