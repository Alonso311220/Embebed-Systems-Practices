# !/usr/bin/env python3
import RPi.GPIO as GPIO
from time import sleep
import threading

# Configuración de Pines (Basado en tus archivos de práctica)
PIN_LEDS = [12, 16, 18, 22, 24, 26, 32]
PIN_BCD  = [36, 38, 40, 37]

# Variables de control para las animaciones
stop_event = threading.Event()
current_thread = None

def _setup_gpio():
    """Inicializa los pines una sola vez"""
    if GPIO.getmode() is None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        for pin in PIN_LEDS + PIN_BCD:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

def _stop_current_animation():
    """Detiene cualquier hilo de marquesina activo antes de iniciar otro"""
    global stop_event, current_thread
    stop_event.set()
    if current_thread and current_thread.is_alive():
        current_thread.join(timeout=0.1)
    stop_event.clear()

def leds(num):
    """Enciende el led especificado (1-7), apagando los demás"""
    _setup_gpio()
    _stop_current_animation()
    
    # El índice es num-1 porque el arreglo empieza en 0
    idx = int(num) - 1
    for i, pin in enumerate(PIN_LEDS):
        if i == idx:
            GPIO.output(pin, GPIO.HIGH)
        else:
            GPIO.output(pin, GPIO.LOW)

def bcd(num):
    """Despliega el número en el display de siete segmentos (vía 74LS47)"""
    _setup_gpio()
    # No detenemos la animación aquí por si quieres ver BCD y marquesina a la vez, 
    # pero si interfieren, llama a _stop_current_animation()
    val = int(num)
    GPIO.output(36, GPIO.HIGH if (val & 1) else GPIO.LOW)
    GPIO.output(38, GPIO.HIGH if (val & 2) else GPIO.LOW)
    GPIO.output(40, GPIO.HIGH if (val & 4) else GPIO.LOW)
    GPIO.output(37, GPIO.HIGH if (val & 8) else GPIO.LOW)

def marquee(type='pingpong'):
    """Gestiona el inicio de los hilos de marquesina"""
    global current_thread
    _setup_gpio()
    _stop_current_animation()

    switcher = {
        'left'     : _marquee_left,
        'right'    : _marquee_right,
        'pingpong' : _marquee_pingpong
    }
    
    func = switcher.get(type)
    if func:
        current_thread = threading.Thread(target=func)
        current_thread.daemon = True
        current_thread.start()

def _marquee_left():
    delay = 0.2
    while not stop_event.is_set():
        for pin in PIN_LEDS:
            if stop_event.is_set(): break
            GPIO.output(pin, GPIO.HIGH)
            sleep(delay)
            GPIO.output(pin, GPIO.LOW)

def _marquee_right():
    delay = 0.2
    while not stop_event.is_set():
        for pin in reversed(PIN_LEDS):
            if stop_event.is_set(): break
            GPIO.output(pin, GPIO.HIGH)
            sleep(delay)
            GPIO.output(pin, GPIO.LOW)

def _marquee_pingpong():
    delay = 0.2
    while not stop_event.is_set():
        # Ida
        for pin in PIN_LEDS:
            if stop_event.is_set(): break
            GPIO.output(pin, GPIO.HIGH)
            sleep(delay)
            GPIO.output(pin, GPIO.LOW)
        # Vuelta (excluyendo extremos para fluidez)
        for pin in reversed(PIN_LEDS[1:-1]):
            if stop_event.is_set(): break
            GPIO.output(pin, GPIO.HIGH)
            sleep(delay)
            GPIO.output(pin, GPIO.LOW)
