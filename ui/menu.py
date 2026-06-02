#!/usr/bin/env python3
# Le hace saber al sistema que este script debe ejecutarse con Python3
import os, sys, time, threading # Módulos para el SO, parámetros y funciones del sistema, manejo de pausas, y tareas en segun plano 
import tkinter as tk # Asignación de un alias para interfaz gráfica 
import subprocess as sp #Modulo para ejecutar comandos del sistema operativo para manejo de USBs
from pathlib import Path #Para rutas de archivos

# Fix para RPi OS Lite con xinit: VLC y PulseAudio requieren XDG_RUNTIME_DIR
if not os.environ.get('XDG_RUNTIME_DIR'): 
    _rtdir = f'/tmp/runtime-{os.getuid()}' # Dirección temporal para runtime para evitar problemas con el audio y vlc
    os.makedirs(_rtdir, mode=0o700, exist_ok=True) # Crear directorio si no existe, con permisos seguros
    os.environ['XDG_RUNTIME_DIR'] = _rtdir # Establece la variable de entorno para el runtime de XDG

#Ruta para importar los modulos que se encuentran en /home/pi/ProyectoFinal
sys.path.append(str(Path(__file__).parent.parent))

try:
    import pyudev #detecta los eventos de conexión y desconexión de USBs
except ImportError as e:
    print(f"\033[31mFaltan dependencias: {e}\033[0m"); sys.exit(1)

try:
    from remote.input import IRInput # Maneja el control remoto al detectar las señales infrarrojas
except ImportError as e:
    print(f"\033[31mError remote.input: {e}\033[0m"); sys.exit(1)

try:
    from media.videos import obtener_videos, ReproductorVideo #Llama a la clase 
    from media.classifier import classify_usb # Clasifica el contenido del USB 
except ImportError as e:
    print(f"\033[31mError modulos media: {e}\033[0m"); sys.exit(1)

try:
    from media.musica import obtener_canciones, ReproductorMusica
    from media.imagenes import obtener_imagenes, ReproductorImagenes
except ImportError as e:
    print(f"\033[31mError modulos media: {e}\033[0m"); sys.exit(1)

try:
    from services.online import GestorOnline, SERVICIOS_VIDEO # Servicios Online
except ImportError as e:
    print(f"\033[31mError modulos online: {e}\033[0m"); sys.exit(1)

# PIL para cargar iconos PNG; si no está instalado se usan caracteres de texto
try:
    from PIL import Image, ImageTk # Para cargar y manejar imágenes del menú e iconos
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

ICON_DIR = Path(__file__).parent.parent / "assets" / "icons"
#Colores para interfaz gráfica
BG      = "#0a0a0a"
BG_HDR  = "#000000"
BG_SB   = "#141414"
BG_SEL  = "#1f1f1f"
BG_LINE = "#2a2a2a"
GREEN     = "#09e55d"
GREEN2    = "#0fb207"
WHITE   = "#ffffff"
GRAY    = "#888888"
LGRAY   = "#cccccc"

# "icon": nombre de archivo en assets/icons/ (PNG cargado con PIL)
# "char": caracter de respaldo si PIL no está disponible, y para el panel de detalle grande
ITEMS = [
    {"label": "Servicio Online",     "icon": "monitor-de-television.png", "char": "▶", "desc": "Reproducir videos desde USB"},
    {"label": "Musica",        "icon": "musica.png",                "char": "♪", "desc": "Reproducir audio desde USB"},
    {"label": "Videos",        "icon": "video.png",                 "char": "◉", "desc": "Contenido multimedia local"},
    {"label": "Fotos",         "icon": "edicion-de-fotos.png",      "char": "◈", "desc": "Ver fotos desde USB en presentacion"},
    {"label": "Configuracion", "icon": "configuracion-web.png",     "char": "⚙", "desc": "Ajustes del sistema"},
    {"label": "Salir Kiosko",  "icon": "apagado.png",               "char": "✕", "desc": "Cerrar la aplicacion"},
]

class SmartTVApp:
    def __init__(self, root):
        self.root = root # Referencia a la ventana principal
        self.root.title("SmartTV Kiosk")

        # --- Pantalla completa en cascada
        self.root.update_idletasks() # Asegura que winfo tanto para el ancho como para el alto retornen valores actualizados
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0") #autoajuste de la pantalla
        self.root.overrideredirect(True) # Elimina bordes y la barra del título 
        self.root.attributes("-fullscreen", True) # Pantalla completa
        self.root.configure(bg=BG) # Color de fondo
        self.root.update_idletasks() # Asegurar que se renderize la ventana antes de continuar con vlc

        # --- Variables de Estado
        self.estado = "PRINCIPAL" # Puede ser "PRINCIPAL", "VIDEOS", "MUSICA",... para controlar la navegación
        self.idx = 0 # Índice del item seleccionado en el menú
        self._filas = [] # Lista de referencias
        self._notif_job = None # Ocultar notificaciones después de mostrarlo
        
        # --- Variables para USB Videos
        self.videos_usb          = []
        self.videos_rutas        = []
        self.idx_video           = 0
        self.reproduciendo_video = False

        # --- Variables para USB Música
        self.canciones_usb        = []
        self.canciones_rutas      = []
        self.idx_cancion          = 0
        self.reproduciendo_musica = False

        # --- Variables para USB Fotos
        self.reproduciendo_imagenes = False

        # --- Variables compartidas USB
        self.ruta_usb      = ""
        self.usb_conectado = ""

        # --- Variables para Servicios Online
        self.servicios_items = []
        self.idx_servicio    = 0
        self._internet_ok    = False  # cache del estado de internet (se verifica en hilo)

        # --- Reproductores y Gestor Online
        self.video_player  = ReproductorVideo()
        self.audio_player  = ReproductorMusica()
        self.imagen_player = ReproductorImagenes()
        self.gestor_online = GestorOnline()

        self._build_ui()

        # Forzar que tkinter registre el frame con X11 antes de pasarle el ID a VLC
        self.root.update_idletasks()
        _wid = self.video_display.winfo_id()
        self.video_player.set_ventana(_wid)   # videos
        self.imagen_player.set_ventana(_wid)  # fotos (mismo frame, usan uno a la vez)

        # --- Control Remoto
        self.ir = IRInput()
        self.ir.on("nav_up",   lambda: self.root.after(0, self.ir_subir))
        self.ir.on("nav_down", lambda: self.root.after(0, self.ir_bajar))
        self.ir.on("nav_ok",   lambda: self.root.after(0, self.ir_seleccionar))
        self.ir.on("prev",     lambda: self.root.after(0, self.ir_regresar))
        self.ir.on("apagar",   lambda: self.root.after(0, self.ir_apagar_sistema))
        self.ir.start()

        # Detectar silenciosamente si ya hay un USB conectado antes de arrancar
        self.usb_conectado = self._detectar_usb_actual()

        threading.Thread(target=self._loop_usb, daemon=True).start()
        self._tick_clock()

    # ======================================
    #  UI MAIN
    # ======================================
    def _build_ui(self):
        self.root.rowconfigure(0, weight=0) # Header
        self.root.rowconfigure(1, weight=0) # Linea
        self.root.rowconfigure(2, weight=1) #Cuerpo (Sidebar+ Detalle)
        self.root.rowconfigure(3, weight=0) # Footer
        self.root.columnconfigure(0, weight=1) # Solo una columna que ocupa toda la ventana

        # Header
        hdr = tk.Frame(self.root, bg=BG_HDR)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="SMARTTV", font=("Helvetica", 26, "bold"),
                 bg=BG_HDR, fg=GREEN, padx=20, pady=10).pack(side=tk.LEFT)
        tk.Label(hdr, text="Kiosk  |  Centro Multimedia",
                 font=("Helvetica", 11), bg=BG_HDR, fg=GRAY).pack(side=tk.LEFT, pady=14)
        self._clk = tk.Label(hdr, text="", font=("Helvetica", 16, "bold"), bg=BG_HDR, fg=LGRAY, padx=20)
        self._clk.pack(side=tk.RIGHT, pady=10)

        # Linea
        tk.Frame(self.root, bg=GREEN, height=3).grid(row=1, column=0, sticky="ew")

        # Cuerpo
        self.body = tk.Frame(self.root, bg=BG)
        self.body.grid(row=2, column=0, sticky="nsew")
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=0)
        self.body.columnconfigure(1, weight=0)
        self.body.columnconfigure(2, weight=1)

        sb = tk.Frame(self.body, bg=BG_SB, width=280)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False) # Evita que el sidebar cambie de tamaño
        self._build_sidebar(sb) # Construye el menú lateral con los items definidos en ITEMS

        tk.Frame(self.body, bg=GREEN, width=3).grid(row=0, column=1, sticky="ns")

        det = tk.Frame(self.body, bg=BG) # Contenedor para el panel de detalle que muestra la información del item seleccionado 
        det.grid(row=0, column=2, sticky="nsew") # El panel de detalle ocupa el espacio restante a la derecha del sidebar
        det.rowconfigure(0, weight=1) # Solo una fila ocupa todo el espacio vertical
        det.columnconfigure(0, weight=1) # Solo una columna ocupa todo el espacio horizontal
        self._build_detail(det) # Contruye el panel de detalle
        
        # --- Contenedor Overlay para Lista de Videos (Inicialmente Oculto)
        self.frame_videos = tk.Frame(self.body, bg=BG)

        self.frame_musica = tk.Frame(self.body, bg=BG)
        
        # --- Contenedor Overlay para Servicios Online (Inicialmente Oculto)
        self.frame_servicios = tk.Frame(self.body, bg=BG)

        # --- Pantalla negra donde VLC renderiza el video (cubre toda la app)
        # Ocupa la ventana raíz (no self.body) para tapar header y footer también
        self.video_display = tk.Frame(self.root, bg='black')

        # Notificación
        self._notif = tk.Label(self.root, text="", font=("Helvetica", 12, "bold"),
                               bg=GREEN, fg=WHITE, pady=7, padx=20, anchor="w")

        # Footer
        ftr = tk.Frame(self.root, bg=BG_HDR) # Contenedor para el footer
        ftr.grid(row=3, column=0, sticky="ew")
        tk.Frame(ftr, bg=BG_LINE, height=1).pack(fill=tk.X) # Línea separadora
        row = tk.Frame(ftr, bg=BG_HDR)
        row.pack(fill=tk.X, padx=14, pady=5) #Fila para mostrar los controles del control remoto
        for key, desc in [("UP/DN","Navegar"),("OK","Seleccionar"),("PREV","Regresar")]:
            tk.Label(row, text=f" {key} ", font=("Helvetica", 8, "bold"), # Resalta la tecla del control 
                     bg=GREEN, fg=WHITE, padx=2, pady=1).pack(side=tk.LEFT, padx=(0,3)) # Muestra la descripción de la función
            tk.Label(row, text=desc, font=("Helvetica", 9),
                     bg=BG_HDR, fg=GRAY).pack(side=tk.LEFT, padx=(0,16))

    def _build_sidebar(self, sb):
        tk.Label(sb, text="MENU PRINCIPAL", font=("Helvetica", 8, "bold"),
                 bg=BG_SB, fg=GRAY, padx=14, pady=9, anchor="w").pack(fill=tk.X)
        tk.Frame(sb, bg=BG_LINE, height=1).pack(fill=tk.X)

        self._filas = []
        self._icon_imgs = []  # referencias para evitar que el GC borre las imágenes
        for item in ITEMS:
            row = tk.Frame(sb, bg=BG_SB) # Fila para cada item del menú con fondo de color BG_SB
            row.pack(fill=tk.X) # Hace que la fila ocupe todo el ancho del sidebar
            bar = tk.Frame(row, bg=BG_SB, width=5) # Barra lateral que resalta cada item seleccionado
            bar.pack(side=tk.LEFT, fill=tk.Y) # La barra posiciona a la izquierda cada item y ocupa toda la altura de la fila 

            # Intentar cargar PNG con PIL; si falla, usar carácter de texto
            foto = None
            if _PIL_OK:
                try:
                    img  = Image.open(ICON_DIR / item["icon"]).resize((26, 26), Image.LANCZOS)
                    foto = ImageTk.PhotoImage(img)
                except Exception:
                    foto = None
            self._icon_imgs.append(foto)

            if foto:
                ico = tk.Label(row, image=foto, bg=BG_SB, width=40, pady=12)
            else:
                ico = tk.Label(row, text=item["char"], font=("Helvetica", 16), bg=BG_SB, fg=GRAY, width=4, pady=12)
            ico.pack(side=tk.LEFT)

            lbl = tk.Label(row, text=item["label"], font=("Helvetica", 13), bg=BG_SB, fg=LGRAY, anchor="w", pady=12)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            arr = tk.Label(row, text="<", font=("Helvetica", 13), bg=BG_SB, fg=BG_SB, padx=8, pady=12)
            arr.pack(side=tk.RIGHT)
            tk.Frame(sb, bg=BG_LINE, height=1).pack(fill=tk.X)
            self._filas.append({"row": row, "bar": bar, "ico": ico, "lbl": lbl, "arr": arr,
                                 "usa_img": foto is not None})

        self._refrescar_sidebar()

    def _build_detail(self, det):
        inner = tk.Frame(det, bg=BG)
        inner.place(relx=0.5, rely=0.42, anchor="center")
        self._d_ico  = tk.Label(inner, text="", font=("Helvetica", 44, "bold"), bg=BG, fg=GREEN)
        self._d_ico.pack(pady=(0,8))
        self._d_tit  = tk.Label(inner, text="", font=("Helvetica", 20, "bold"), bg=BG, fg=WHITE)
        self._d_tit.pack()
        self._d_desc = tk.Label(inner, text="", font=("Helvetica", 12), bg=BG, fg=GRAY, wraplength=340, justify="center")
        self._d_desc.pack(pady=(8,18))
        self._d_btn  = tk.Label(inner, text="  Presiona  OK  ", font=("Helvetica", 11, "bold"), bg=GREEN, fg=WHITE, padx=14, pady=7)
        self._d_btn.pack()
        self._refrescar_detalle()

    def _refrescar_sidebar(self):
        for i, ui in enumerate(self._filas): # Recorre todas las filas del sidebar
            sel   = (i == self.idx)
            exit_ = "Salir" in ITEMS[i]["label"]
            ac    = GREEN2 if exit_ else GREEN
            bg    = BG_SEL if sel else BG_SB
            ui["row"].config(bg=bg)
            ui["bar"].config(bg=ac if sel else BG_SB)
            ui["ico"].config(bg=bg)
            if not ui["usa_img"]:  # solo cambiar color de texto, no de imagen
                ui["ico"].config(fg=ac if sel else GRAY)
            ui["lbl"].config(bg=bg, fg=WHITE if sel else LGRAY, font=("Helvetica",14,"bold") if sel else ("Helvetica",13))
            ui["arr"].config(bg=bg, fg=ac if sel else bg)

    def _refrescar_detalle(self):
        item  = ITEMS[self.idx]
        exit_ = "Salir" in item["label"]
        ac    = GREEN2 if exit_ else GREEN
        self._d_ico.config(text=item["char"], fg=ac)
        self._d_tit.config(text=item["label"])
        self._d_desc.config(text=item["desc"])
        self._d_btn.config(bg=ac)

    def _tick_clock(self):
        self._clk.config(text=time.strftime("%H:%M"))
        self.root.after(10_000, self._tick_clock)

    # ======================================
    #  UI VIDEOS USB OVERLAY
    # ======================================
    def abrir_menu_videos(self, path, videos_rutas):
        """Prepara el estado para mostrar la lista de videos del USB.

        videos_rutas: lista de rutas COMPLETAS devuelta por obtener_videos().
        """
        self.estado = "VIDEOS"
        self.ruta_usb = path
        self.videos_rutas = sorted(videos_rutas)  # rutas completas para reproducir
        # videos_usb: índice 0 = opción especial, resto = nombres de archivo para mostrar
        self.videos_usb = ["▶ REPRODUCIR TODO (Modo Presentación)"] + [
            os.path.basename(r) for r in self.videos_rutas
        ]
        self.idx_video = 1
        self._refrescar_menu_videos()

    def _refrescar_menu_videos(self):
        """Renderiza la lista de videos sobre el cuerpo principal, con paginación."""
        self.frame_videos.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Limpiar widgets anteriores
        for w in self.frame_videos.winfo_children(): w.destroy()

        tk.Label(self.frame_videos, text="CONTENIDO DE VIDEO DETECTADO", 
                 font=("Helvetica", 18, "bold"), bg=BG, fg=GRAY).pack(pady=(30, 20))

        # Paginación (Para no saturar la pantalla si hay muchos videos)
        max_visibles = 7
        inicio = max(0, min(self.idx_video - 3, len(self.videos_usb) - max_visibles))
        fin = min(len(self.videos_usb), inicio + max_visibles)

        for i in range(inicio, fin):
            texto = self.videos_usb[i]
            sel = (i == self.idx_video)
            bg_color = GREEN if sel else BG_SB
            fg_color = WHITE if sel else LGRAY
            font_w = "bold" if sel else "normal"

            lbl = tk.Label(self.frame_videos, text=texto, font=("Helvetica", 14, font_w),
                           bg=bg_color, fg=fg_color, anchor="w", padx=20, pady=12)
            lbl.pack(fill=tk.X, padx=80, pady=4)

        if len(self.videos_usb) > max_visibles:
            tk.Label(self.frame_videos, text=f"Mostrando {inicio+1} - {fin} de {len(self.videos_usb)}",
                     bg=BG, fg=GRAY, font=("Helvetica", 10)).pack(pady=10)

    # ======================================
    #  UI MUSIC USB OVERLAY
    # ======================================
    def _abrir_menu_musica(self, path, canciones):
        self.estado = "MUSICA"
        self.canciones_rutas = sorted(canciones)
        self.canciones_usb = ["♪ REPRODUCIR TODO (Bucle)"] + [os.path.basename(c)for c in self.canciones_rutas]
        self.idx_cancion = 0
        self._refrescar_menu_musica()

    def _refrescar_menu_musica(self):
        self.frame_musica.place(relx=0, rely=0, relwidth=1, relheight=1)
        for w in self.frame_musica.winfo_children():
            w.destroy()
        tk.Label(self.frame_musica, text="CONTENIDO MUSICAL DETECTADO",
                 font=("Helvetica", 18, "bold"), bg=BG, fg=GRAY).pack(pady=(30, 20))
        max_visibles = 7
        inicio = max(0, min(self.idx_cancion - 3, len(self.canciones_usb) - max_visibles))
        fin = min(len(self.canciones_usb), inicio + max_visibles)
        for i in range(inicio, fin):
            nombre = self.canciones_usb[i]
            sel = (i == self.idx_cancion)
            tk.Label(self.frame_musica, text=nombre,
                     bg=GREEN if sel else BG_SB, fg=WHITE,
                     font=("Helvetica", 14, "bold" if sel else "normal"),
                     anchor="w", padx=20, pady=10).pack(fill=tk.X, padx=80, pady=3)
        if len(self.canciones_usb) > max_visibles:
            tk.Label(self.frame_musica, text=f"Mostrando {inicio+1}-{fin} de {len(self.canciones_usb)}",
                     bg=BG, fg=GRAY, font=("Helvetica", 10)).pack(pady=10)
    
    # ======================================
    #  PANTALLA DE VIDEO
    # ======================================
    def _mostrar_video_display(self):
        """Despliega el frame negro sobre toda la ventana para que VLC renderice."""
        self.video_display.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.video_display.lift()
        self.root.update_idletasks()  # X11 debe registrar la ventana antes de que VLC la use

    def _ocultar_video_display(self):
        """Oculta el frame de video y devuelve el control al menú."""
        self.video_display.place_forget()

    # ======================================
    #  NAVEGACIÓN MULTI-ESTADO
    # ======================================
    def ir_subir(self):
        if self.estado == "PRINCIPAL":
            self.idx = (self.idx - 1) % len(ITEMS)
            self._refrescar_sidebar(); self._refrescar_detalle()
        elif self.estado == "VIDEOS":
            self.idx_video = (self.idx_video - 1) % len(self.videos_usb)
            self._refrescar_menu_videos()
        elif self.estado == "MUSICA":
            self.idx_cancion = (
            self.idx_cancion - 1) % len(self.canciones_usb)
            self._refrescar_menu_musica()
        elif self.estado == "SERVICIOS":
            self.idx_servicio = (self.idx_servicio - 1) % len(self.servicios_items)
            self._refrescar_menu_servicios()

    def ir_bajar(self):
        if self.estado == "PRINCIPAL":
            self.idx = (self.idx + 1) % len(ITEMS)
            self._refrescar_sidebar(); self._refrescar_detalle()
        elif self.estado == "VIDEOS":
            self.idx_video = (self.idx_video + 1) % len(self.videos_usb)
            self._refrescar_menu_videos()
        elif self.estado == "MUSICA":
            self.idx_cancion = (self.idx_cancion + 1) % len(self.canciones_usb)
            self._refrescar_menu_musica()
        elif self.estado == "SERVICIOS":
            self.idx_servicio = (self.idx_servicio + 1) % len(self.servicios_items)
            self._refrescar_menu_servicios()

    def ir_seleccionar(self):
        if self.estado == "PRINCIPAL":
            item = ITEMS[self.idx]
            if "Salir" in item["label"]:
                self.cerrar_aplicacion()
            elif item["label"] == "Servicio Online":
                self.abrir_menu_servicios()
            elif item["label"] == "Videos":
                mp = self.usb_conectado or self._detectar_usb_actual()
                if mp:
                    self.usb_conectado = mp
                    self.analizar_y_reproducir_usb(mp)
                else:
                    self.mostrar_notificacion("No hay USB conectado", "#cc3333")
            elif item["label"] == "Musica":
                mp = self.usb_conectado or self._detectar_usb_actual()
                if mp:
                    self.usb_conectado = mp
                    canciones = obtener_canciones(mp)
                    if canciones:
                        self._abrir_menu_musica(mp, canciones)
                    else:
                        self.mostrar_notificacion("No se encontraron canciones en el USB", "#cc3333")
                else:
                    self.mostrar_notificacion("No hay USB conectado", "#cc3333")
            elif item["label"] == "Fotos":
                mp = self.usb_conectado or self._detectar_usb_actual()
                if mp:
                    self.usb_conectado = mp
                    imagenes = obtener_imagenes(mp)
                    if imagenes:
                        self.mostrar_notificacion(f"{len(imagenes)} fotos detectadas. Iniciando presentacion...", "#0077cc")
                        self._mostrar_video_display()
                        self.reproduciendo_imagenes = True
                        self.imagen_player.iniciar_presentacion(imagenes)
                    else:
                        self.mostrar_notificacion("No hay fotos en el USB", "#cc3333")
                else:
                    self.mostrar_notificacion("No hay USB conectado", "#cc3333")
            else:
                self.mostrar_notificacion(f"Abriendo: {item['label']}", GREEN)

        elif self.estado == "VIDEOS":
            if self.idx_video == 0:
                self.mostrar_notificacion("Iniciando Presentacion de Videos...", GREEN)
                self._mostrar_video_display()
                self.reproduciendo_video = True
                self.video_player.reproducir_lista(self.videos_rutas, loop=True)
            else:
                nombre = self.videos_usb[self.idx_video]
                ruta   = self.videos_rutas[self.idx_video - 1]
                self.mostrar_notificacion(f"Reproduciendo: {nombre}", GREEN)
                self._mostrar_video_display()
                self.reproduciendo_video = True
                self.video_player.reproducir_lista([ruta], loop=False)

        elif self.estado == "MUSICA":
            if self.idx_cancion == 0:
                self.reproduciendo_musica = True
                self.audio_player.reproducir_lista(self.canciones_rutas, loop=True)
                self.mostrar_notificacion("Reproduciendo toda la musica en bucle", GREEN)
            else:
                ruta = self.canciones_rutas[self.idx_cancion - 1]
                self.reproduciendo_musica = True
                self.audio_player.reproducir_lista([ruta], loop=False)
                self.mostrar_notificacion(f"Reproduciendo: {os.path.basename(ruta)}", GREEN)

        elif self.estado == "SERVICIOS":
            item = self.servicios_items[self.idx_servicio]
            if item["tipo"] == "usb":
                mp = self.usb_conectado or self._detectar_usb_actual()
                if mp:
                    self.usb_conectado = mp
                    self.frame_servicios.place_forget()
                    self.estado = "PRINCIPAL"
                    self.analizar_y_reproducir_usb(mp)
                else:
                    self.mostrar_notificacion("No hay USB conectado", "#cc3333")
            else:
                ok, msg = self.gestor_online.abrir_streaming_video(item["key"])
                color = item["color"] if ok else "#cc3333"
                self.mostrar_notificacion(msg, color)

    def ir_regresar(self):
        # 1. Detener cualquier reproducción activa (flags propios, no is_playing())
        if self.reproduciendo_video:
            self.video_player.detener()
            self.reproduciendo_video = False
            self._ocultar_video_display()
            self.mostrar_notificacion("Video detenido", "#228833")
            return
        if self.reproduciendo_imagenes:
            self.imagen_player.detener()
            self.reproduciendo_imagenes = False
            self._ocultar_video_display()
            self.mostrar_notificacion("Presentacion detenida", "#228833")
            return
        if self.reproduciendo_musica:
            self.audio_player.detener()
            self.reproduciendo_musica = False
            self.mostrar_notificacion("Musica detenida", "#228833")
            return  # nos quedamos en el menu de musica

        # 2. Si Chromium está abierto, cerrarlo
        if self.gestor_online.navegador_abierto():
            self.gestor_online.cerrar_navegador()
            self.mostrar_notificacion("Servicio cerrado", "#228833")
            return

        # 3. Cerrar sub-menús y volver al menú principal
        if self.estado == "VIDEOS":
            self.estado = "PRINCIPAL"
            self.frame_videos.place_forget()
            self._ocultar_video_display()
            self.mostrar_notificacion("Regresando al menu principal", "#228833")
        elif self.estado == "MUSICA":
            self.estado = "PRINCIPAL"
            self.frame_musica.place_forget()
            self.mostrar_notificacion("Regresando al menu principal", "#228833")
        elif self.estado == "SERVICIOS":
            self.estado = "PRINCIPAL"
            self.frame_servicios.place_forget()
            self.mostrar_notificacion("Regresando al menu principal", "#228833")

    def ir_apagar_sistema(self):
        self.mostrar_notificacion("Apagando Raspberry Pi...", "#cc3333")
        self.root.update(); time.sleep(2)
        self.cerrar_aplicacion()
        # os.system("sudo shutdown -h now")

    # ======================================
    #  NOTIFICACIÓN
    # ======================================
    def mostrar_notificacion(self, msg, color):
        if self._notif_job:
            self.root.after_cancel(self._notif_job)
        self._notif.config(text=f"  {msg}", bg=color)
        self._notif.place(x=0, y=68, relwidth=1)
        self._notif_job = self.root.after(3000, self._ocultar_notif)

    def _ocultar_notif(self):
        self._notif.place_forget()
        self._notif_job = None

    # ======================================
    #  SERVICIOS ONLINE
    # ======================================
    def abrir_menu_servicios(self):
        """Construye la lista de servicios y muestra el overlay."""
        self.estado = "SERVICIOS"
        self.servicios_items = [
            {"tipo": "servicio", "key": k, **v}
            for k, v in SERVICIOS_VIDEO.items()
        ]
        self.servicios_items.append({
            "tipo":  "usb",
            "key":   "usb",
            "label": "Reproducir desde USB",
            "char":  "◉",
            "color": GREEN,
        })
        self.idx_servicio = 0
        self._internet_ok  = False  # reset; se verifica en hilo para no bloquear UI
        self._refrescar_menu_servicios()
        threading.Thread(target=self._verificar_internet_async, daemon=True).start()

    def _verificar_internet_async(self):
        """Verifica internet en hilo y refresca el indicador cuando termina."""
        self._internet_ok = self.gestor_online.hay_internet()
        self.root.after(0, self._refrescar_menu_servicios)

    def _refrescar_menu_servicios(self):
        """Renderiza la lista de servicios sobre el cuerpo principal."""
        self.frame_servicios.place(relx=0, rely=0, relwidth=1, relheight=1)
        for w in self.frame_servicios.winfo_children():
            w.destroy()

        tk.Label(self.frame_servicios, text="PELICULAS — Elige tu servicio",
                 font=("Helvetica", 18, "bold"), bg=BG, fg=GRAY).pack(pady=(30, 6))

        # Indicador de internet: usa cache (_internet_ok) para no bloquear navegación
        net_txt = "Internet: CONECTADO"   if self._internet_ok else "Internet: Verificando..."
        net_col = "#09e55d"               if self._internet_ok else GRAY
        tk.Label(self.frame_servicios, text=net_txt,
                 font=("Helvetica", 10), bg=BG, fg=net_col).pack(pady=(0, 18))

        for i, item in enumerate(self.servicios_items):
            sel      = (i == self.idx_servicio)
            bg_color = item["color"] if sel else BG_SB
            fg_color = WHITE
            font_w   = "bold" if sel else "normal"
            padx_val = 14

            # Fila: carácter + label
            fila = tk.Frame(self.frame_servicios, bg=bg_color)
            fila.pack(fill=tk.X, padx=100, pady=3)
            tk.Label(fila, text=item["char"], font=("Helvetica", 15, "bold"),
                     bg=bg_color, fg=fg_color, width=3, pady=10).pack(side=tk.LEFT, padx=padx_val)
            tk.Label(fila, text=item["label"], font=("Helvetica", 14, font_w),
                     bg=bg_color, fg=fg_color, anchor="w", pady=10).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(self.frame_servicios,
                 text="OK = Abrir   |   PREV = Regresar",
                 font=("Helvetica", 9), bg=BG, fg=GRAY).pack(pady=(16, 0))

    # ======================================
    #  USB
    # ======================================
    def _loop_usb(self):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem="block", device_type="partition")
        while self.ir._running:
            device = monitor.poll(timeout=1.0)
            if device is None: continue
            if device.action == "add":
                dev_path = f"/dev/{device.sys_name}"
                sp.run(["udisksctl","mount","-b",dev_path], capture_output=True)
                cp = sp.run(["findmnt","-unl","-S",dev_path], capture_output=True, text=True)
                mp = cp.stdout.split(" ")[0].strip() if cp.stdout else ""
                if mp:
                    self.usb_conectado = mp
                    self.root.after(0, lambda m=mp: self.analizar_y_reproducir_usb(m))
            elif device.action == "remove":
                self.usb_conectado = ""
                self.root.after(0, lambda: self.mostrar_notificacion("USB desconectado", "#cc3333"))

    def _detectar_usb_actual(self):
        """Lee /proc/mounts buscando particiones USB (/dev/sd*). Solo funciona en Linux/RPi."""
        try:
            with open("/proc/mounts") as f:
                for linea in f:
                    partes = linea.split()
                    if len(partes) >= 2 and partes[0].startswith("/dev/sd"):
                        return partes[1]  # devuelve el mount point
        except Exception:
            pass
        return ""

    def analizar_y_reproducir_usb(self, path):
        """Detecta el tipo de contenido del USB y actua en consecuencia.
        Usa media/classifier.py y media/videos.py en lugar de reimplementar la logica.
        """
        tipo = classify_usb(path)  # 'video', 'audio', 'image', 'mixed' o 'empty'

        if tipo == "empty":
            self.mostrar_notificacion("USB sin contenido multimedia", GRAY)
        elif tipo == "mixed":
            self.mostrar_notificacion("USB mixto — elige que reproducir", "#cc8800")
        elif tipo == "video":
            videos = obtener_videos(path)  # lista de rutas completas
            self.mostrar_notificacion(f"{len(videos)} videos detectados. Abriendo menu...", "#cc6600")
            self.abrir_menu_videos(path, videos)
        elif tipo == "audio":
            canciones = obtener_canciones(path)
            self.mostrar_notificacion(f"{len(canciones)} canciones detectadas. Abriendo menu...", "#7700cc")
            self._abrir_menu_musica(path, canciones)
        elif tipo == "image":
            imagenes = obtener_imagenes(path)
            self.mostrar_notificacion(f"{len(imagenes)} fotos detectadas. Iniciando presentacion...", "#0077cc")
            self._mostrar_video_display()
            self.reproduciendo_imagenes = True
            self.imagen_player.iniciar_presentacion(imagenes)

    def cerrar_aplicacion(self):
        self.ir.stop()
        self.video_player.detener()
        self.audio_player.detener()
        self.imagen_player.detener()
        self.gestor_online.cerrar_navegador()
        self.root.destroy()
        print("\nKiosko cerrado correctamente.\n")

if __name__ == "__main__":
    root = tk.Tk()
    app  = SmartTVApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.cerrar_aplicacion()
