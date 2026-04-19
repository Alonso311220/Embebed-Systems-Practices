import os
import sys
import json
import magic
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configuración de red solicitada
address = "192.168.50.1"
port = 8080

class WebServer(BaseHTTPRequestHandler):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    def do_HEAD(self):
        if self.path in ('/', '/PaginaGrafica.html'):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

        elif self.path == '/temp.log':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

        elif self.path.startswith('/css') or self.path.startswith('/js'):
            path = self.path.lstrip('/')
            if os.path.isfile(path):
                self.send_response(200)

                if path.endswith(".js"):
                    self.send_header("Content-type", "application/javascript")
                elif path.endswith(".css"):
                    self.send_header("Content-type", "text/css")
                else:
                    self.send_header("Content-type", "text/plain")

                self.end_headers()
            else:
                self.send_error(404)
        else:
            self.send_error(404)
    def _get_log_data(self):
        """Lee temp.log y lo convierte a formato JSON para la gráfica"""
        data_list = []
        if os.path.isfile("temp.log"):
            with open("temp.log", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) == 2:
                        try:
                            data_list.append({
                                "timestamp": float(parts[0]),
                                "temp": float(parts[1])
                            })
                        except ValueError:
                            continue
        return json.dumps(data_list)

    def _serve_file(self, rel_path):
        if not os.path.isfile(rel_path):
            self.send_error(404)
            return

        self.send_response(200)

        if rel_path.endswith(".js"):
            self.send_header("Content-type", "application/javascript")
        elif rel_path.endswith(".css"):
            self.send_header("Content-type", "text/css")
        else:
            self.send_header("Content-type", "text/plain")

        self.end_headers()

        with open(rel_path, 'rb') as file:
            self.wfile.write(file.read())

    def serve_ui_file(self):
        ui_file = "PaginaGrafica.html"

        if not os.path.isfile(ui_file):
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"File not found")
            return

        try:
            with open(ui_file, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()

            self.wfile.write(content)

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_GET(self):
        # 1. Endpoint para los datos que requiere logica.js
        print("GET:", self.path)
        if self.path == '/temp.log':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(self._get_log_data(), "utf-8"))
        
        # 2. Acceso a la raíz: sirve la interfaz gráfica
        elif self.path in ('/', '/PaginaGrafica.html') :
            self.serve_ui_file()
        # 3. Otros archivos (CSS, JS, imágenes)
        elif self.path.startswith('/css') or self.path.startswith('/js'):
            self._serve_file(self.path.lstrip('/'))
        else:
            self.error_content_type = "text/html"
            self.send_error(404, "Archivo no encontrado")   

    def do_POST(self):
        """Mantiene la estructura de POST por si se agrega controles después"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length < 1:
            return
        post_data = self.rfile.read(content_length)
        try:
            jobj = json.loads(post_data.decode("utf-8"))
            print(f"Datos POST recibidos: {jobj}")
            # Aquí se pueden llamar a las funciones necesarias para procesar los datos POST
        except:
            print(sys.exc_info())
            print("Datos POST no reconocidos")

def main():
    # Inicializa la instancia con la IP y puerto específicos
    webServer = HTTPServer((address, port), WebServer)
    print("Servidor iniciado")
    print(f"\tAtendiendo solicitudes en http://{address}:{port}")

    try:
        # Mantiene al servidor ejecutándose
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error inesperado: {e}")
    
    webServer.server_close()
    print("Server stopped.")

if __name__ == "__main__":
    main()
