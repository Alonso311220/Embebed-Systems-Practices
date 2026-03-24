import vlc
import time
import os
import threading
from gpiozero import Button

# --- CONFIGURACIÓN DE VLC ---
vlc_flags = ['--input-repeat=999999','--fullscreen', '--no-video-title-show', '--no-osd', '--quiet']
instancia = vlc.Instance(vlc_flags)

# Objetos de reproducción
reproductor = instancia.media_player_new()
lista_reproductor = instancia.media_list_player_new()
lista_reproductor.set_media_player(reproductor) # Vínculo para que el volumen afecte a la lista

# --- VARIABLES GLOBALES DE CONTROL ---
vol_actual = 100
timer_fotos = 0 
ejecutando_kiosko = True

# --- FUNCIONES DE CONTROL (CALLBACKS) ---

def finalizar_programa():
    global ejecutando_kiosko
    print("\n[GPIO 4] Botón Parar presionado. Finalizando...")
    ejecutando_kiosko = False
    lista_reproductor.stop()
    reproductor.stop()

def reset_timer():
    global timer_fotos
    timer_fotos = 0

def accion_siguiente():
    print("Siguiente imagen...")
    reset_timer()
    lista_reproductor.next()

def accion_anterior():
    print("Imagen anterior...")
    reset_timer()
    lista_reproductor.previous()

def toggle_pausa():
    # Alterna entre pausa y reproducción
    if reproductor.is_playing():
        print("Pausado.")
        reproductor.pause()
    else:
        print("Reanudado.")
        reproductor.play()

def subir_vol():
    global vol_actual
    vol_actual = min(100, vol_actual + 10)
    reproductor.audio_set_volume(vol_actual)
    print(f"Volumen Maestro: {vol_actual}%")

def bajar_vol():
    global vol_actual
    vol_actual = max(0, vol_actual - 10)
    reproductor.audio_set_volume(vol_actual)
    print(f"Volumen Maestro: {vol_actual}%")

# --- CONFIGURACIÓN DE PINES GPIO ---
btn_ant = Button(2)
btn_sig = Button(3)
btn_parar = Button(4)
btn_pausa = Button(17)
btn_vol_mas = Button(27)
btn_vol_menos = Button(22)

# Asignación de acciones a los botones
btn_ant.when_pressed = accion_anterior
btn_sig.when_pressed = accion_siguiente
btn_parar.when_pressed = finalizar_programa
btn_pausa.when_pressed = toggle_pausa
btn_vol_mas.when_pressed = subir_vol
btn_vol_menos.when_pressed = bajar_vol

# --- FUNCIONES DE APOYO ---
def generar_lista(directorio):
    """Carga pic01.jpg a pic04.jpg del directorio dado"""
    m_list = instancia.media_list_new()
    for i in range(1, 5):
        ruta = os.path.join(directorio.strip(), f"pic0{i}.jpg")
        if os.path.exists(ruta):
            m_list.add_media(instancia.media_new(ruta))
    return m_list

# --- EJECUCIÓN PRINCIPAL ---
try:
    os.system('clear')
    os.system('tput civis') # Ocultar cursor

    # 1. ETAPA: VIDEO DE 20s CON FADE INTERACTIVO
    video = instancia.media_new('videos/video.mp4')
    reproductor.set_media(video)
    reproductor.play()
    
    time.sleep(0.5)
    print(">>> Iniciando Video (20s) con Fade. Controles activos.")

    t = 0
    while t < 200 and ejecutando_kiosko:
        # Si pausamos, el tiempo de fade no avanza
        if not reproductor.is_playing():
            time.sleep(0.1)
            continue 

        # Cálculo de curva de volumen
        seg = t / 10.0
        if seg <= 5: 
            v_curva = (seg / 5.0)
        elif seg <= 15: 
            v_curva = 1.0
        else: 
            v_curva = 1.0 - ((seg - 15.0) / 5.0)

        # Aplicar volumen (Curva * Ajuste del usuario)
        vol_final = int(v_curva * vol_actual)
        reproductor.audio_set_volume(max(0, min(100, vol_final)))

        time.sleep(0.1)
        t += 1

    reproductor.stop()

    if ejecutando_kiosko:
        # 2. ETAPA: CARGA DE IMÁGENES
        media_list = generar_lista("pictures")
        lista_reproductor.set_media_list(media_list)
        lista_reproductor.set_playback_mode(vlc.PlaybackMode.loop)
        lista_reproductor.play()

        print(">>> Kiosko de Imágenes Activo. Cambio cada 3s (o manual).")

        # 3. ETAPA: BUCLE DE CONTROL DE IMÁGENES
        while ejecutando_kiosko:
            time.sleep(0.1)
            
            # Solo corre el tiempo si el reproductor está activo (no pausado)
            if reproductor.is_playing():
                timer_fotos += 0.2
            else:
                timer_fotos = 0.01 # Opcional: reiniciar para que al reanudar espere 3s

            # Cambio automático cada 3 segundos
            if timer_fotos >= 3.0:
                lista_reproductor.next()
                timer_fotos = 0

except KeyboardInterrupt:
    pass

finally:
    reproductor.stop()
    lista_reproductor.stop()
    os.system('tput cnorm') # Devolver cursor
    print("\nPrograma finalizado correctamente.")
