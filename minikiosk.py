import vlc 
import time
import os #para las rutas

os.system('clear') #Limpiar la pantalla
os.system('tput civis')
#Parametros para ocultar la interfaz y forzar pantalla completa
vlc_flags =['--fullscreen', '--no-video-title-show','--no-osd', '--quiet','--mouse-hide-timeout=0']
#ruta absoluta del video
video_path = 'videos/video.mp4'

#Reproduccion inicial del video
#se crea la instancia
instance = vlc.Instance(' '.join(vlc_flags))
#Se crea el reproductor
player = instance.media_player_new()
#se crea el objeto media antes de pasar directo la ruta
video_objeto = instance.media_new(video_path)
#se asigna el objeto Media al reproductor
player.set_media(video_objeto)
player.play()
time.sleep(10) #forzamos los 10 segundos
player.stop()

#configuracion del bucle de imagenes
instance = vlc.Instance('--input-repeat=999999') #condifguracion de repeticion
media_list = instance.media_list_new()
#se generan las rutas para las imagenes sabiendo que estan al mismo nivel que la carpeta videos

for i in range (1, 5):
	ruta_img = f'pictures/pic0{i}.jpg'
	#se tiene que verificar si existe antes de añadir la ruta
	if os.path.exists(ruta_img):
		media_list.add_media(instance.media_new(ruta_img))
	else:
		print(f"Advertencia: No se encontro ̣̣{ruta_img}")
#configuracion del reproducto de lista
list_player = instance.media_list_player_new()
list_player.set_media_list(media_list)
#Configuracion del modo loop para que VLC no este en un estado Ended con la ultima imagen
list_player.set_playback_mode(vlc.PlaybackMode.loop)
list_player.play()
#Logica para cambiar de imagen cada 3 segundos
try:
	while True:
		time.sleep(3)
		list_player.next()
except KeyBoardInterrupt:
	#Se detiene el programa con Ctrl+C, y devolvemos el cursor a la normalidad
	os.system('tput cnorm')
	list_player.stop()
