"""
remote/input.py  —  Lector IR para SmartTV Kiosk
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sensor  : KY-022 en GPIO 18 (BCM) · Pin físico 12
Protocolo: NEC extendido (Motorola / Google TV)

Uso desde menu.py:
    from remote.input import IRInput
    ir = IRInput()
    ir.on("nav_up",   lambda: menu.nav_up())
    ir.on("nav_down", lambda: menu.nav_down())
    ir.on("nav_ok",   lambda: menu.select())
    ir.start()

Prueba standalone:
    cd /home/pi/ProyectoFinal && python3 -m remote.input
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger("ir.input")

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except ImportError:
    _HAS_GPIO = False
    log.warning("RPi.GPIO no disponible — modo SIMULADO activo")

# ── Timings NEC en microsegundos ─────────────────────────────────────────
# Pulso inicial LOW (marca de inicio de trama)
_H_LOW_MIN,  _H_LOW_MAX  =  7_500, 10_500   # ~9ms nominal
# Pulso HIGH que sigue al LOW de inicio
_H_DATA_MIN, _H_DATA_MAX =  3_500,  5_500   # ~4.5ms → trama de datos
_H_REP_MIN,  _H_REP_MAX  =  1_800,  2_800   # ~2.25ms → repetición
# Umbral para distinguir bit 0 (562µs HIGH) de bit 1 (1687µs HIGH)
_BIT_THRESH  = 1_000
# Timeouts de seguridad para no bloquearse si la señal es inválida
_BIT_TIMEOUT = 3_000   # tiempo máx esperando un cambio de flanco en un bit
_PLS_TIMEOUT = 2_000   # tiempo máx esperando el LOW inicial de cada bit
_WAIT_S      = 0.5     # timeout esperando el inicio de trama

_KEYMAP_DEFAULT = Path(__file__).parent / "ir_keymap.json"


class IRInput:
    def __init__(
        self,
        keymap_path: str | Path = _KEYMAP_DEFAULT,
        pin: int = 18,
        repeat_gap: float = 0.28,
    ):
        self.pin        = pin
        self.repeat_gap = repeat_gap
        self._keymap: dict[str, str] = {}
        self._handlers: dict[str, list[Callable]] = {}
        self._thread: threading.Thread | None = None
        self._running   = False
        self._last_code = ""
        self._last_time = 0.0

        self._load_keymap(keymap_path)

        if _HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.IN)

    # ── API pública ──────────────────────────────────────────────────────

    def on(self, action: str, callback: Callable) -> "IRInput":
        self._handlers.setdefault(action, []).append(callback)
        return self

    def start(self) -> "IRInput":
        if self._running:
            return self
        self._running = True
        target = self._loop_gpio if _HAS_GPIO else self._loop_simulate
        self._thread = threading.Thread(
            target=target, daemon=True, name="ir-listener"
        )
        self._thread.start()
        log.info("IRInput iniciado %s", "(GPIO)" if _HAS_GPIO else "(SIMULADO)")
        return self

    def stop(self):
        self._running = False
        if _HAS_GPIO:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    # ── Carga de keymap ──────────────────────────────────────────────────

    def _load_keymap(self, path: str | Path):
        path = Path(path)
        if not path.exists():
            log.error("Keymap no encontrado: %s", path)
            return
        try:
            data = json.loads(path.read_text())
            self._keymap = data.get("keymap", {})
            log.info("Keymap cargado: %d teclas desde %s", len(self._keymap), path)
        except Exception as e:
            log.error("Error leyendo keymap: %s", e)

    # ── Decodificador NEC (extendido + estándar) ─────────────────────────

    def _decode_nec(self) -> str | None:
        """
        Decodifica una trama NEC completa de 32 bits.

        El KY-022 (receptor activo-bajo) invierte la señal:
          - Reposo      → GPIO HIGH
          - Pulso IR    → GPIO LOW

        Flujo de una trama NEC:
          1. Cabecera LOW  (~9 ms)   ← inicio de burst
          2. Cabecera HIGH (~4.5 ms) ← datos  |  (~2.25 ms) ← repetición
          3. 32 bits: cada bit = LOW breve + HIGH variable
                bit 0 → HIGH ~562 µs
                bit 1 → HIGH ~1687 µs
        """

        # 1. Esperar a que la línea baje (inicio de trama)
        t0 = time.perf_counter()
        while GPIO.input(self.pin) == GPIO.HIGH:
            if time.perf_counter() - t0 > _WAIT_S:
                return None   # timeout — sin señal

        # 2. Medir el pulso LOW de cabecera
        t_start = time.perf_counter()
        while GPIO.input(self.pin) == GPIO.LOW:
            pass                                  # esperar flanco subida
        low_us = (time.perf_counter() - t_start) * 1e6

        if not (_H_LOW_MIN < low_us < _H_LOW_MAX):
            return None   # no es cabecera NEC válida

        # 3. Medir el pulso HIGH que clasifica la trama
        t_start = time.perf_counter()
        while GPIO.input(self.pin) == GPIO.HIGH:
            pass                                  # esperar flanco bajada
        high_us = (time.perf_counter() - t_start) * 1e6

        if _H_REP_MIN < high_us < _H_REP_MAX:
            return "REPEAT"

        if not (_H_DATA_MIN < high_us < _H_DATA_MAX):
            return None   # high desconocido

        # 4. Decodificar los 32 bits de datos
        bits: list[int] = []
        for _ in range(32):
            # a) Esperar el LOW de separación entre bits
            t_start = time.perf_counter()
            while GPIO.input(self.pin) == GPIO.HIGH:
                if (time.perf_counter() - t_start) * 1e6 > _PLS_TIMEOUT:
                    return None   # timeout — trama truncada

            # b) Esperar el LOW de este bit (duración fija ~562 µs, ignorada)
            while GPIO.input(self.pin) == GPIO.LOW:
                if (time.perf_counter() - t_start) * 1e6 > _PLS_TIMEOUT:
                    return None

            # c) Medir el HIGH que codifica 0 o 1
            t_bit = time.perf_counter()
            while GPIO.input(self.pin) == GPIO.HIGH:
                if (time.perf_counter() - t_bit) * 1e6 > _BIT_TIMEOUT:
                    return None
            bit_high_us = (time.perf_counter() - t_bit) * 1e6

            bits.append(1 if bit_high_us > _BIT_THRESH else 0)

        # 5. Reconstruir los 4 bytes (LSB primero en NEC)
        def b2i(b: list[int]) -> int:
            return sum(v << i for i, v in enumerate(b))

        addr_lo = b2i(bits[0:8])
        addr_hi = b2i(bits[8:16])
        cmd     = b2i(bits[16:24])
        cmd_inv = b2i(bits[24:32])

        # Validar integridad: cmd y cmd_inv deben sumar 0xFF
        if (cmd + cmd_inv) & 0xFF != 0xFF:
            log.debug("NEC checksum fallo: cmd=0x%02X cmd_inv=0x%02X", cmd, cmd_inv)
            return None

        # NEC extendido: addr_lo y addr_hi NO son complementos → dirección 16-bit
        if (addr_lo + addr_hi) & 0xFF != 0xFF:
            code = (addr_hi << 16) | (addr_lo << 8) | cmd
            return f"0x{code:06X}"

        # NEC estándar: dirección 8-bit
        return f"0x{(addr_lo << 8 | cmd):04X}"

    # ── Loops ────────────────────────────────────────────────────────────

    def _loop_gpio(self):
        """Loop principal del hilo GPIO. Decodifica y despacha acciones."""
        log.info("Escuchando IR en GPIO %d (BCM)...", self.pin)
        while self._running:
            try:
                code = self._decode_nec()
                if code is None:
                    # Sin señal o trama inválida — pequeña pausa para no saturar CPU
                    time.sleep(0.001)
                elif code == "REPEAT":
                    # Repetición de la última tecla mantenida: ignorar
                    # (el rate de repetición ya está controlado por repeat_gap en _process)
                    time.sleep(0.001)
                else:
                    self._process(code)
            except Exception as e:
                log.error("Loop IR error: %s", e)
                time.sleep(0.05)

    def _process(self, code: str):
        """
        Convierte un código NEC en acción y llama a los handlers registrados.
        Filtra repeticiones rápidas (anti-rebote por tiempo).
        """
        now = time.time()
        if code == self._last_code and (now - self._last_time) < self.repeat_gap:
            return   # misma tecla muy seguida → ignorar

        self._last_code = code
        self._last_time = now

        action = self._keymap.get(code)
        if action:
            log.info("IR ▶  %-25s → %s", code, action)
            for cb in self._handlers.get(action, []):
                try:
                    cb()
                except Exception as e:
                    log.error("Handler '%s' error: %s", action, e)
        else:
            log.warning("IR ?  %s  (sin asignar en keymap)", code)

    # ── Modo simulado (sin GPIO) ─────────────────────────────────────────

    def _loop_simulate(self):
        """
        Modo de prueba sin hardware: escribe el nombre de una acción
        y Enter para simular la pulsación del botón correspondiente.
        """
        actions = sorted(set(self._keymap.values()))
        print("\n" + "─" * 52)
        print("  MODO SIMULADO — escribe una acción y Enter")
        print("  Acciones disponibles:")
        for a in actions:
            print(f"    {a}")
        print("─" * 52 + "\n")

        while self._running:
            try:
                action = input("  acción > ").strip()
                if not action:
                    continue
                handlers = self._handlers.get(action, [])
                if handlers:
                    log.info("SIM ▶  %s", action)
                    for cb in handlers:
                        cb()
                else:
                    print(f"  Acción '{action}' no tiene handler registrado")
            except (EOFError, KeyboardInterrupt):
                break


# ── Standalone ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║   🍓  SmartTV — Prueba de sensor IR              ║")
    print("║   Presiona teclas del control · Ctrl+C = salir   ║")
    print("╚══════════════════════════════════════════════════╝\n")

    ir = IRInput()

    if ir._keymap:
        print("  Teclas registradas:")
        for code, action in ir._keymap.items():
            print(f"    {code:28s} → \033[36m{action}\033[0m")
        print()

    def show(action):
        return lambda: print(f"\n  \033[1;32m✔ ACCIÓN:\033[0m \033[1m{action}\033[0m\n")

    for action in set(ir._keymap.values()):
        ir.on(action, show(action))

    _orig_process = ir._process
    def _patched(code):
        if code not in ir._keymap:
            print(f"\n  \033[33m⚡ Sin asignar:\033[0m {code}\n")
        _orig_process(code)
    ir._process = _patched

    try:
        ir.start()
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n  Saliendo...\n")
    finally:
        ir.stop()