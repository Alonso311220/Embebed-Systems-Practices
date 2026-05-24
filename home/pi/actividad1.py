#!/usr/bin/env python3
"""
Actividad 1 - Muestra nombres de los integrantes en LCD 16x2.
LCD via I2C con adaptador PCF8574 (direccion 0x27).
Practica 8 - Fundamentos de Sistemas Embebidos
Integrantes: Alonso, Dalia, Alondra
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

    def print_line(self, text, row=0, align='center'):
        text = text[:16]
        if align == 'center':
            text = text.center(16)
        elif align == 'right':
            text = text.rjust(16)
        else:
            text = text.ljust(16)
        self.set_cursor(0, row)
        for ch in text:
            self.write_char(ch)


def main():
    lcd = LCD()
    lcd.clear()

    # Linea 1: nombres centrados
    lcd.print_line("Alonso Dalia", row=0, align='center')

    # Linea 2: tercer integrante centrado
    lcd.print_line("Alondra", row=1, align='center')

    print("Nombres mostrados en el LCD.")

    # Mantener el display encendido indefinidamente
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        lcd.clear()
        print("Fin.")


if __name__ == "__main__":
    main()
