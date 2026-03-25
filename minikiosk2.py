import vlc
import time
import os
import threading
from gpiozero import Button

# --- CONFIGURACIÓN DE VLC ---
# Flags para que no se vea nada más que el video/imagen
vlc_flags = [
    '--fullscreen', 
    '--no-video-title-show', 
    '--no-osd', 
    '--quiet', 
    '--mouse-hide-timeout=0'
]
instancia = vlc.Instance(vlc_flags)

# Imagenes para reproducción
lista_reproductor = instancia.media_list_player_new()

# Variables de control para la USB
usb_ruta_detectada = None
usb_lista_lista = False

# --- PUNTO 4: CONTROL GPIO ---
# Definimos los botones según tus pines
btn_ant = Button(2)
btn_sig = Button(3)
btn_parar = Button(4)
btn_pausa = Button(17)

# Asignación de acciones
btn_sig.when_pressed = lista_reproductor.next
btn_ant.when_pressed = lista_reproductor.previous
btn_parar.when_pressed = lista_reproductor.stop
btn_pausa.when_pressed = lista_reproductor.pause
btn_vol_mas.when_pressed = subir_vol
btn_vol_menos.when_pressed = bajar_vol

# --- FUNCIONES DE APOYO ---
def generar_lista(directorio):
    """Crea una MediaList con pic01 a pic04 en el directorio dado"""
    m_list = instancia.media_list_new()
    for i in range(1, 5):
        # strip() limpia posibles saltos de línea en la ruta de la USB
        ruta = os.path.join(directorio.strip(), f"pic0{i}.jpg")
        if os.path.exists(ruta):
            m_list.add_media(instancia.media_new(ruta))
    return m_list

def hilo_espera_usb():
    """Importa tu script usbdetect.py y captura la ruta cuando termine"""
    global usb_ruta_detectada, usb_lista_lista
    # Al importar, se ejecuta el 'while True' de tu archivo hasta que detecta la USB
    import usbdetect 
    # 'mp' es la variable que definiste al final de usbdetect.py
    usb_ruta_detectada = usbdetect.mp
    usb_lista_lista = True

# --- EJECUCIÓN PRINCIPAL ---
try:
    # Limpieza de pantalla y cursor
    os.system('clear')
    os.system('tput civis')

    # 1. ACTIVAR DETECTOR USB EN SEGUNDO PLANO
    escucha_usb = threading.Thread(target=hilo_espera_usb, daemon=True)
    escucha_usb.start()

    # 2.  BUCLE INFINITO DE IMÁGENES LOCALES
    media_list = generar_lista("pictures")
    lista_reproductor.set_media_list(media_list)
    lista_reproductor.set_playback_mode(vlc.PlaybackMode.loop)
    lista_reproductor.play()

    print("Kiosko iniciado. Pulse Ctrl+C para salir.")

    while True:
        # Si el hilo de la USB terminó, cambiamos la lista
        if usb_lista_lista:
            print(f"Cambiando a imágenes de la USB en: {usb_ruta_detectada}")
            lista_reproductor.stop()
            nueva_lista = generar_lista(usb_ruta_detectada)
            lista_reproductor.set_media_list(nueva_lista)
            lista_reproductor.play()
            usb_lista_lista = False # Para no recargar en bucle

        time.sleep(3)
        lista_reproductor.next()

except KeyboardInterrupt:
    os.system('tput cnorm') # Devolver el cursor
    print("\nPrograma detenido.")

 
