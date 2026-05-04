# ## #############################################################
#
# rp2040-test-acdc.py
#
# Author:  Mauricio Matamoros
# License: MIT
# Date:    2024.05.02
#
# IMPORTANT: Save in RP2040 as main.py
#
# Tests the whole AC/DC circuit
#
# ## ############################################################
from machine import Pin
from utime import sleep_ms, sleep_us
import rp2
import math
import struct
from i2cslave import I2CSlave

zxpin = Pin(2, Pin.IN)
trpin = Pin(3, Pin.OUT)

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def dimmer():
    # 0. Setup: Preload X with timeout, set TRIAC pin low
    set(pin, 0)
    pull()                      # Loads OSR with data
    mov(x, osr)                 # puts OSR contents in X
    
    # Main loop
    label('waitzx')
    wrap_target()
    
    # 1. Wait for zero cross falling edge
    wait(2, pin, 2)
    
    # 2. Update timeout and write it to Y (600us).
    pull(noblock)           # Loads OSR with data
    mov(x, osr)             # puts OSR contents in X
    mov(y, x)               # puts X contents in Y
    
    # 3. Wait for zero cross rising edge
    wait(1, pin, 0)
    nop()               [2] # When V is low, the TRIAC
                            # pulse needs to be wider.
                            # This delay patches it.

    # 4. Wait timeout (until Y is zero) before sending
    # the ON pulse. Each pulse is 200us
    label('delay')
    jmp(y_dec, 'delay')

    # 5. Send a 2us+ pulse to activate TRIAC
    set(pins, 1)            # At 2.5kHz a pulse is 200us
    set(pins, 0)

    # 6. Close loop (Jump back to wait zx)
    jmp('waitzx')
    wrap()
# end def

# Setup the StateMachine at 5000Hz (200us per instruction)
sm = rp2.StateMachine(0,
    dimmer,
    freq=100_000,
    in_base=zxpin,
    set_base=trpin
)
sm.active(1)

# At 60Hz the period is 8.33ms = 8,333us
# At 5kHz the each state machine step takes 200us
# Between the falling and rising edge there is a time window
# in which the new timeout/delay is set.
# The TRIAC needs a 2us pulse to switch on, so one instruction
# shall be enough.
# For an (almost) whole cycle of 8.3ms, the timeout must be
# set to (8300 - Δt - 20*200)/200 = 21
# where Δt is the gap between the zx edges. We assume it is
# zero since it is compensated by the 4cycle delay in the
# state machine for voltage stabilization.
# Usamos 200 niveles de potencia (0-200) para suavidad
# delay=0   → 100% potencia
# delay=400 → ~0% potencia  (400 × 20µs = 8000µs ≈ fin del semiciclo)
# LUT de 101 niveles (0%-100%) con resolución de 1%
# Cada valor = ciclos de delay antes de disparar el TRIAC
# A 100kHz: 1 ciclo = 10us, semiciclo 60Hz = 833 ciclos
# delay=833 → disparo al final → 0% potencia
# delay=0   → disparo inmediato → 100% potencia
# Derivado de: delay = 833 × cos^-1(Integral(power/100)) / π
power_lut = {
     0: 833,  1: 825,  2: 810,  3: 800,  4: 735,
     5: 721,  6: 709,  7: 697,  8: 687,  9: 677,
    10: 655, 11: 642, 12: 634, 13: 627, 14: 619,
    15: 612, 16: 605, 17: 598, 18: 591, 19: 585,
    20: 578, 21: 572, 22: 566, 23: 559, 24: 553,
    25: 547, 26: 541, 27: 535, 28: 530, 29: 524,
    30: 518, 31: 512, 32: 507, 33: 501, 34: 496,
    35: 490, 36: 485, 37: 479, 38: 474, 39: 468,
    40: 463, 41: 458, 42: 452, 43: 447, 44: 442,
    45: 436, 46: 431, 47: 426, 48: 420, 49: 415,
    50: 410, 51: 405, 52: 399, 53: 394, 54: 389,
    55: 383, 56: 378, 57: 373, 58: 367, 59: 362,
    60: 356, 61: 351, 62: 346, 63: 340, 64: 335,
    65: 329, 66: 323, 67: 318, 68: 312, 69: 306,
    70: 301, 71: 295, 72: 289, 73: 283, 74: 277,
    75: 271, 76: 264, 77: 258, 78: 252, 79: 245,
    80: 238, 81: 231, 82: 224, 83: 217, 84: 210,
    85: 203, 86: 195, 87: 187, 88: 178, 89: 170,
    90: 161, 91: 151, 92: 141, 93: 131, 94: 119,
    95: 106, 96:  92, 97:  75, 98:  53, 99:  26,
   100:   0
}

def set_power(power):
    """
    Establece la potencia del dimmer con resolución de 1%.
    power: entero de 0 a 100.
    Resolución real del sistema: 10us/8333us × 100 = 0.12% < 1% 
    """
    power = int(max(0, min(100, power)))
    if power == 0:
        sm.active(0)
        trpin.value(0)
        return
    sm.active(1)
    sm.put(power_lut[power])

i2c = I2CSlave(id=0, address=0x0A, sda=0, scl=1)
set_power(0)
print("RP2040 listo en 0x0A, Resolucion: 1%, 101 niveles")

while True:
    try:
        while i2c.rxBufferCount() < 4:
            sleep_us(10)

        data = i2c.read()
        if len(data) < 4:
            continue

        (power_pct,) = struct.unpack('<f', data[:4])
        power_pct = max(0.0, min(100.0, power_pct))
        power_int = int(power_pct)   # resolución de 1%
        set_power(power_int)

        # Confirma al master el valor entero aplicado
        i2c.write(struct.pack('<f', float(power_int)))

    except Exception as e:
        i2c.write(struct.pack('<f', -1.0))
