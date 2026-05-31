#!/bin/bash
cd /home/pi/ProyectoFinal/ui
pkill -f "python3 menu.py" 2>/dev/null
sleep 0.3
export SDL_VIDEODRIVER=kmsdrm
export SDL_VIDEO_KMSDRM_DEVICE_INDEX=0
export SDL_NOMOUSE=1
unset DISPLAY
python3 menu.py