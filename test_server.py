import os
import sys
import json
import magic
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configuración del servidor
ADDRESS = "192.168.1.254"
PORT = 8080
UI_FILE = "PaginaGrafica.html"

class WebServer(BaseHTTPRequestHandler):
    """Maneja las solicitudes HTTP para el control de la Raspberry Pi"""

    def _serve_file(self, rel_path):
        """Sirve archivos estáticos detectando su tipo MIME"""
        if not os.path.isfile(rel_path):
            self.send_error(404)
            return
        
        self.send_response(200)
        mime = magic.Magic(mime=True)
        self.send_header("Content-type", mime.from_file(rel_path))
        self.end_headers()
        
        with open(rel_path, 'rb') as file:
            self.wfile.write(file.read())

    def _serve_ui_file(self):
        """Sirve el archivo de interfaz principal (PaginaGrafica.html)"""
        if not os.path.isfile(UI_FILE):
            err = f"Error: {UI_FILE} no encontrado."
            print(err)
            self.send_response(404)
            self.end_headers()
            self.wfile.write(bytes(err, "utf-8"))
            return

        try:
            with open(UI_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            self.wfile.write(bytes(content, "utf-8"))
        except Exception as e:
            print(f"Error al leer el archivo: {e}")
            self.wfile.write(bytes("Error interno al leer la interfaz", "utf-8"))

    def _parse_post(self, json_obj):
        """Procesa las acciones enviadas vía JSON"""
        if 'action' not in json_obj or 'value' not in json_obj:
            return

        switcher = {
            'led': leds,
            'marquee': marquee,
            'numpad': bcd
        }

        func = switcher.get(json_obj['action'])
        if func:
            print(f"\tEjecutando {json_obj['action']} con valor: {json_obj['value']}")
            func(json_obj['value'])

    def do_GET(self):
        """Gestiona solicitudes de páginas"""
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self._serve_ui_file()
        else:
            # Sirve otros recursos (CSS, JS, Imágenes)
            self._serve_file(self.path[1:])

    def do_POST(self):
        """Gestiona el envío de comandos desde la interfaz"""
        content_length = int(self.headers.get('Content-Length', 0))
        
        if content_length < 1:
            return

        try:
            post_data = self.rfile.read(content_length)
            jobj = json.loads(post_data.decode("utf-8"))
            self._parse_post(jobj)
            
            # Responder al cliente que el POST fue exitoso
            self.send_response(200)
            self.end_headers()
        except Exception as e:
            print(f"Error procesando POST: {e}")
            self.send_error(400, "Datos POST no reconocidos")

def main():
    webServer = HTTPServer((ADDRESS, PORT), WebServer)
    print(f"Servidor iniciado en http://{ADDRESS}:{PORT}")

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
    finally:
        webServer.server_close()
        print("Servidor cerrado correctamente.")

if __name__ == "__main__":
    main()
