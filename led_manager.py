import RPi.GPIO as GPIO
from time import sleep
import threading
from flask import Flask, jsonify

# =========================
# CONFIGURACIÓN
# =========================

PIN_LEDS = [18, 23, 24, 25, 8, 7, 12]
PIN_BCD  = [16, 20, 21, 26]

stop_event = threading.Event()
current_thread = None
base_delay = 0.5

# Estado global
state = {
    "mode": "En espera",
    "marquee_type": None,
    "speed": 0.5,
    "active_led": None,
    "bcd_value": None,
    "current_led": None #este lo usa el html para brillar
}

# =========================
# GPIO SETUP
# =========================

def _setup_gpio():
    if GPIO.getmode() is None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        for pin in PIN_LEDS:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

        for pin in PIN_BCD:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

def _stop_current_animation():
    global current_thread
    if current_thread and current_thread.is_alive():
        stop_event.set()
        current_thread.join()
    stop_event.clear()

# =========================
# ANIMACIONES
# =========================
def _marquee_left():
    while not stop_event.is_set():
        for i in range(len(PIN_LEDS)):
            if stop_event.is_set(): break
            
            # ACTUALIZAMOS EL ESTADO ANTES DEL SLEEP
            state["current_led"] = i + 1 
            
            GPIO.output(PIN_LEDS[i], GPIO.HIGH)
            sleep(base_delay)
            GPIO.output(PIN_LEDS[i], GPIO.LOW)
        # Al terminar o interrumpir, limpiamos el led actual
        state["current_led"] = None

def _marquee_right():
    while not stop_event.is_set():
        for i in range(len(PIN_LEDS)-1, -1, -1):
            if stop_event.is_set(): break
            
            state["current_led"] = i + 1
            
            GPIO.output(PIN_LEDS[i], GPIO.HIGH)
            sleep(base_delay)
            GPIO.output(PIN_LEDS[i], GPIO.LOW)
        state["current_led"] = None

def _marquee_pingpong():
    while not stop_event.is_set():
        for i in range(len(PIN_LEDS)):
            if stop_event.is_set(): break
            
            state["current_led"] = i + 1

            GPIO.output(PIN_LEDS[i], GPIO.HIGH)
            sleep(base_delay)
            GPIO.output(PIN_LEDS[i], GPIO.LOW)

        for i in range(len(PIN_LEDS)-2, 0, -1):
            if stop_event.is_set(): break
            
            state["current_led"] = i + 1

            GPIO.output(PIN_LEDS[i], GPIO.HIGH)
            sleep(base_delay)
            GPIO.output(PIN_LEDS[i], GPIO.LOW)

# =========================
# CONTROL
# =========================

def marquee(type='pingpong', speed=0.5):
    global current_thread, base_delay
    
    base_delay = speed
    _setup_gpio()
    _stop_current_animation()

    state["mode"] = f"Animacion ({type})"
    state["marquee_type"] = type
    state["speed"] = speed
    state["active_led"] = "Secuencia"

    switcher = {
        'left': _marquee_left,
        'right': _marquee_right,
        'pingpong': _marquee_pingpong
    }

    func = switcher.get(type)

    if func:
        current_thread = threading.Thread(target=func)
        current_thread.daemon = True
        current_thread.start()

def leds(num):
    _setup_gpio()
    _stop_current_animation()

    idx = int(num) - 1

    state["mode"] = "Manual"
    state["active_led"] = num
    state["marquee_type"] = num #en modo manual, el actual es el activo
    state["current_led"] = int(num) #esto ilumina el circulo en el html
    for i, pin in enumerate(PIN_LEDS):
        GPIO.output(pin, GPIO.HIGH if i == idx else GPIO.LOW)

def bcd(num):
    _setup_gpio()

    val = int(num)

    state["mode"] = "bcd"
    state["bcd_value"] = val
    state["current_led"] = None #Apaga los círculos de la secunecia en la web
    state["active_led"] = None

    GPIO.output(16, GPIO.HIGH if val & 0x8 else GPIO.LOW)
    GPIO.output(20, GPIO.HIGH if val & 0x4 else GPIO.LOW)
    GPIO.output(21, GPIO.HIGH if val & 0x2 else GPIO.LOW)
    GPIO.output(26, GPIO.HIGH if val & 0x1 else GPIO.LOW)

# =========================
# FLASK API
# =========================

app = Flask(__name__)

@app.route("/state")
def get_state():
    return jsonify(state)

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
