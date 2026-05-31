#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  setup_kiosk.sh — Instala y arranca el Raspberry Kiosk      ║
# ║  Uso: chmod +x setup_kiosk.sh && ./setup_kiosk.sh           ║
# ╚══════════════════════════════════════════════════════════════╝

set -e
KIOSK_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "══════════════════════════════════════════"
echo "   🍓  RASPBERRY KIOSK — Setup            "
echo "══════════════════════════════════════════"
echo ""

# ── 1. Dependencias del sistema ────────────────────────────────
echo "[1/4] Instalando dependencias del sistema..."
sudo apt-get update -q
sudo apt-get install -y -q \
  python3 python3-pip python3-pygame \
  mpv chromium-browser \
  libsdl2-dev libsdl2-image-dev

# ── 2. Dependencias Python ─────────────────────────────────────
echo "[2/4] Instalando paquetes Python..."
pip3 install --upgrade flask flask-cors pillow 2>/dev/null || \
pip3 install --break-system-packages flask flask-cors pillow

# ── 3. Arrancar servidor Flask en background ──────────────────
echo "[3/4] Iniciando servidor Flask+Pygame..."
pkill -f kiosk_server.py 2>/dev/null || true
sleep 1
nohup python3 "$KIOSK_DIR/kiosk_server.py" \
  > "$KIOSK_DIR/kiosk_server.log" 2>&1 &
echo "      → PID=$! · log: $KIOSK_DIR/kiosk_server.log"

# ── 4. Abrir interfaz en Chromium kiosk mode ──────────────────
echo "[4/4] Abriendo Chromium en modo kiosk..."
sleep 2
chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=TranslateUI \
  --no-first-run \
  --start-maximized \
  "file://$KIOSK_DIR/index.html" &

echo ""
echo "✓ Kiosk iniciado correctamente."
echo ""
echo "  Logs Flask:    $KIOSK_DIR/kiosk_server.log"
echo "  Para detener:  pkill chromium-browser; pkill -f kiosk_server.py"
echo ""

# ── Servicio systemd opcional ──────────────────────────────────
read -p "¿Instalar como servicio systemd (autoarranque)? [s/N] " resp
if [[ "$resp" =~ ^[sS]$ ]]; then
  SERVICE_FILE="/etc/systemd/system/raspberry-kiosk.service"
  sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Raspberry Kiosk Multimedia
After=network.target graphical.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$KIOSK_DIR
ExecStart=$KIOSK_DIR/setup_kiosk.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable raspberry-kiosk.service
  echo "✓ Servicio systemd instalado. Se iniciará automáticamente al encender."
fi
