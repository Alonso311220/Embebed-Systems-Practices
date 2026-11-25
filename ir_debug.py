"""
Herramienta de diagnóstico IR — corre directamente en la Pi
Muestra exactamente qué está recibiendo el sensor, sin filtros.

Uso:
    cd /home/pi/ProyectoFinal
    python3 ir_debug.py
"""
import time
import sys

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("ERROR: RPi.GPIO no disponible")
    sys.exit(1)

PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.IN)

# Timings NEC
_H_LOW_MIN,  _H_LOW_MAX  =  7_500, 10_500
_H_DATA_MIN, _H_DATA_MAX =  3_500,  5_500
_H_REP_MIN,  _H_REP_MAX  =  1_800,  2_800
_BIT_THRESH  = 1_000
_BIT_TIMEOUT = 4_000
_PLS_TIMEOUT = 4_000
_WAIT_S      = 1.0

print()
print("╔══════════════════════════════════════════════════╗")
print("║   IR DIAGNÓSTICO — Presiona botones del control  ║")
print("║   GPIO 18 · NEC extendido · Ctrl+C para salir   ║")
print("╚══════════════════════════════════════════════════╝")
print()
print("Esperando señal IR...\n")

def read_pulse_us(expected_state, timeout_us):
    """Mide cuánto tiempo dura el estado expected_state. Retorna microsegundos o None si timeout."""
    t = time.perf_counter()
    while GPIO.input(PIN) == expected_state:
        elapsed = (time.perf_counter() - t) * 1e6
        if elapsed > timeout_us:
            return None
    return (time.perf_counter() - t) * 1e6

count = 0
try:
    while True:
        # Esperar flanco bajada (inicio de trama)
        t0 = time.perf_counter()
        while GPIO.input(PIN) == GPIO.HIGH:
            if time.perf_counter() - t0 > _WAIT_S:
                break
        
        if GPIO.input(PIN) == GPIO.HIGH:
            continue  # timeout, sin señal

        # Medir LOW de cabecera
        low_us = read_pulse_us(GPIO.LOW, 15_000)
        if low_us is None:
            print(f"  ! LOW cabecera demasiado largo (>15ms) — ruido?")
            continue

        # Medir HIGH de cabecera
        high_us = read_pulse_us(GPIO.HIGH, 8_000)
        if high_us is None:
            print(f"  ! HIGH cabecera demasiado largo — LOW={low_us:.0f}us")
            continue

        count += 1
        
        # Clasificar cabecera
        is_data   = _H_LOW_MIN < low_us < _H_LOW_MAX and _H_DATA_MIN < high_us < _H_DATA_MAX
        is_repeat = _H_LOW_MIN < low_us < _H_LOW_MAX and _H_REP_MIN < high_us < _H_REP_MAX
        
        if not is_data and not is_repeat:
            print(f"  [{count:3d}] Cabecera INVALIDA  LOW={low_us:.0f}us  HIGH={high_us:.0f}us")
            print(f"         Esperado LOW: {_H_LOW_MIN}-{_H_LOW_MAX}us  HIGH: {_H_DATA_MIN}-{_H_DATA_MAX}us (datos)")
            continue

        if is_repeat:
            print(f"  [{count:3d}]  REPETIR  (LOW={low_us:.0f}us HIGH={high_us:.0f}us)")
            continue

        # Decodificar 32 bits
        bits = []
        ok   = True
        for b in range(32):
            # Esperar fin del LOW de separación
            dur = read_pulse_us(GPIO.LOW, _PLS_TIMEOUT)
            if dur is None:
                print(f"  [{count:3d}] Timeout bit {b} (LOW sep)")
                ok = False; break

            # Medir HIGH que codifica el bit
            dur = read_pulse_us(GPIO.HIGH, _BIT_TIMEOUT)
            if dur is None:
                print(f"  [{count:3d}] Timeout bit {b} (HIGH)")
                ok = False; break

            bits.append(1 if dur > _BIT_THRESH else 0)

        if not ok:
            continue

        def b2i(b): return sum(v << i for i, v in enumerate(b))
        addr_lo = b2i(bits[0:8])
        addr_hi = b2i(bits[8:16])
        cmd     = b2i(bits[16:24])
        cmd_inv = b2i(bits[24:32])

        chk = (cmd + cmd_inv) & 0xFF

        # NEC extendido vs estándar
        is_ext = (addr_lo + addr_hi) & 0xFF != 0xFF
        if is_ext:
            code = f"0x{(addr_hi << 16) | (addr_lo << 8) | cmd:06X}"
        else:
            code = f"0x{(addr_lo << 8 | cmd):04X}"

        chk_ok = "OK" if chk == 0xFF else "X"
        proto  = "NEC-EXT" if is_ext else "NEC-STD"

        print(f"  [{count:3d}] {chk_ok} {proto}  código={code}  "
              f"addr=0x{addr_lo:02X}+0x{addr_hi:02X}  cmd=0x{cmd:02X}/0x{cmd_inv:02X}  "
              f"chk={'OK' if chk==0xFF else f'FAIL(0x{chk:02X})'}")

        if chk != 0xFF:
            print(f" Bits: {' '.join(str(b) for b in bits)}")

except KeyboardInterrupt:
    print(f"\n  Total tramas recibidas: {count}")
    print("  Saliendo...\n")
finally:
    GPIO.cleanup()