#!/bin/bash
# run_menu.sh — Lanzador oficial del kiosk SmartTV
# Uso: sudo bash /home/pi/ProyectoFinal/run_menu.sh
# Se puede llamar desde /etc/systemd/system/smarttv-kiosk.service

# Matar instancias anteriores si las hay
pkill -f "menu.py" 2>/dev/null
sleep 0.5

# --- Audio: desmutar y subir volumen en todos los controles ALSA comunes
for ctrl in Master PCM Speaker Headphone; do
    amixer -q sset "$ctrl" 90% unmute 2>/dev/null || true
done

# --- PulseAudio: Chromium lo necesita para tener audio bajo xinit
# Si no está corriendo, arrancarlo como demonio antes de entrar a X11
if ! pulseaudio --check 2>/dev/null; then
    pulseaudio --start --exit-idle-time=-1 --log-target=null 2>/dev/null || true
    sleep 1
fi

# Lanzar el kiosk dentro de una sesión X11 limpia
# xinit gestiona el servidor X y pasa DISPLAY=:0 automáticamente
exec xinit /usr/bin/python3 /home/pi/ProyectoFinal/ui/menu.py
