Author: Martínez Araujo Jesús Alonso
# SmartTV Kiosk

Sistema multimedia para Raspberry Pi que convierte un televisor HDMI en una SmartTV
controlada por control remoto infrarrojo. No requiere teclado, raton ni monitor adicional.
Toda la interaccion se realiza desde el control remoto.

Desarrollado como proyecto final de la materia Fundamentos de Sistemas Embebidos.


---

## Indice

1. Descripcion general
2. Hardware requerido
3. Estructura del proyecto
4. Instalacion
5. Configuracion del control remoto
6. Como usar el sistema
7. Mapa de botones del control
8. Servicios de streaming disponibles
9. Reproduccion desde USB
10. Detalles tecnicos


---

## 1. Descripcion general

SmartTV Kiosk es una aplicacion de pantalla completa que presenta un menu lateral
navegable con las siguientes secciones:

- Servicio Online: acceso a plataformas de streaming de video y musica via Chromium
- Musica: reproduccion de archivos de audio desde memoria USB
- Videos: reproduccion de archivos de video desde memoria USB
- Fotos: presentacion de diapositivas de imagenes desde memoria USB
- Configuracion: reservado para ajustes del sistema
- Salir Kiosko: apaga la Raspberry Pi de forma segura

La aplicacion se inicia automaticamente al arrancar el sistema mediante un servicio
de systemd. Todo corre bajo una sesion X11 limpia lanzada con xinit, sin entorno de
escritorio (Raspberry Pi OS Lite).


---

## 2. Hardware requerido

- Raspberry Pi 4 B+ con imagen de Raspberry Pi OS Lite (Debian 12) en microSD de 32 GB
- Television o monitor con entrada HDMI o VGA
- Cable HDMI y adaptador HDMI a micro HDMI (incluido en kits oficiales de RPi)
- Convertidor VGA a HDMI (solo si el monitor no tiene entrada HDMI)
- Bocina con conexion 3.5 mm (Mini Jack) y cable Jack 3.5 Macho-Macho
- Sensor de infrarrojo KY-022 y 3 jumpers hembra-hembra
- Control remoto Motorola Google TV (Television 32 pulgadas Motorola HD MOT32HLE11 o compatible)
- Cargador USB-C con salida de 5V a 3A
- Memoria USB con contenido multimedia (opcional)
- Teclado USB (necesario solo la primera vez para iniciar sesion en Netflix, Spotify, etc.)
- Cable ethernet (opcional, alternativa al WiFi)

Conexion del sensor KY-022:

- VCC     ->  Pin 1  (3.3V)
- GND     ->  Pin 6  (GND)
- Señal   ->  Pin 12 (GPIO 18)


---

## 3. Estructura del proyecto

```
ProyectoFinal/
|
+-- run_menu.sh             Script de arranque del kiosk
+-- detect_display.py       Herramienta de diagnostico de video (uso manual)
+-- ir_debug.py             Herramienta de diagnostico del sensor IR (uso manual)
|
+-- ui/
|   +-- menu.py             Aplicacion principal (interfaz grafica y logica central)
|
+-- remote/
|   +-- input.py            Lector de senales IR desde GPIO (clase IRInput)
|   +-- identificator.py    Herramienta para identificar y mapear botones del control
|   +-- teclado_virtual.py  Teclado virtual a nivel kernel (uinput) para streaming
|   +-- ir_keymap.json      Mapa de codigos IR a acciones del sistema
|
+-- media/
|   +-- classifier.py       Extensiones soportadas, flags de audio y clasificador USB
|   +-- videos.py           Escaner de videos y reproductor VLC embebido
|   +-- musica.py           Escaner de audio y reproductor VLC
|   +-- imagenes.py         Escaner de imagenes y reproductor VLC (slideshow 1.5s/foto)
|   +-- player.py           Reproductor alternativo (referencia, no usado por la app)
|   +-- detector.py         Monitor USB alternativo (referencia, no usado por la app)
|   +-- usb_media.py        Gestor USB alternativo (referencia, no usado por la app)
|
+-- services/
|   +-- online.py           WiFi, Chromium kiosk y servicios de streaming
|
+-- assets/
|   +-- icons/              Iconos PNG para el menu principal
```


---

## 4. Instalacion

### 4.1 Requisitos previos del sistema

Instalar Raspberry Pi OS Lite y asegurarse de tener conexion a internet durante la
instalacion de dependencias.

Actualizar el sistema:

```
sudo apt update && sudo apt upgrade -y
```

### 4.2 Dependencias del sistema

```
sudo apt install -y \
    python3 python3-pip \
    python3-tk \
    python3-vlc vlc \
    chromium-browser \
    network-manager \
    xorg xinit \
    xdotool \
    udisks2 \
    pulseaudio \
    alsa-utils \
    dbus-x11 \
    python3-pyudev \
    python3-rpi.gpio \
    python3-evdev \
    python3-pil python3-pil.imagetk
```

### 4.3 Modulo uinput (teclado virtual para streaming)

El teclado virtual requiere el modulo uinput del kernel para enviar eventos de teclado
a Chromium de forma que no sean bloqueados por plataformas como Netflix:

```
sudo modprobe uinput
echo 'uinput' | sudo tee -a /etc/modules
```

### 4.4 Clonar o copiar el proyecto

Copiar la carpeta del proyecto a la Raspberry Pi:

```
scp -r ProyectoFinal pi@<ip-de-la-pi>:/home/pi/
```

O clonar desde repositorio si aplica:

```
git clone <url-del-repositorio> /home/pi/ProyectoFinal
```

### 4.5 Permisos del script de arranque

```
chmod +x /home/pi/ProyectoFinal/run_menu.sh
```

### 4.6 Arranque automatico con systemd

Para que el kiosk inicie automaticamente cada vez que se enciende la Raspberry Pi,
crear el archivo de servicio con el siguiente comando:

```
sudo nano /etc/systemd/system/smarttv-kiosk.service
```

Pegar el siguiente contenido dentro del archivo:

```
[Unit]
Description=SmartTV Kiosk Official Launcher
After=network.target sound.target

[Service]
Type=simple
ExecStart=/bin/bash /home/pi/ProyectoFinal/run_menu.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Guardar y salir (en nano: Ctrl+O, Enter, luego Ctrl+X).

Nota: el servicio corre bajo multi-user.target (modo consola, sin entorno de escritorio).
Esto funciona correctamente porque run_menu.sh se encarga de levantar la sesion grafica
X11 mediante xinit.

Habilitar e iniciar el servicio:

```
sudo systemctl daemon-reload
sudo systemctl enable smarttv-kiosk.service
sudo systemctl start smarttv-kiosk.service
```

### 4.7 Monitoreo y solucion de problemas

Ver el estado actual del servicio:

```
sudo systemctl status smarttv-kiosk.service
```

Ver los logs en tiempo real (los print() de Python y errores de xinit aparecen aqui):

```
sudo journalctl -u smarttv-kiosk.service -f
```

### 4.8 Arranque manual

Para iniciar el kiosk manualmente sin systemd:

```
sudo bash /home/pi/ProyectoFinal/run_menu.sh
```

### 4.9 Nota para usuarios de Raspberry Pi OS Lite

Si se usa la version Lite de Raspberry Pi OS, verificar que xinit y el servidor X
esten instalados antes de ejecutar el kiosk, de lo contrario xinit fallara:

```
sudo apt install xinit xserver-xorg xorg
```


---

## 5. Configuracion del control remoto

El sistema viene con un mapa de botones preconfigurado para el control remoto de la
Television Pantalla 32 pulgadas Google TV Motorola HD MOT32HLE11, guardado en
remote/ir_keymap.json.

Si se usa un control diferente, los codigos IR deben identificarse y registrarse con la
herramienta incluida:

```
sudo python3 /home/pi/ProyectoFinal/remote/identificator.py
```

La herramienta pide presionar cada boton tres veces (votacion para estabilidad) y
asignarlo a una accion. Al terminar, guarda automaticamente el nuevo ir_keymap.json.

El archivo resultante tiene este formato:

```
{
  "generated": "2026-01-01T00:00:00",
  "sensor_pin": 18,
  "protocol": "NEC_EXT",
  "keymap": {
    "0x404015": "nav_up",
    "0x404016": "nav_down",
    ...
  }
}
```


---

## 6. Como usar el sistema

### Navegacion en el menu principal

Al iniciar el sistema aparece el menu principal con una barra lateral izquierda que
lista las secciones disponibles. El item seleccionado se resalta en verde.

- Flecha arriba / abajo: mueve la seleccion en el menu
- OK: confirma la seleccion actual
- PREV (atras): regresa al menu anterior o detiene la reproduccion activa
- RESET: reinicia todas las variables al estado inicial sin cerrar la aplicacion
- APAGAR (boton rojo del control): apaga la Raspberry Pi de forma segura

### Insertar un USB

Al conectar una memoria USB, el sistema la detecta automaticamente, analiza su contenido
y muestra una notificacion en la parte superior de la pantalla indicando que tipo de
contenido encontro. Si el USB contiene solo musica y el usuario accede a "Videos", el
sistema indicara que no hay videos. Cuando el USB tiene contenido variado (mixto), el
sistema lo separa correctamente y cada seccion del menu accede de forma independiente a
su tipo de archivo correspondiente.

Al desconectar el USB aparece la notificacion "USB desconectado" y el sistema regresa
automaticamente al menu principal deteniendo cualquier reproduccion activa. Si el sistema
parece no responder, presionar RESET para limpiar el estado.

### Reproducir videos desde USB

1. Navegar a "Videos" en el menu principal y presionar OK
2. El sistema muestra la lista de archivos de video encontrados
3. Navegar con las flechas (arriba / abajo) y presionar OK para reproducir
4. La primera opcion "REPRODUCIR TODO" reproduce todos los videos en bucle
5. Presionar PREV para detener y volver a la lista
6. Presionar PREV nuevamente para volver al menu principal

### Reproducir musica desde USB

1. Navegar a "Musica" y presionar OK
2. El sistema muestra la lista de canciones encontradas
3. Navegar y presionar OK para reproducir la cancion seleccionada
4. La primera opcion reproduce toda la lista en bucle
5. La musica continua en segundo plano mientras se navega el menu
6. Presionar PREV para detener la reproduccion

### Ver fotos desde USB

1. Navegar a "Fotos" y presionar OK
2. Las fotos se muestran una por una cada 1.5 segundos en bucle automatico
3. Presionar PREV para detener la presentacion

### Acceder a servicios de streaming

1. Navegar a "Servicio Online" y presionar OK
2. El sistema verifica la conexion a internet
3. Se muestra la lista de plataformas disponibles: primero video, luego musica
4. Navegar con las flechas arriba / abajo y presionar OK para abrir la plataforma
5. Chromium se abre en pantalla completa con el sitio elegido
6. Usar las cuatro flechas del control para mover el cursor del mouse dentro del navegador
7. Mantener presionada una flecha acelera el cursor progresivamente
8. OK hace clic en la posicion actual del cursor
9. Los botones de scroll (sidebar arriba / sidebar abajo) desplazan el contenido
   de la pagina hacia arriba o hacia abajo sin mover el cursor
10. Presionar PREV para cerrar el navegador y volver al menu

Nota importante: la primera vez que se accede a Netflix, Spotify u otros servicios,
se solicitara inicio de sesion. Conectar un teclado USB a la Raspberry Pi para ingresar
el correo y la contrasena. Una vez guardadas las credenciales, no sera necesario
repetir este paso y el control remoto tomara el control completo.

### Control de volumen

Estos botones funcionan en cualquier momento, sin importar lo que este en pantalla:

- Boton de volumen arriba: sube el volumen 5%
- Boton de volumen abajo: baja el volumen 5%
- Boton mute: silencia o restaura el audio


---

## 7. Mapa de botones del control

### Navegacion general (menu y listas)

- Arriba: mueve la seleccion hacia arriba en el menu
- Abajo: mueve la seleccion hacia abajo en el menu
- OK: confirma / selecciona / reproduce
- PREV: regresa / detiene reproduccion / cierra navegador

### Cuando Chromium esta abierto (streaming)

- Arriba: mueve el cursor del mouse hacia arriba
- Abajo: mueve el cursor del mouse hacia abajo
- Izquierda: mueve el cursor del mouse hacia la izquierda
- Derecha: mueve el cursor del mouse hacia la derecha
- OK: clic izquierdo en la posicion actual del cursor
- Sidebar arriba: desplaza el contenido de la pagina hacia arriba (scroll)
- Sidebar abajo: desplaza el contenido de la pagina hacia abajo (scroll)
- PREV: cierra Chromium y regresa al menu

Aceleracion del cursor: mantener presionada cualquier flecha aumenta la velocidad
del cursor progresivamente hasta 5 veces la velocidad base (25px por pulsacion).

### Volumen (siempre activo)

- Volume Up: sube volumen 5%
- Volume Down: baja volumen 5%
- Mute: silenciar / restaurar

### Botones especiales

- Reset: detiene todo, cierra Chromium si estaba abierto y regresa al menu principal
  con todos los indices en cero. La aplicacion no se cierra, solo se limpia.
- Apagar: apaga la Raspberry Pi de forma segura

### Codigos IR asignados actualmente

```
0x404015  ->  Flecha arriba           (nav_up)
0x404016  ->  Flecha abajo            (nav_down)
0x404017  ->  Flecha izquierda        (nav_left)
0x404018  ->  Flecha derecha          (nav_right)
0x404019  ->  OK / Seleccionar        (nav_ok)
0x404048  ->  Atras / PREV            (prev)
0x404023  ->  Volumen arriba          (volume_up)
0x404024  ->  Volumen abajo           (volume_down)
0x404025  ->  Silenciar               (mute)
0x404021  ->  Apagar sistema          (apagar)
0x404033  ->  Scroll arriba Chromium  (sidebar_up)
0x404034  ->  Scroll abajo Chromium   (sidebar_down)
0x404047  ->  Reiniciar aplicacion    (reset)
0x404049  ->  Modo audio              (mode_audio)
0x40404A  ->  Modo imagen             (mode_image)
0x40404B  ->  Modo video              (mode_video)
0x40404C  ->  USB 1                   (usb_1)
```


---

## 8. Servicios de streaming disponibles

### Video

- Netflix          https://www.netflix.com
- HBO Go           https://www.hbomax.com/mx/es
- Blim             https://www.blim.com
- YouTube          https://www.youtube.com/tv
- Disney Plus      https://www.disneyplus.com
- Prime Video      https://www.primevideo.com

### Musica

- Spotify          https://open.spotify.com
- YouTube Music    https://music.youtube.com
- Deezer           https://www.deezer.com
- Tidal            https://listen.tidal.com

Nota: algunos servicios como Netflix requieren cuenta activa. La primera vez
solicitaran inicio de sesion — conectar un teclado USB a la Raspberry para ingresar
correo y contrasena. Las credenciales se guardan en el perfil de Chromium y no sera
necesario repetirlo en sesiones futuras.


---

## 9. Reproduccion desde USB

### Formatos de video reconocidos

mp4, mkv, avi, mov, m4v, wmv, ts, m2ts, webm, 3gp, flv, mpg, mpeg, vob, divx

### Formatos de audio reconocidos

mp3, flac, ogg, wav, aac, m4a

### Formatos de imagen reconocidos

jpg, jpeg, png, bmp, gif, webp

### Notas sobre el USB

- El USB se monta automaticamente al insertarse mediante udisksctl
- Los archivos se escanean de forma recursiva (incluye subcarpetas)
- Los nombres de archivo se muestran sin la extension ni la ruta completa
- Si el USB tiene contenido mixto, cada seccion del menu accede a sus propios archivos
  de forma independiente (Videos accede solo a videos, Musica solo a canciones, etc.)
- Al desconectar el USB el sistema detiene la reproduccion y regresa al menu principal


---

## 10. Detalles tecnicos

### Audio

La salida de audio esta configurada de forma fija al jack 3.5mm de la Raspberry Pi
(dispositivo ALSA plughw:0,0). El script run_menu.sh inicializa el volumen al 90%
y desmutea todos los controles ALSA antes de arrancar para garantizar audio desde
el inicio.

### Control infrarrojo

El receptor IR usa el protocolo NEC en su variante extendida (direcciones de 16 bits).
La clase IRInput en remote/input.py lee directamente del GPIO sin libreria de terceros
para el protocolo, lo que reduce la latencia. Implementa:

- Anti-rebote por tiempo (repeat_gap = 0.28 segundos)
- Soporte de tecla mantenida (senal REPEAT de NEC) con contador de repeticiones
- Aceleracion de cursor proporcional al tiempo que se mantiene presionado un boton

### Cursor del mouse en streaming

Cuando Chromium esta abierto, las cuatro flechas del control mueven el puntero del
mouse usando xdotool mousemove_relative. La velocidad base es de 25 pixeles por
pulsacion y escala con el numero de repeticiones consecutivas de la senal REPEAT:

- Pulsaciones 1 a 3:        velocidad 1x  (25px)
- Pulsaciones 4 a 6:        velocidad 2x  (50px)
- Pulsaciones 7 a 9:        velocidad 3x  (75px)
- Pulsaciones 10 a 12:      velocidad 4x  (100px)
- Pulsacion 13 en adelante: velocidad maxima 5x (125px)

### Teclado virtual

Para enviar eventos de teclado a Chromium que no sean bloqueados por plataformas
de streaming, el sistema usa /dev/uinput a traves de la libreria evdev. Los eventos
generados son indistinguibles de un teclado fisico real.

### Reproduccion de video

El video se embebe directamente dentro de la ventana de tkinter usando el Window ID
de X11 (xwindow). VLC recibe este identificador y renderiza dentro del frame en
lugar de abrir una ventana separada.

### Presentacion de imagenes

Las imagenes se muestran con una duracion de 1.5 segundos por foto en bucle
continuo, tambien embebidas dentro del mismo frame X11 que el reproductor de video.

### Deteccion de USB

El modulo pyudev monitorea eventos del kernel (netlink) para detectar particiones
nuevas en tiempo real. Al detectar una insercion, el sistema monta el dispositivo
con udisksctl y encuentra la ruta de montaje con findmnt. Al extraer el USB, detiene
toda reproduccion activa y regresa al menu principal automaticamente.

### Ejecucion como root

El sistema corre como root (sudo) porque xinit bajo Raspberry Pi OS Lite lo requiere
sin configuracion adicional de Xwrapper. Esto tambien permite el acceso directo a
GPIO sin necesidad de agregar el usuario al grupo gpio.
