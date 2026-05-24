#!/usr/bin/env python3
"""
Actividad 4 - Marquesina de apellidos + temperatura DS18B20.
Linea 1: marquesina izquierda con apellidos de los integrantes.
Linea 2: temperatura en grados Celsius del sensor DS18B20.
LCD via I2C con adaptador PCF8574 (direccion 0x27).
Practica 8 - Fundamentos de Sistemas Embebidos
Integrantes: Martinez, Cuevas, Pimentel
"""

import smbus2
import time
import os
import glob

# -------------------------------------------------------
LCD_ADDR  = 0x27
LCD_BUS   = 1

APELLIDOS = "Martinez Cuevas Pimentel"
VELOCIDAD = 0.35   # segundos entre cada paso de scroll
TEMP_CADA = 10     # actualizar temperatura cada N pasos
# -------------------------------------------------------

LCD_BACKLIGHT = 0x08
LCD_ENABLE    = 0x04
LCD_RS        = 0x01

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

    def print_line(self, text, row=0, align='left'):
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


def find_sensor():
    base = '/sys/bus/w1/devices/'
    try:
        devices = glob.glob(base + '28-*')
        if devices:
            return devices[0] + '/w1_slave'
    except Exception:
        pass
    return None


def read_temp(sensor_path):
    try:
        with open(sensor_path, 'r') as f:
            lines = f.readlines()
        if lines[0].strip().endswith('YES'):
            temp_str = lines[1].split('t=')[1]
            return float(temp_str) / 1000.0
    except Exception:
        pass
    return None


def format_temp(temp):
    if temp is None:
        return "Temp: Error  "
    return "Temp: {:.1f} C".format(temp)


def main():
    lcd = LCD()
    lcd.clear()

    sensor_path = find_sensor()
    if sensor_path:
        print(f"Sensor DS18B20 encontrado: {sensor_path}")
    else:
        print("Sensor DS18B20 no encontrado, reintentando en bucle...")

    marquee = APELLIDOS + " " * 16
    total   = len(marquee)
    pos     = 0
    paso    = 0

    temp       = read_temp(sensor_path) if sensor_path else None
    temp_texto = format_temp(temp)
    lcd.print_line(temp_texto, row=1, align='left')

    print("Marquesina + temperatura iniciada. Ctrl+C para salir.")
    try:
        while True:
            # Linea 1: marquesina
            ventana = ""
            for i in range(16):
                ventana += marquee[(pos + i) % total]
            lcd.print_line(ventana, row=0)
            pos  = (pos + 1) % total
            paso += 1

            # Linea 2: temperatura cada TEMP_CADA pasos
            if paso % TEMP_CADA == 0:
                if not sensor_path:
                    sensor_path = find_sensor()
                temp       = read_temp(sensor_path) if sensor_path else None
                temp_texto = format_temp(temp)
                lcd.print_line(temp_texto, row=1, align='left')

            time.sleep(VELOCIDAD)

    except KeyboardInterrupt:
        lcd.clear()
        print("Fin.")


if __name__ == "__main__":
    main()
