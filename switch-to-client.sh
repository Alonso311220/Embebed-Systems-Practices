#!/bin/bash
# Script seguro para pasar de AP → Cliente WiFi

LOG="/home/pi/wifi-switch.log"
echo "=== $(date) ===" >> $LOG

# --- TIMER DE EMERGENCIA ---
# Si en 90 segundos no cancelas, revierte a AP
(sleep 90 && \
  sudo systemctl stop wpa_supplicant && \
  sudo systemctl start hostapd dnsmasq && \
  echo "$(date) — REVERTIDO a AP (timeout)" >> $LOG) &
TIMER_PID=$!
echo "Timer de emergencia activo (PID $TIMER_PID) — 90s para revertir" | tee -a $LOG

# --- CAMBIO A MODO CLIENTE ---
echo "Deteniendo AP..." | tee -a $LOG
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

echo "Activando cliente WiFi..." | tee -a $LOG
sudo systemctl start wpa_supplicant

# Espera a obtener IP
sleep 15
IP=$(ip addr show wlan0 | grep "inet " | awk '{print $2}' | cut -d/ -f1)

if [ -n "$IP" ]; then
    echo "✅ Conectado al router. IP: $IP" | tee -a $LOG
    # Cancelar el timer de emergencia
    kill $TIMER_PID 2>/dev/null
    echo "Timer cancelado. Conexión estable." | tee -a $LOG
    echo ""
    echo "========================================"
    echo "  NUEVA IP para SSH: $IP"
    echo "  ssh pi@$IP"
    echo "========================================"
else
    echo "❌ No se obtuvo IP. Revirtiendo a AP..." | tee -a $LOG
    kill $TIMER_PID 2>/dev/null
    sudo systemctl stop wpa_supplicant
    sudo systemctl start hostapd dnsmasq
    echo "AP restaurado." | tee -a $LOG
fi
