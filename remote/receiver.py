"""
ir_receiver.py  —  Módulo reutilizable para leer códigos IR desde ir_keymap.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Importa este módulo en kiosk_server.py cuando quieras reaccionar a IR.

Ejemplo de integración en kiosk_server.py:
    from ir_receiver import IRReceiver

    ir = IRReceiver(keymap_path="ir_keymap.json", pin=18)
    ir.on_action("play",    lambda: requests.post("http://localhost:5000/play", ...))
    ir.on_action("stop",    lambda: requests.post("http://localhost:5000/stop"))
    ir.on_action("next",    lambda: my_next_track())
    ir.start()   # hilo en background, no bloquea
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import RPi.GPIO as GPIO
import threading
import json
import time
import logging

log = logging.getLogger("ir_receiver")


class IRReceiver:
    def __init__(self, keymap_path: str = "ir_keymap.json", pin: int = 18,
                 duplicate_gap: float = 0.3):
        self.pin           = pin
        self.duplicate_gap = duplicate_gap
        self._keymap: dict = {}          # { "0x1234": "play" }
        self._handlers: dict = {}        # { "play": callable }
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_code = None
        self._last_time = 0.0

        self._load_keymap(keymap_path)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)

    def _load_keymap(self, path: str):
        try:
            with open(path) as f:
                data = json.load(f)
            self._keymap = data.get("keymap", {})
            log.info(f"IRReceiver: {len(self._keymap)} teclas cargadas desde {path}")
        except FileNotFoundError:
            log.warning(f"IRReceiver: {path} no encontrado. Ejecuta ir_key_identifier.py primero.")
        except json.JSONDecodeError as e:
            log.error(f"IRReceiver: error al parsear {path}: {e}")

    def on_action(self, action: str, callback):
        """Registra un callback para una acción del keymap."""
        self._handlers[action] = callback

    def start(self):
        """Inicia el listener IR en un hilo daemon."""
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name="ir-listener")
        self._thread.start()
        log.info("IRReceiver: listener iniciado en background")

    def stop(self):
        self._running = False
        GPIO.cleanup()

    # ── Decodificador NEC (mismo que ir_key_identifier.py) ─────────────────

    def _decode_nec(self) -> str | None:
        t0 = time.perf_counter()
        while GPIO.input(self.pin) == GPIO.HIGH:
            if time.perf_counter() - t0 > 0.5:
                return None

        start = time.perf_counter()
        while GPIO.input(self.pin) == GPIO.LOW:
            pass
        header_low = (time.perf_counter() - start) * 1_000_000

        start = time.perf_counter()
        while GPIO.input(self.pin) == GPIO.HIGH:
            pass
        header_high = (time.perf_counter() - start) * 1_000_000

        if not (7500 < header_low < 10500):
            return None
        if 1800 < header_high < 2800:
            return "REPEAT"
        if not (3500 < header_high < 5500):
            return None

        bits = []
        for _ in range(32):
            start = time.perf_counter()
            while GPIO.input(self.pin) == GPIO.LOW:
                if (time.perf_counter() - start) * 1_000_000 > 2000:
                    return None
            start = time.perf_counter()
            while GPIO.input(self.pin) == GPIO.HIGH:
                if (time.perf_counter() - start) * 1_000_000 > 3000:
                    return None
            duration = (time.perf_counter() - start) * 1_000_000
            bits.append(1 if duration > 1000 else 0)

        def b2byte(b): return sum(bit << i for i, bit in enumerate(b))

        cmd     = b2byte(bits[16:24])
        cmd_inv = b2byte(bits[24:32])
        if (cmd + cmd_inv) & 0xFF != 0xFF:
            return None

        addr = b2byte(bits[0:8])
        return f"0x{(addr << 8 | cmd):04X}"

    def _loop(self):
        while self._running:
            try:
                code = self._decode_nec()
                if code is None or code == "REPEAT":
                    time.sleep(0.001)
                    continue

                now = time.time()
                if code == self._last_code and (now - self._last_time) < self.duplicate_gap:
                    continue
                self._last_code = code
                self._last_time = now

                action = self._keymap.get(code)
                if action and action in self._handlers:
                    log.info(f"IR: {code} → {action}")
                    try:
                        self._handlers[action]()
                    except Exception as e:
                        log.error(f"IRReceiver handler error ({action}): {e}")
                elif action:
                    log.debug(f"IR: {code} → {action} (sin handler registrado)")
                else:
                    log.debug(f"IR: código desconocido {code}")

            except Exception as e:
                log.error(f"IRReceiver loop error: {e}")
                time.sleep(0.1)