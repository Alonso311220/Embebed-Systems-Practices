# !/usr/bin/env python3
# ## ###############################################
#
# webserver.py
# Starts a custom webserver and handles all requests
#
# Autor: Mauricio Matamoros
# License: MIT
#
# ## ###############################################
#!/usr/bin/env python3
#!/usr/bin/env python3
import os
import sys
import json  # <--- Fundamental para que la línea 97 funcione
from http.server import BaseHTTPRequestHandler, HTTPServer
import led_manager  # Importamos todo el módulo para acceder a su 'state'

# Configuración
address = "192.168.1.254"
port = 8080

class WebServer(BaseHTTPRequestHandler):
    
    def _serve_file(self, rel_path):
        """Sirve archivos estáticos (CSS, JS)"""
        if not os.path.isfile(rel_path):
            self.send_error(404)
            return
        self.send_response(200)
        if rel_path.endswith(".css"):
            self.send_header("Content-type", "text/css")
        elif rel_path.endswith(".js"):
            self.send_header("Content-type", "application/javascript")
        self.end_headers()
        with open(rel_path, 'rb') as file:
            self.wfile.write(file.read())

    def _serve_ui_file(self):
        """Sirve el HTML principal"""
        if not os.path.isfile("user_interface.html"):
            self.send_error(404, "Archivo HTML no encontrado")
            return
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open("user_interface.html", "r", encoding="utf-8") as f:
            self.wfile.write(bytes(f.read(), "utf-8"))

    def _parse_post(self, json_obj):
        """Mapea el JSON a funciones de led_manager"""
        action = json_obj.get('action')
        value = json_obj.get('value')
        
        switcher = {
            'led': led_manager.leds,
            'marquee': led_manager.marquee,
            'numpad': led_manager.bcd
        }
        
        func = switcher.get(action)
        if func:
            print(f"[*] Ejecutando: {action}({value})")
            func(value)

    def do_GET(self):
        """Maneja la carga de la página y el estado JSON"""
        if self.path == '/':
            self._serve_ui_file()
        elif self.path == '/state':
            # Esta es la ruta que tu JavaScript consulta cada 100ms
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(led_manager.state), "utf-8"))
        else:
            self._serve_file(self.path[1:])

    def do_POST(self):
        """Recibe comandos desde el navegador"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                # Esta es la línea que te marcaba error:
                json_data = json.loads(post_data.decode("utf-8"))
                
                self._parse_post(json_data)
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(bytes(json.dumps({"status": "ok"}), "utf-8"))
        except Exception as e:
            print(f"[!] Error en POST: {e}")
            self.send_response(500)
            self.end_headers()

def main():
    try:
        server = HTTPServer((address, port), WebServer)
        print(f"Servidor listo en http://{address}:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nApagando servidor...")
        server.server_close()

if __name__ == "__main__":
    main()
