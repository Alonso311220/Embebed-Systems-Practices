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
power_lut = {
     0: 833,
     1: 825,
     2: 810,
     3: 800,
     4: 735,
     5: 721,
     6: 709,
     7: 697,
     8: 687,
     9: 677,
    10: 655,
    11: 757,
    12: 642,
    13: 634,
    14: 627,
    15: 619,
    16: 612,
    17: 605,
    18: 598,
    19: 591,
    20: 585,
    21: 578,
    22: 572,
    23: 566,
    24: 559,
    25: 553,
    26: 547,
    27: 541,
    28: 535,
    29: 530,
    30: 524,
    31: 518,
    32: 512,
    33: 507,
    34: 501,
    35: 496,
    36: 490,
    37: 485,
    38: 479,
    39: 474,
    40: 468,
    41: 463,
    42: 458,
    43: 452,
    44: 447,
    45: 442,
    46: 436,
    47: 431,
    48: 426,
    49: 420,
    50: 415,
    51: 410,
    52: 405,
    53: 399,
    54: 394,
    55: 389,
    56: 383,
    57: 378,
    58: 373,
    59: 367,
    60: 362,
    61: 356,
    62: 351,
    63: 346,
    64: 340,
    65: 335,
    66: 329,
    67: 323,
    68: 318,
    69: 312,
    70: 306,
    71: 301,
    72: 295,
    73: 289,
    74: 283,
    75: 277,
    76: 271,
    77: 264,
    78: 258,
    79: 252,
    80: 245,
    81: 238,
    82: 231,
    83: 224,
    84: 217,
    85: 210,
    86: 203,
    87: 195,
    88: 187,
    89: 178,
    90: 170,
    91: 161,
    92: 151,
    93: 141,
    94: 131,
    95: 119,
    96: 106,
    97: 92,
    98: 75,
    99: 53,
    100: 0
}
#POWER_MIN = 0
#POWER_MAX = 100
#MAX_DELAY = 800
keys = sorted(power_lut.keys())

def set_power(power):
    power = int(max(0, min(100, power)))
    if power <= 0:
        sm.active(0)          # detiene la SM
        trpin.value(0)        # fuerza el pin del TRIAC a bajo
        return
    if power >= 100:
        sm.active(1)
        sm.put(0)
        return
    sm.active(1)
    sm.put(power_lut[power])

#para la comunicación I2C
i2c = I2CSlave(id=0, address=0x0A, sda=0, scl=1)
sm.put(830)
print("RP2040 listo en 0x0A")

while True:
    try:
        while i2c.rxBufferCount() < 4:
            sleep_us(10)

        data = i2c.read()

        if len(data) < 4:
            continue

        (power_pct,) = struct.unpack('<f', data[:4])

        power_pct = max(0.0, min(100.0, power_pct))
        power_int = int(power_pct)

        set_power(power_int)

    except Exception as e:
        i2c.write(struct.pack('<f', -1.0))
    
