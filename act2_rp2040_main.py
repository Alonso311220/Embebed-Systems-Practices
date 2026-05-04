# ## #############################################################
#
# act2_rp2040_main.py
#
# Author:  Mauricio Matamoros (modificado)
# License: MIT
# Date:    2024.05.02
#
# IMPORTANT: Save in RP2040 as main.py
#            Also upload i2cslave.py to the RP2040
#
# Actividad 2:
#   Igual que la Actividad 1, pero además el RP2040 responde al
#   master con la potencia REAL modulada: el tiempo de encendido
#   equivalente en milisegundos (ton_ms) dentro del semiciclo.
#
# Cálculo de potencia real:
#   A 60 Hz el semiciclo dura T_half = 1/(2·60) = 8.333 ms.
#   La SM corre a 5000 Hz → cada paso dura dt = 1/5000 = 0.200 ms.
#   Con un delay de N pasos, el TRIAC se activa en:
#       t_on = T_half - N·dt  [ms]
#   La potencia equivalente (fracción del semiciclo que el TRIAC
#   conduce) es:
#       P_real [%] = (t_on / T_half) × 100
#               = (1 − N / MAX_DELAY) × 100
#
#   El valor que se devuelve al Raspberry Pi es t_on en ms,
#   que permite verificar el tiempo real de conducción.
#
# ## ############################################################

import machine
import ustruct
import rp2
from machine import Pin
from utime import sleep_ms, sleep_us
from i2cslave import I2CSlave

# ---------------------------------------------------------------
# Constantes de tiempo
# ---------------------------------------------------------------
FREQ_SM   = 5_000          # Hz de la state machine
DT_MS     = 1000.0 / FREQ_SM   # ms por instrucción = 0.200 ms
T_HALF_MS = 1000.0 / (2 * 60)  # semiciclo a 60 Hz = 8.333 ms
MAX_DELAY = 41              # pasos máximos = floor(T_HALF_MS / DT_MS)

# ---------------------------------------------------------------
# Pines
# ---------------------------------------------------------------
zxpin = Pin(2, Pin.IN)
trpin = Pin(3, Pin.OUT)

# ---------------------------------------------------------------
# PIO State Machine (idéntica a Actividad 1)
# ---------------------------------------------------------------
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def dimmer():
    set(pins, 0)
    pull()
    mov(x, osr)

    label('waitzx')
    wrap_target()

    wait(0, pin, 0)

    pull(noblock)
    mov(x, osr)
    mov(y, x)

    wait(1, pin, 0)
    nop()           [4]

    label('delay')
    jmp(y_dec, 'delay')

    set(pins, 1)
    set(pins, 0)

    jmp('waitzx')
    wrap()

sm = rp2.StateMachine(
    0, dimmer, freq=FREQ_SM,
    in_base=zxpin, set_base=trpin
)
sm.active(1)
sm.put(MAX_DELAY)

# ---------------------------------------------------------------
# I²C Slave
# ---------------------------------------------------------------
i2c = I2CSlave(id=0, address=0x0A, sda=0, scl=1)
print('RP2040 listo — esclavo I2C 0x0A')

# ---------------------------------------------------------------
# Funciones de conversión
# ---------------------------------------------------------------
def power_to_delay(power_pct: float) -> int:
    """Porcentaje (0-100) → pasos de delay para la SM."""
    p = max(0.0, min(100.0, power_pct))
    return round(MAX_DELAY * (1.0 - p / 100.0))

def delay_to_ton_ms(delay: int) -> float:
    """
    Tiempo de conducción real del TRIAC en ms.
    t_on = T_half - delay * dt
    Con delay=0 → t_on = T_half (100 %)
    Con delay=MAX_DELAY → t_on ≈ 0 (0 %)
    """
    return T_HALF_MS - delay * DT_MS

def delay_to_power_pct(delay: int) -> float:
    """Delay → porcentaje de potencia real (0–100 %)."""
    return (delay_to_ton_ms(delay) / T_HALF_MS) * 100.0

# ---------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------
def main():
    sm.put(MAX_DELAY)

    while True:
        # Esperar 4 bytes (float potencia deseada)
        while i2c.rxBufferCount() < 4:
            sleep_us(10)

        data = i2c.read()
        if len(data) < 4:
            continue

        (power_pct,) = ustruct.unpack('<f', data)
        power_pct = max(0.0, min(100.0, power_pct))

        # Calcular delay y actualizar SM
        delay    = power_to_delay(power_pct)
        ton_ms   = delay_to_ton_ms(delay)
        real_pct = delay_to_power_pct(delay)

        sm.put(delay)

        # Responder con t_on en ms (float LE, 4 bytes)
        response = ustruct.pack('<f', ton_ms)
        i2c.write(response)

        print(f'Solicitado: {power_pct:.1f}%  '
              f'| Delay: {delay} pasos  '
              f'| t_on: {ton_ms:.3f} ms  '
              f'| Potencia real: {real_pct:.1f}%')

if __name__ == '__main__':
    main()
