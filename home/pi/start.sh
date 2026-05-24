cd /home/pi || exit 1
 
# --- LCD: marquesina + temperatura en segundo plano ---
if [ -f actividad4.py ]; then
    python3 actividad4.py &
else
    echo "actividad4.py no encontrado"
fi
 
# Mantener el script vivo para que el proceso no muera
wait

