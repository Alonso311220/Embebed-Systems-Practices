#!/usr/bin/env python3
"""
Marquesina infinita con apellidos de los integrantes del equipo.
LCD 16x2 via I2C con adaptador PCF8574 (direccion 0x27).
Practica 8 - Fundamentos de Sistemas Embebidos
"""

import smbus2
import time

# Configuracion del LCD
LCD_ADDR = 0x27
LCD_BUS  = 1

# Bits de control PCF8574 -> LCD
LCD_BACKLIGHT = 0x08
LCD_ENABLE    = 0x04
LCD_RS        = 0x01

# Comandos LCD
LCD_CLEAR        = 0x01
LCD_ENTRY_MODE   = 0x06
LCD_DISPLAY_ON   = 0x0C
LCD_FUNCTION_SET = 0x28
LCD_LINE1        = 0x80
LCD_LINE2        = 0xC0


class LCD:
    def __init__(self, addr=LCD_ADDR, bus=LCD_BUS):
        self.addr = addr
        self.bus  = smbus2.SMBus(bus)
        self._init()

    def _write_byte(self, data):
        self.bus.write_byte(self.addr, data | LCD_BACKLIGHT)

    def _pulse_enable(self, data):
        self._write_byte(data | LCD_ENABLE)
        time.sleep(0.0005)
        self._write_byte(data & ~LCD_ENABLE)
        time.sleep(0.0001)

    def _write4(self, data):
        self._write_byte(data)
        self._pulse_enable(data)

    def _send(self, data, mode):
        high = mode | (data & 0xF0)
        low  = mode | ((data << 4) & 0xF0)
        self._write4(high)
        self._write4(low)

    def command(self, cmd):
        self._send(cmd, 0x00)
        time.sleep(0.002)

    def write_char(self, ch):
        self._send(ord(ch), LCD_RS)

    def _init(self):
        time.sleep(0.05)
        for _ in range(3):
            self._write4(0x30)
            time.sleep(0.005)
        self._write4(0x20)
        time.sleep(0.005)
        self.command(LCD_FUNCTION_SET)
        self.command(LCD_DISPLAY_ON)
        self.command(LCD_CLEAR)
        self.command(LCD_ENTRY_MODE)

    def clear(self):
        self.command(LCD_CLEAR)

    def set_cursor(self, col, row):
        addr = LCD_LINE1 + col if row == 0 else LCD_LINE2 + col
        self.command(0x80 | addr)

    def print_line(self, text, row=0):
        """Imprime exactamente 16 caracteres en la fila indicada."""
        text = text[:16].ljust(16)
        self.set_cursor(0, row)
        for ch in text:
            self.write_char(ch)


# -------------------------------------------------------
# Apellidos de los integrantes separados por espacio
APELLIDOS = "Martinez Cuevas Pimentel"
# Velocidad del scroll: segundos entre cada desplazamiento
VELOCIDAD = 0.35
# -------------------------------------------------------

def main():
    lcd = LCD()
    lcd.clear()

    # Linea 2 fija
    lcd.print_line("FSE - Practica 8", row=1)

    # Texto circular: se añaden 16 espacios para que el texto
    # entre suavemente desde la derecha y salga por la izquierda
    marquee = APELLIDOS + " " * 16
    total   = len(marquee)
    pos     = 0

    print("Marquesina iniciada. Ctrl+C para salir.")
    try:
        while True:
            # Ventana de 16 caracteres sobre el texto circular
            ventana = ""
            for i in range(16):
                ventana += marquee[(pos + i) % total]

            lcd.print_line(ventana, row=0)
            pos = (pos + 1) % total
            time.sleep(VELOCIDAD)

    except KeyboardInterrupt:
        lcd.clear()
        print("Fin.")


if __name__ == "__main__":
    main()
