import vlc
import time
import os

# --- CONFIGURACIÓN DE VLC (Modo Kiosko) ---
vlc_flags = [
    '--fullscreen',                # Pantalla completa
    '--no-video-title-show',       # No mostrar el nombre del archivo
    '--no-osd',                    # Sin interfaz en pantalla
    '--quiet',                     # Sin logs innecesarios
    '--mouse-hide-timeout=0'       # Ocultar el puntero del mouse
]

instancia = vlc.Instance(vlc_flags)
reproductor = instancia.media_player_new()

# --- LÓGICA DE REPRODUCCIÓN ---
try:
    # Limpiar terminal y ocultar cursor para presentación profesional
    os.system('clear')
    os.system('tput civis')

    # Cargar el archivo de video
    video = instancia.media_new('videos/video.mp4')
    reproductor.set_media(video)
    
    print("Iniciando video de 20 segundos con envolvente de volumen...")
    reproductor.play()
    
    # Pequeño retardo para asegurar que el motor de audio de VLC haya arrancado
    time.sleep(0.2)

    # Bucle de control de tiempo (200 pasos de 0.1s = 20 segundos totales)
    for t in range(200):
        segundo_actual = t / 10.0
        
        # 1. FADE IN: De 0 a 5 segundos (Incremento gradual)
        if segundo_actual <= 5.0:
            volumen = int((segundo_actual / 5.0) * 100)
            
        # 2. MESETA: De 5 a 15 segundos (Volumen máximo al 100%)
        elif segundo_actual <= 15.0:
            volumen = 100
            
        # 3. FADE OUT: De 15 a 20 segundos (Decremento gradual)
        else:
            volumen = int(100 - ((segundo_actual - 15.0) / 5.0) * 100)
        
        # Aplicar el volumen calculado
        reproductor.audio_set_volume(volumen)
        
        # Esperar 100ms antes del siguiente ajuste
        time.sleep(0.1)

    # Detener el video exactamente a los 20 segundos
    reproductor.stop()
    print("Reproducción finalizada con éxito.")

except KeyboardInterrupt:
    print("\nReproducción interrumpida por el usuario.")

finally:
    # Devolver el cursor a la normalidad al salir
    os.system('tput cnorm')
