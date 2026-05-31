#!/usr/bin/env python3
"""
identificador.py  —  Captura de teclas IR para SmartTV Kiosk
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Soporta:
  • NEC estándar   (dirección 8-bit)
  • NEC extendido  (dirección 16-bit) ← Motorola Google TV
  • Fallback por votación: captura la tecla 3 veces y usa
    el código más repetido — elimina hashes RAW inestables

Uso:
    cd /home/pi/ProyectoFinal
    python3 remote/identificador.py

Genera: remote/ir_keymap.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import RPi.GPIO as GPIO
import time
import json
import os
from datetime import datetime
from collections import Counter

# ── Config ─────────────────────────────────────────────────
IR_PIN      = 18
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "ir_keymap.json")

# Timings NEC (µs)
_H_LOW_MIN,  _H_LOW_MAX  =  7_500, 10_500
_H_DATA_MIN, _H_DATA_MAX =  3_500,  5_500
_H_REP_MIN,  _H_REP_MAX  =  1_800,  2_800
_BIT_THRESH  = 1_000
_BIT_TIMEOUT = 3_500
_PLS_TIMEOUT = 2_500

ACCIONES = [
    "nav_up","nav_down","nav_left","nav_right","nav_ok",
    "volume_up","volume_down","mute",
    "mode_video","mode_image","mode_audio",
    "usb_1","usb_2","usb_3","usb_4",
    "stop","play","next","prev",
    "num_0","num_1","num_2","num_3","num_4",
    "num_5","num_6","num_7","num_8","num_9",
]

GPIO.setmode(GPIO.BCM)
GPIO.setup(IR_PIN, GPIO.IN)

# ── Decodificador NEC estándar + extendido ─────────────────

def _wait_edge(state, timeout=0.6):
    t = time.perf_counter()
    while GPIO.input(IR_PIN) == state:
        if time.perf_counter() - t > timeout:
            return False
    return True

def decode_nec():
    """
    Retorna:
      '0xAABBCC'  → NEC extendido (addr16 + cmd8)
      '0xAABB'    → NEC estándar  (addr8  + cmd8)
      'REPEAT'    → tecla mantenida
      None        → no reconocido
    """
    # Espera flanco de bajada
    if not _wait_edge(GPIO.HIGH, timeout=0.8):
        return None

    # Header LOW
    t = time.perf_counter()
    while GPIO.input(IR_PIN) == GPIO.LOW:
        pass
    low_us = (time.perf_counter() - t) * 1e6
    if not (_H_LOW_MIN < low_us < _H_LOW_MAX):
        return None

    # Header HIGH
    t = time.perf_counter()
    while GPIO.input(IR_PIN) == GPIO.HIGH:
        pass
    high_us = (time.perf_counter() - t) * 1e6

    if _H_REP_MIN < high_us < _H_REP_MAX:
        return "REPEAT"
    if not (_H_DATA_MIN < high_us < _H_DATA_MAX):
        return None

    # 32 bits LSB-first
    bits = []
    for _ in range(32):
        t = time.perf_counter()
        while GPIO.input(IR_PIN) == GPIO.LOW:
            if (time.perf_counter() - t) * 1e6 > _PLS_TIMEOUT:
                return None
        t = time.perf_counter()
        while GPIO.input(IR_PIN) == GPIO.HIGH:
            if (time.perf_counter() - t) * 1e6 > _BIT_TIMEOUT:
                return None
        bits.append(1 if (time.perf_counter() - t) * 1e6 > _BIT_THRESH else 0)

    def b2i(b): return sum(v << i for i, v in enumerate(b))

    addr_lo  = b2i(bits[0:8])
    addr_hi  = b2i(bits[8:16])
    cmd      = b2i(bits[16:24])
    cmd_inv  = b2i(bits[24:32])

    # Validar comando
    if (cmd + cmd_inv) & 0xFF != 0xFF:
        return None

    # NEC extendido: addr_lo y addr_hi son los dos bytes de la dirección
    # (NO son complementos entre sí — esa es la diferencia con NEC estándar)
    if (addr_lo + addr_hi) & 0xFF != 0xFF:
        # Extendido: dirección = addr_hi<<8 | addr_lo
        code = (addr_hi << 16) | (addr_lo << 8) | cmd
        return f"0x{code:06X}"
    else:
        # Estándar: dirección = addr_lo
        code = (addr_lo << 8) | cmd
        return f"0x{code:04X}"


def capturar_con_votacion(n=3, timeout=8):
    """
    Pide n lecturas de la misma tecla y retorna el código más frecuente.
    Elimina hashes RAW inestables.
    """
    lecturas = []
    intentos = 0
    max_intentos = n * 4

    while len(lecturas) < n and intentos < max_intentos:
        intentos += 1
        code = decode_nec()
        if code and code != "REPEAT":
            lecturas.append(code)
            print(f"      lectura {len(lecturas)}/{n}: {code}")
            time.sleep(0.15)

    if not lecturas:
        return None

    # El código más frecuente gana
    winner, count = Counter(lecturas).most_common(1)[0]
    return winner if count >= 1 else None


# ── Interfaz de consola ────────────────────────────────────

def cls():
    os.system("clear")

def print_header():
    print("\033[1;36m")
    print("╔══════════════════════════════════════════════════════╗")
    print("║   🍓  SmartTV — Identificador de teclas IR           ║")
    print("║   Control: Motorola Google TV  ·  Protocolo NEC Ext  ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("\033[0m")

def print_mapa(mapa):
    if not mapa:
        return
    print("\n  \033[1mTeclas capturadas:\033[0m")
    print("  " + "─"*46)
    for code, accion in mapa.items():
        print(f"  \033[33m{code:<20}\033[0m  →  \033[36m{accion}\033[0m")
    print()

def guardar(mapa):
    data = {
        "generated": datetime.now().isoformat(),
        "sensor_pin": IR_PIN,
        "protocol": "NEC_EXT",
        "keymap": {k: v for k, v in mapa.items() if v}
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n\033[1;32m✓ Guardado en {OUTPUT_FILE}\033[0m")
    print(f"  {len(data['keymap'])} teclas asignadas\n")


# ── Main ────────────────────────────────────────────────────

def main():
    mapa = {}

    # Cargar keymap existente si hay
    if os.path.exists(OUTPUT_FILE):
        try:
            data = json.loads(open(OUTPUT_FILE).read())
            mapa = data.get("keymap", {})
            print(f"\n  Keymap existente cargado ({len(mapa)} teclas)")
            time.sleep(1)
        except Exception:
            pass

    try:
        while True:
            cls()
            print_header()
            print_mapa(mapa)

            print("  \033[33mApunta el control al sensor y presiona una tecla...\033[0m")
            print("  \033[90mSe capturará 3 veces para asegurar consistencia\033[0m")
            print("  \033[90mCtrl+C para guardar y salir\033[0m\n")

            # Captura con votación (3 lecturas)
            print("  Esperando primera lectura...")
            code = capturar_con_votacion(n=3)

            if code is None:
                print("  \033[31m✗ No se pudo decodificar. Intenta de nuevo.\033[0m")
                time.sleep(1.5)
                continue

            cls()
            print_header()
            print_mapa(mapa)

            # Si ya está en el mapa, mostrar y continuar
            if code in mapa:
                print(f"  \033[33m⚡ Código:\033[0m \033[1m{code}\033[0m  "
                      f"→  ya asignado como \033[36m{mapa[code]}\033[0m\n")
                print("  (presiona otra tecla o Ctrl+C para salir)")
                time.sleep(2)
                continue

            print(f"  \033[1;32m✔ Código estable:\033[0m  \033[1;37m{code}\033[0m\n")

            # Mostrar acciones disponibles
            cols = 4
            print("  Acciones disponibles:")
            for i, a in enumerate(ACCIONES):
                end = "\n" if (i+1) % cols == 0 else "  "
                print(f"  \033[36m{a:<18}\033[0m", end=end)
            print("\n")

            try:
                accion = input(f"  Acción para {code} (Enter = omitir): ").strip()
            except EOFError:
                continue

            if accion == "":
                mapa[code] = ""
                print("  \033[90mOmitida\033[0m")
            else:
                mapa[code] = accion
                print(f"  \033[32m✔ {code} → {accion}\033[0m")

            time.sleep(0.6)

    except KeyboardInterrupt:
        print("\n\n  Saliendo...")
    finally:
        GPIO.cleanup()
        guardar(mapa)


if __name__ == "__main__":
    main()